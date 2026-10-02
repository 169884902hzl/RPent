# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Run an explicit development/gate cohort with warm SAM and Pi0.5 services."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from harness_v5_eval import run_episode


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
    if args.collection_config is not None:
        from robots.libero.v5_collection import OriginalCollection, file_sha
        collection_config = json.loads(args.collection_config.read_text())
        bank_path = Path(collection_config["wording_bank"])
        if file_sha(bank_path) != collection_config["wording_bank_sha256"]:
            raise ValueError("registered wording bank changed")
        wording_bank = json.loads(bank_path.read_text())
        if args.provider != "oracle":
            parser.error("initial collection uses only the original script expert")
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
                    key = episode["suite"] + "/" + str(episode["task"])
                    if collection_config.get("split") == "validation":
                        run_args.instruction_override = wording_bank["tasks"][key]["instruction"]
                    elif episode.get("counterfactual_spec"):
                        variant = json.loads(Path(episode["counterfactual_spec"]).read_text())
                        run_args.instruction_override = variant["rewrites"][episode["seed"] - 10]
                    else:
                        run_args.instruction_override = wording_bank["tasks"][key]["rewrites"][episode["seed"] - 10]
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
        (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
