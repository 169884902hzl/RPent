# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Run an explicit development/gate cohort with warm SAM and Pi0.5 services."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

from harness_v5_eval import run_episode


def validate_collection_identities(episodes: list[dict]) -> None:
    """Require registered original init hashes before launching collection."""
    for episode in episodes:
        digest = episode.get("init_state_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(
                f"collection episode {(episode['suite'], episode['task'], episode['seed'])} "
                "lacks a valid registered init_state_sha256"
            )


def collection_instruction(episode: dict, config: dict, bank: dict) -> str:
    """Resolve every registered instruction before starting GPU services."""
    key = episode["suite"] + "/" + str(episode["task"])
    if episode.get("counterfactual_spec"):
        item = json.loads(Path(episode["counterfactual_spec"]).read_text())
    else:
        item = bank["tasks"].get(key)
        if item is None:
            raise ValueError(f"registered wording bank lacks {key}")
    if config.get("split") == "validation":
        text = item["instruction"]
    else:
        rewrites = item["rewrites"]
        index = episode["seed"] - 10
        if len(rewrites) < 30 or len(set(rewrites)) != len(rewrites):
            raise ValueError(f"{key} needs at least 30 distinct registered rewrites")
        if not 0 <= index < 30:
            raise ValueError(f"{key} collection init must be in 10..39")
        text = rewrites[index]
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{key} has an empty registered instruction")
    return text


def main() -> None:
    """Preserve every attempted episode and yield between episodes on request."""
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--choice-package", type=Path, required=True)
    parser.add_argument(
        "--provider", choices=("oracle", "qwen4b", "dagger2323", "qwen27", "jev", "systemone"), required=True
    )
    parser.add_argument("--choice-endpoint")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pause-marker", type=Path, required=True)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--collection-config", type=Path)
    args = parser.parse_args()
    if not 1 <= args.shard_count <= 3 or not 0 <= args.shard_index < args.shard_count:
        parser.error("one to three nonoverlapping shards are supported")
    manifest = json.loads(args.manifest.read_text())
    collection_config = None
    wording_bank = None
    collection_instructions = {}
    if args.collection_config is not None:
        from robots.libero.v5_collection import OriginalCollection, file_sha
        collection_config = json.loads(args.collection_config.read_text())
        bank_path = Path(collection_config["wording_bank"])
        if file_sha(bank_path) != collection_config["wording_bank_sha256"]:
            raise ValueError("registered wording bank changed")
        wording_bank = json.loads(bank_path.read_text())
        if args.provider not in ("oracle", "qwen4b", "dagger2323", "systemone"):
            parser.error("collection requires the original expert or a local typed model rollout")
        validate_collection_identities(manifest["episodes"])
        from robots.libero.v5_confirmation_exclusions import check_original_collection_episode
        for episode in manifest["episodes"]:
            check_original_collection_episode(episode, collection_config)
        for episode in manifest["episodes"]:
            identity = (episode["suite"], episode["task"], episode["seed"])
            collection_instructions[identity] = collection_instruction(
                episode, collection_config, wording_bank
            )
    identities = [(e["suite"], e["task"], e["seed"]) for e in manifest["episodes"]]
    if len(identities) != len(set(identities)):
        parser.error("duplicate episode identity in cohort")
    if args.provider == "oracle" and (
        manifest["libero_type"] != "standard"
        or any(
            e[0] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
            or not 0 <= e[1] < 10
            for e in identities
        )
    ):
        parser.error("oracle is restricted to the 40 original tasks")
    episodes = manifest["episodes"][args.shard_index :: args.shard_count]
    args.output_dir.mkdir(parents=True, exist_ok=False)
    daemons, endpoints = [], {}
    summary = {
        "purpose": manifest["purpose"],
        "provider": args.provider,
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "shard_count": args.shard_count,
        "shard_index": args.shard_index,
        "planned": len(episodes),
        "attempted": 0,
        "correct_finish": 0,
        "status": "startup",
    }
    started = time.perf_counter()
    startup_error_seen = False
    try:
        for name, module, extra in (
            ("sam3", "robots.libero.v5_sam3_server", []),
            (
                "vla",
                "rpent.robots.components.pi05_vla_server",
                ["--embodiment", "libero"],
            ),
        ):
            port = pick_free_port()
            daemon = ProcessDaemon(
                name=f"v5_batch_{name}",
                cmd=[
                    sys.executable,
                    "-m",
                    module,
                    *extra,
                    "--transport",
                    "http",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--parent-watch",
                ],
                log_path=str(args.output_dir / f"shared_{name}.log"),
            )
            daemons.append(daemon)
            endpoints[name] = f"http://127.0.0.1:{port}"
            daemon.start()
        for name, daemon in zip(("sam3", "vla"), daemons):
            wait_for_ready(HttpRpcClient(endpoints[name]), daemon=daemon, timeout_s=300)
        summary["shared_initialization_s"] = time.perf_counter() - started
        summary["status"] = "running"
        with (args.output_dir / "episodes.jsonl").open("w") as trace:
            for episode in episodes:
                if args.pause_marker.exists():
                    summary["status"] = "yielded_between_episodes"
                    break
                output = (
                    args.output_dir
                    / f"{episode['suite']}_t{episode['task']}_s{episode['seed']}"
                )
                run_args = argparse.Namespace(
                    **episode,
                    libero_type=manifest["libero_type"],
                    provider=args.provider,
                    choice_endpoint=args.choice_endpoint,
                    choice_package=args.choice_package,
                    sam3_endpoint=endpoints["sam3"],
                    vla_endpoint=endpoints["vla"],
                    output_dir=output,
                    done_gated=False,
                    **manifest["budget"],
                )
                collection = None
                if collection_config is not None:
                    identity = (episode["suite"], episode["task"], episode["seed"])
                    run_args.instruction_override = collection_instructions[identity]
                    run_args.done_gated = True
                    collection = OriginalCollection(collection_config, output, run_args)
                try:
                    result = run_episode(run_args, collection=collection)
                except Exception as error:
                    result = (
                        json.loads((output / "result.json").read_text())
                        if (output / "result.json").exists()
                        else {
                            "status": "startup_error",
                            "error": f"{type(error).__name__}: {error}",
                        }
                    )
                if (result.get("status") in ("startup_error", "startup")
                        or result.get("termination_category") == "startup_error"):
                    # Preserve the row, but expose infrastructure startup
                    # failures to Slurm instead of silently exiting 0.
                    startup_error_seen = True
                if collection is not None:
                    collection.finish(result)
                record = {
                    "episode": episode,
                    "output_dir": str(output),
                    "result": result,
                }
                trace.write(json.dumps(record) + "\n")
                trace.flush()
                summary["attempted"] += 1
                summary["correct_finish"] += int(result.get("correct_finish", False))
                (args.output_dir / "summary.json").write_text(
                    json.dumps(summary, indent=2)
                )
            else:
                summary["status"] = "completed"
    finally:
        for daemon in reversed(daemons):
            daemon.stop()
        summary["wall_s"] = time.perf_counter() - started
        summary["startup_error_seen"] = startup_error_seen
        summary["exit_contract"] = "nonzero_if_any_startup_error"
        (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    if startup_error_seen:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
