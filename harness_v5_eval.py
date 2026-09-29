"""Independent v5 runner; official predicates are evaluation-only outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

from robots.libero.v5_state import (
    VERSION,
    candidates,
    entity_record,
    prepare_request,
    serialize,
)


def run_episode(args: argparse.Namespace) -> dict:
    """Run one measured-state episode without exposing simulator goals."""
    from transformers import AutoTokenizer

    from robots.libero.robot_spec import _init_runtime
    from robots.libero.toolkit import LiberoToolkit
    from robots.libero.v5_runtime import MeasuredScene, V5Executor, category
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.memory import MemoryManager
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    from typed_choice_eval import ChoiceScorer

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    sys.path.insert(0, str(args.choice_package))
    import parallel_schema

    tokenizer = AutoTokenizer.from_pretrained(
        args.choice_package, local_files_only=True
    )
    events = NullDashboardEventSink()
    sam_port = pick_free_port()
    sam = ProcessDaemon(
        name="v5_sam3",
        cmd=[
            sys.executable,
            "-m",
            "robots.libero.v5_sam3_server",
            "--transport",
            "http",
            "--host",
            "127.0.0.1",
            "--port",
            str(sam_port),
            "--parent-watch",
        ],
        log_path=str(output / "sam3_v5.log"),
    )
    daemons, toolkit = [], None
    result = {
        "version": VERSION,
        "suite": args.suite,
        "task": args.task,
        "seed": args.seed,
        "provider": args.provider,
        "mode": "engineering_smoke" if args.provider == "smoke" else "development",
        "official_success": False,
        "correct_finish": False,
        "status": "startup",
    }
    config = vars(args).copy()
    config = {k: str(v) if isinstance(v, Path) else v for k, v in config.items()}
    (output / "config.json").write_text(json.dumps(config, indent=2))
    try:
        sam.start()
        sam_rpc = HttpRpcClient(f"http://127.0.0.1:{sam_port}")
        wait_for_ready(sam_rpc, daemon=sam, timeout_s=300)
        runtime_args = argparse.Namespace(
            suite=args.suite,
            task=args.task,
            seed=args.seed,
            libero_type=args.libero_type,
            max_episode_steps=args.max_episode_steps,
            env_endpoint=None,
            vla_endpoint=None,
            sam3_endpoint=f"http://127.0.0.1:{sam_port}",
            molmo_endpoint=None,
            cuda_device=None,
            planner="typed_choice",
            collect_flywheel_data=False,
        )
        daemons, runtime = _init_runtime(runtime_args, output, events, None)
        toolkit = LiberoToolkit(
            runtime_kwargs=runtime,
            dashboard_events=events,
            memory=MemoryManager(output / "empty_memory", memory_access="read_only"),
            state_output_dir=output,
        )
        scene = MeasuredScene(toolkit, sam_rpc, args.seed)
        executor = V5Executor(toolkit, scene, args.max_chunks)
        initial = toolkit.execute_tool("view_env_state", {}).result
        instruction = initial["task_language"]
        vocab = [category(n) for n in initial["state"]["object_names"]]
        scene.refresh(vocab)
        scorer = (
            None
            if args.provider == "smoke"
            else ChoiceScorer(args.provider, args.choice_endpoint)
        )
        rng = random.Random(args.seed)
        (output / "initial_measurements.json").write_text(
            json.dumps(
                {
                    "entities": [entity_record(e) for e in scene.entities.values()],
                    "segmentation_calls": scene.calls,
                    "perception_s": scene.perception_s,
                },
                indent=2,
            )
        )
        result.update(status="running", initialization_s=time.perf_counter() - started)
        last_action = None
        with (output / "choices.jsonl").open("w") as trace:
            for decision in range(args.max_decisions):
                step_started = time.perf_counter()
                entities = list(scene.entities.values())
                choices = candidates(
                    entities,
                    instruction,
                    tuple(executor.p._last_obs_eef_pos),
                    executor.held,
                    executor.receipts,
                    rng,
                )
                context = serialize(
                    instruction,
                    entities,
                    executor.p._last_obs_gripper,
                    executor.held,
                    executor.receipts,
                )
                request, tokens = prepare_request(
                    tokenizer, parallel_schema.prepare_prompts, context, choices
                )
                model_started = time.perf_counter()
                if scorer is None:
                    if executor.held:
                        options = [
                            c
                            for c in choices
                            if c.tool == "place"
                            and args.smoke_target in scene.entities[c.target].name
                        ]
                    elif executor.receipts and executor.receipts[-1].get(
                        "place_verified"
                    ):
                        options = [c for c in choices if c.tool == "finish"]
                    else:
                        options = [
                            c
                            for c in choices
                            if c.tool == "grasp"
                            and args.smoke_object in scene.entities[c.object].name
                            and c.mode == "direct"
                        ]
                    if not options:
                        raise ValueError(
                            "smoke category has no measured feasible candidate"
                        )
                    action = options[0]
                    answer = {
                        "selected": choices.index(action),
                        "probabilities": None,
                        "model": "scripted-engineering-smoke",
                        "model_inference_s": 0.0,
                    }
                else:
                    answer = scorer.score(**request)
                    index = int(answer["selected"])
                    if not 0 <= index < len(choices):
                        raise ValueError("choice index out of bounds")
                    action = choices[index]
                choice_s = time.perf_counter() - model_started
                perception_before = scene.perception_s
                execution_started = time.perf_counter()
                receipt = executor.execute(action)
                action_total_s = time.perf_counter() - execution_started
                perception_s = scene.perception_s - perception_before
                record = {
                    "decision": decision,
                    "request": request,
                    "prompt_tokens": tokens,
                    "candidates": [c.text() for c in choices],
                    "answer": answer,
                    "selected": action.text(),
                    "receipt": receipt,
                    "post_measurements": [
                        entity_record(e) for e in scene.entities.values()
                    ],
                    "official_success": toolkit.solved(),
                    "timing_s": {
                        "model_inference": answer.get("model_inference_s"),
                        "choice_request": choice_s,
                        "perception": perception_s,
                        "execution": action_total_s - perception_s,
                        "total": time.perf_counter() - step_started,
                    },
                }
                trace.write(json.dumps(record, ensure_ascii=True) + "\n")
                trace.flush()
                last_action = action
                result["decisions"] = decision + 1
                if action.tool in ("finish", "ask_help") or executor.p.env.truncated:
                    break
                if executor.p.env.terminated:
                    # Preserve the model's explicit terminal choice after physical
                    # completion; control actions need no further simulator steps.
                    continue
        result.update(
            status="completed",
            official_success=toolkit.solved(),
            correct_finish=bool(
                toolkit.solved() and last_action and last_action.tool == "finish"
            ),
            false_finish=bool(
                not toolkit.solved() and last_action and last_action.tool == "finish"
            ),
            budget_exhausted=bool(
                last_action and last_action.tool not in ("finish", "ask_help")
            ),
            perception_calls=scene.calls,
            perception_s=scene.perception_s,
        )
        return result
    except Exception as error:
        result.update(status="error", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        if toolkit is not None:
            toolkit.close()
        for daemon in reversed(daemons):
            daemon.stop()
        sam.stop()
        result["wall_s"] = time.perf_counter() - started
        result["source_hashes"] = {
            name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
            for name in (
                "harness_v5_eval.py",
                "robots/libero/v5_state.py",
                "robots/libero/v5_runtime.py",
                "robots/libero/v5_sam3_server.py",
            )
        }
        (output / "result.json").write_text(json.dumps(result, indent=2))


def main() -> None:
    """Run a single bounded episode using its explicit output path."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="libero_spatial")
    parser.add_argument("--task", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--libero-type", choices=("standard", "pro"), default="standard"
    )
    parser.add_argument(
        "--provider", choices=("smoke", "qwen4b", "dagger2323", "jev"), default="smoke"
    )
    parser.add_argument("--choice-endpoint")
    parser.add_argument("--choice-package", type=Path, required=True)
    parser.add_argument("--max-decisions", type=int, default=4)
    parser.add_argument("--max-episode-steps", type=int, default=3000)
    parser.add_argument("--max-chunks", type=int, default=40)
    parser.add_argument("--smoke-object", default="bowl")
    parser.add_argument("--smoke-target", default="plate")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.libero_type == "pro" and args.provider == "smoke":
        parser.error("engineering smoke is original-task-only")
    run_episode(args)


if __name__ == "__main__":
    main()
