# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Manifest-driven RPent original API planner development, without memory."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    """Warm model services, check two tool episodes, then continue the cohort."""
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pause-marker", type=Path, required=True)
    parser.add_argument("--base-url", default="http://node02:18360/v1")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=False)
    memory = args.output_dir / "empty_memory"
    memory.mkdir()
    # The original CLI requires a corpus file; zero bytes carry no memory.
    (memory / "MEMORY.md").write_text("")
    endpoints, daemons = {}, []
    summary = {
        "purpose": manifest["purpose"],
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "model": manifest["model"],
        "model_revision": manifest["model_revision"],
        "memory_bytes": 0,
        "planned": len(manifest["episodes"]),
        "attempted": 0,
        "official_success": 0,
        "status": "startup",
    }
    start = time.perf_counter()
    try:
        for name, module, extra in (
            ("sam3", "rpent.robots.components.sam3_server", []),
            (
                "vla",
                "rpent.robots.components.pi05_vla_server",
                ["--embodiment", "libero"],
            ),
        ):
            port = pick_free_port()
            endpoints[name] = f"http://127.0.0.1:{port}"
            daemon = ProcessDaemon(
                name=f"a1n_{name}",
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
            daemon.start()
        for name, daemon in zip(("sam3", "vla"), daemons):
            wait_for_ready(HttpRpcClient(endpoints[name]), daemon=daemon, timeout_s=300)
        summary["shared_initialization_s"] = time.perf_counter() - start
        summary["status"] = "running"
        smoke_tools = []
        with (args.output_dir / "episodes.jsonl").open("x") as trace:
            for index, episode in enumerate(manifest["episodes"]):
                if args.pause_marker.exists():
                    summary["status"] = "yielded_between_episodes"
                    break
                tag = f"{episode['suite']}_t{episode['task']}_s{episode['seed']}"
                output = args.output_dir / tag
                output.mkdir()
                cmd = [
                    sys.executable,
                    "-m",
                    "rpent.cli.main",
                    "--robot",
                    "libero",
                    "--planner",
                    "api",
                    "--model",
                    f"openai-chat:{manifest['model']}",
                    "--base-url",
                    args.base_url,
                    "--reasoning-effort",
                    "none",
                    "--memory-profile",
                    "local",
                    "--memory-dir",
                    str(memory),
                    "--no-auto-merge-memory",
                    "--libero-type",
                    "pro",
                    "--suite",
                    episode["suite"],
                    "--task",
                    str(episode["task"]),
                    "--seed",
                    str(episode["seed"]),
                    "--output-dir",
                    str(output),
                    "--sam3-endpoint",
                    endpoints["sam3"],
                    "--vla-endpoint",
                    endpoints["vla"],
                    "--max-turns",
                    str(manifest["budget"]["max_turns"]),
                    "--max-episode-steps",
                    str(manifest["budget"]["max_episode_steps"]),
                    "--planner-timeout-s",
                    str(manifest["budget"]["planner_timeout_s"]),
                ]
                (output / "command.json").write_text(json.dumps(cmd, indent=2))
                started = time.perf_counter()
                with (output / "cli.log").open("w") as log:
                    completed = subprocess.run(
                        cmd, stdout=log, stderr=subprocess.STDOUT, check=False
                    )
                states_path = output / "states.json"
                raw = (
                    json.loads(states_path.read_text()) if states_path.exists() else []
                )
                states = (
                    raw
                    if isinstance(raw, list)
                    else raw.get("steps", raw.get("records", []))
                )
                physical = any(s.get("terminated", False) for s in states)
                transcript_path = output / f"transcript_{tag}.json"
                transcript = (
                    json.loads(transcript_path.read_text())
                    if transcript_path.exists()
                    else {}
                )
                stats = transcript.get("stats", {})
                calls = stats.get("tool_calls", 0)
                record = {
                    "episode": episode,
                    "output_dir": str(output),
                    "exit_code": completed.returncode,
                    "wall_s": time.perf_counter() - started,
                    "official_success": physical,
                    "finish": transcript.get("finish"),
                    "stats": stats,
                    "decision_timing_kind": "HTTP_round_trip",
                }
                trace.write(json.dumps(record) + "\n")
                trace.flush()
                summary["attempted"] += 1
                summary["official_success"] += int(physical)
                if index < 2:
                    smoke_tools.append(bool(calls) and completed.returncode == 0)
                (args.output_dir / "summary.json").write_text(
                    json.dumps(summary, indent=2)
                )
                print(json.dumps(record), flush=True)
                if index == 1 and not all(smoke_tools):
                    summary["status"] = "tool_smoke_failed"
                    break
            else:
                summary["status"] = "completed"
    finally:
        for daemon in reversed(daemons):
            daemon.stop()
        summary["wall_s"] = time.perf_counter() - start
        (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
