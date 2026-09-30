#!/usr/bin/env python3
"""Direct Pi0.5 check using measured action rows and standard LIBERO budgets.

The network horizon and the executed action chunk are distinct. Count actions
at the env RPC boundary; never estimate executed steps from network horizon.
"""
from __future__ import annotations

import argparse
import json
import time
from argparse import Namespace
from pathlib import Path

SUITES = [
    ("libero_spatial", 10, 220),
    ("libero_object", 10, 280),
    ("libero_goal", 10, 300),
    ("libero_10", 10, 520),
]
ACTION_HORIZON = 5


def _scalar_steps(env) -> int | None:
    value = getattr(env, "elapsed_steps", None)
    if value is None:
        return None
    try:
        return int(value[0])
    except Exception:
        try:
            return int(value)
        except Exception:
            return None


def _scalar_bool(env, name: str) -> bool:
    value = getattr(env, name, False)
    try:
        return bool(value[0])
    except Exception:
        return bool(value)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--action-horizon", type=int, default=ACTION_HORIZON)
    args = ap.parse_args()
    if args.action_horizon <= 0:
        ap.error("--action-horizon must be positive")
    import sys

    sys.path.insert(0, str(args.source))
    from robots.libero.robot_spec import _init_runtime, _spawn_vla_server
    from robots.libero.toolkit import LiberoToolkit
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.memory import MemoryManager
    from rpent.utils.daemon import ProcessDaemon
    from rpent.utils.rpc import wait_for_ready

    events = NullDashboardEventSink()
    args.output.mkdir(parents=True, exist_ok=False)
    vla_args = Namespace(
        suite="libero_spatial",
        task=0,
        seed=0,
        libero_type="standard",
        max_episode_steps=220,
        env_endpoint=None,
        vla_endpoint=None,
        sam3_endpoint=None,
        molmo_endpoint=None,
        cuda_device=None,
        planner="typed_choice",
        collect_flywheel_data=False,
    )
    vla_dir = args.output / "shared_vla"
    vla_dir.mkdir()
    vla_daemon, vla_rpc = _spawn_vla_server(vla_args, vla_dir)
    wait_for_ready(vla_rpc, daemon=vla_daemon, timeout_s=600)
    vla_endpoint = getattr(vla_rpc, "_base_url")
    records = []
    try:
        for suite, count, episode_steps in SUITES:
            max_chunks = episode_steps
            for task in range(count):
                out = args.output / f"{suite}_t{task}_s0"
                out.mkdir()
                started = time.perf_counter()
                daemons = []
                toolkit = None
                rec = {
                    "suite": suite,
                    "task": task,
                    "seed": 0,
                    "provider": "pi05_direct_vla_act",
                    "planner": None,
                    "action_horizon": args.action_horizon,
                    "suite_max_episode_steps": episode_steps,
                    "max_chunks_safety_cap": max_chunks,
                    "status": "startup",
                }
                try:
                    run_args = Namespace(
                        suite=suite,
                        task=task,
                        seed=0,
                        libero_type="standard",
                        max_episode_steps=episode_steps,
                        env_endpoint=None,
                        vla_endpoint=vla_endpoint,
                        sam3_endpoint=None,
                        molmo_endpoint=None,
                        cuda_device=None,
                        planner="typed_choice",
                        collect_flywheel_data=False,
                    )
                    daemons, runtime = _init_runtime(
                        run_args, out, events, {"env", "sam3", "vla"}
                    )
                    memory_dir = out / "empty_memory"
                    memory_dir.mkdir()
                    (memory_dir / "MEMORY.md").write_text("")
                    toolkit = LiberoToolkit(
                        runtime_kwargs=runtime,
                        dashboard_events=events,
                        memory=MemoryManager(memory_dir, memory_access="read_only"),
                        state_output_dir=out,
                    )
                    instruction = str(
                        toolkit.primitives._last_obs.get("task_descriptions") or ""
                    )
                    chunks = 0
                    chunk_times = []
                    action_rows = []
                    predicted_shapes = []
                    obs_shapes = {k: list(v.shape) for k, v in
                                  toolkit.primitives._last_obs.items()
                                  if hasattr(v, "shape")}
                    env = toolkit.primitives.env
                    original_chunk = env.chunk_step

                    def counted_chunk(actions, *, return_all_frames=None):
                        remaining = episode_steps - sum(action_rows)
                        shape = list(actions.shape)
                        predicted_shapes.append(shape)
                        bounded = actions[:remaining]
                        result = original_chunk(bounded, return_all_frames=return_all_frames)
                        action_rows.append(len(bounded))
                        return result

                    env.chunk_step = counted_chunk
                    rec.update(status="running", instruction=instruction)
                    (out / "running.json").write_text(json.dumps(rec, indent=2))
                    while (
                        not _scalar_bool(toolkit.primitives.env, "terminated")
                        and not _scalar_bool(toolkit.primitives.env, "truncated")
                        and sum(action_rows) < episode_steps
                    ):
                        t0 = time.perf_counter()
                        toolkit.primitives._vlm_chunk(instruction)
                        chunk_times.append(time.perf_counter() - t0)
                        chunks += 1
                    actual_steps = sum(action_rows)
                    success = _scalar_bool(toolkit.primitives.env, "terminated")
                    truncated = _scalar_bool(toolkit.primitives.env, "truncated")
                    if success:
                        reason = "official_success"
                    elif truncated or (
                        actual_steps is not None and actual_steps >= episode_steps
                    ):
                        reason = "episode_step_budget"
                    elif chunks >= max_chunks:
                        reason = "vla_chunk_budget"
                    elif actual_steps is not None:
                        reason = "terminated_without_success"
                    else:
                        reason = "loop_exit"
                    rec.update(
                        status="completed",
                        official_success=success,
                        truncated=truncated,
                        chunks=chunks,
                        actual_env_steps=actual_steps,
                        executed_action_rows=action_rows,
                        predicted_action_shapes=predicted_shapes,
                        observation_shapes=obs_shapes,
                        step_count_source="env.chunk_step submitted action rows",
                        estimated_env_steps=None,
                        termination_reason=reason,
                        chunk_wall_s=chunk_times,
                    )
                except Exception as exc:
                    rec.update(
                        status="error",
                        error=f"{type(exc).__name__}: {exc}",
                        termination_reason="error",
                    )
                finally:
                    if toolkit is not None:
                        try:
                            toolkit.close()
                        except Exception as exc:
                            rec["close_error"] = f"{type(exc).__name__}: {exc}"
                    for daemon in reversed(daemons):
                        try:
                            daemon.stop()
                        except Exception:
                            pass
                    rec["wall_s"] = time.perf_counter() - started
                    (out / "result.json").write_text(json.dumps(rec, indent=2))
                records.append(rec)
                (args.output / "summary.json").write_text(
                    json.dumps(
                        {
                            "planned": 40,
                            "attempted": len(records),
                            "official_success": sum(
                                bool(r.get("official_success")) for r in records
                            ),
                            "action_horizon": args.action_horizon,
                            "suite_budgets": {
                                s: {
                                    "max_episode_steps": steps,
                                    "max_chunks_safety_cap": steps,
                                }
                                for s, _, steps in SUITES
                            },
                            "records": records,
                            "vla_endpoint": vla_endpoint,
                        },
                        indent=2,
                    )
                )
                print(json.dumps(rec), flush=True)
    finally:
        if vla_daemon is not None:
            vla_daemon.stop()


if __name__ == "__main__":
    main()
