"""Original LIBERO paired feasibility, with private oracle labels isolated."""
from __future__ import annotations

import argparse
import cProfile
from collections import Counter
from contextlib import contextmanager
import hashlib
import inspect
import json
import os
from pathlib import Path
import random
import re
import subprocess
import time
import traceback

import numpy as np

from scripts.probe_bounded_motion import LocalRPC, original_session, write

ORIGINAL_SUITES = ("libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90")


def public_vocabulary(instruction):
    """Queries from task language and a static visual category vocabulary.

    No per-scene object inventory, instance count or BDDL symbol is consumed.
    All resulting entities still require RGB-D segmentation/measurement.
    """
    from robots.libero.v5_runtime import category, instruction_noun_phrases, scene_vocabulary

    text = instruction.lower().replace('_', ' ')
    names = set(scene_vocabulary([], text))
    known = ('bowl', 'plate', 'ramekin', 'alphabet soup', 'tomato sauce', 'salad dressing',
        'ketchup', 'cream cheese', 'barbecue sauce', 'butter', 'milk', 'chocolate pudding',
        'porcelain mug', 'cookie box', 'moka pot', 'red coffee mug', 'white yellow mug',
        'black book', 'basket', 'rack', 'caddy', 'wine bottle', 'table')
    names.update(name for name in known if re.search(r'\b'+re.escape(name)+r'\b', text))
    for word, visual_label in [('frying pan', 'frypan'), ('frypan', 'frypan'),
                               ('red mug', 'red coffee mug'), ('white and yellow mug', 'white yellow mug')]:
        if word in text:
            names.add(visual_label)
    for phrase in instruction_noun_phrases(text):
        value = category(phrase)
        if value in known or value in {'drawer', 'cabinet', 'microwave', 'stove'}:
            names.add(value)
    return sorted(names)


def category_of(instruction):
    text = instruction.lower()
    if text.startswith("push ") and "plate" in text:
        return "plate_push"
    if "turn off" in text:
        return "stove_off"
    if "turn on" in text:
        return "stove_on"
    if "drawer" in text and text.startswith(("open", "close")):
        return "drawer_"+("open" if text.startswith("open") else "close")
    if "microwave" in text and text.startswith(("open", "close")):
        return "microwave_"+("open" if text.startswith("open") else "close")
    found = []
    for category, words in (("cup", ("cup", "mug")), ("plate", ("plate",)),
                             ("box", ("box", "cream cheese", "alphabet soup", "tomato sauce")),
                             ("bowl", ("bowl",))):
        positions = [text.index(word) for word in words if word in text]
        if positions:
            found.append((min(positions), category+"_transfer"))
    if found:
        return min(found)[1]
    if " in " in text or " into " in text:
        return "container"
    return None


def build_plan(output, count):
    """Fix the original task/state cohort before any policy result is read."""
    from rlinf.envs.libero.utils import benchmark
    from libero.libero import get_libero_path
    expected = {"bowl_transfer", "plate_push", "box_transfer", "cup_transfer", "container",
                "drawer_open", "drawer_close", "stove_on", "stove_off", "microwave_open", "microwave_close"}
    selected, catalog = {}, []
    for name in ORIGINAL_SUITES:
        suite = benchmark.get_benchmark(name)()
        for task_id in range(suite.n_tasks):
            task = suite.get_task(task_id)
            instruction = task.language
            category = category_of(instruction)
            catalog.append({"suite": name, "task": task_id, "instruction": instruction, "category": category})
            if category not in expected or category in selected:
                continue
            path = Path(get_libero_path("bddl_files"))/task.problem_folder/task.bddl_file
            states = suite.get_task_init_states(task_id)
            selected[category] = [{"name": f"{category}_{name}_t{task_id}_s{seed}", "category": category,
                "episode": {"suite": name, "task": task_id, "seed": seed},
                "state_sha256": hashlib.sha256(np.asarray(states[seed], dtype="<f8").tobytes()).hexdigest(),
                "bddl": {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
                "purpose": "development_feasibility_no_training"} for seed in range(min(count, len(states)))]
    plan = {"version": "bounded-original-feasibility/1", "cases": [case for key in sorted(selected) for case in selected[key]],
            "missing_categories": sorted(expected-set(selected)), "budget": {"sim_steps": 10000, "decisions": 160},
            "source_commit": os.environ.get("SOURCE_COMMIT"), "training": False,
            "arms": ["oracle_k1", "oracle_k4", "v5_expert", "pi05_only"], "catalog": catalog}
    write(output, plan)
    return plan


@contextmanager
def services(output, *, vla=True):
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    owned, endpoints = [], {}
    modules = [("sam3", "robots.libero.v5_sam3_server", [])]
    if vla:
        modules.append(("vla", "rpent.robots.components.pi05_vla_server", ["--embodiment", "libero"]))
    try:
        for name, module, extra in modules:
            port = pick_free_port()
            daemon = ProcessDaemon(name="bounded_"+name, cmd=[os.sys.executable, "-m", module, *extra,
                "--transport", "http", "--host", "127.0.0.1", "--port", str(port), "--parent-watch"],
                log_path=str(output/f"{name}.log"))
            owned.append(daemon)
            daemon.start()
            endpoints[name] = HttpRpcClient(f"http://127.0.0.1:{port}")
        for (name, _, _), daemon in zip(modules, owned):
            wait_for_ready(endpoints[name], daemon=daemon, timeout_s=600)
        yield endpoints
    finally:
        for daemon in reversed(owned):
            daemon.stop()


def episode(case, arm, endpoints, output, config, *, startup=False, choice_endpoint=None,
            decision_latency_s=.9853, preparation_latency_s=0.):
    from robots.libero.toolkit import LiberoToolkit
    from robots.libero.v5_runtime import MeasuredScene, V5Executor, category, scene_vocabulary
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from robots.libero.bounded_oracle import BoundedOracle, NoPublicOption
    from robots.libero.v5_oracle_policy import OriginalOraclePolicy
    from robots.libero.v5_state import candidates
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.memory import MemoryManager
    from rpent.robots.components.pi05_vla_client import Pi05VLAClient
    from rpent.robots.components.sam3_client import Sam3Client
    from robots.libero.v5_subtasks import subtask_candidates
    ep = case["episode"]
    facade, primitives = original_session(ep["suite"], ep["task"], ep["seed"], 10000)
    import robosuite
    toolkit = None
    adapter = None
    async_choices = None
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=False)
    try:
        sam3 = Sam3Client(endpoints["sam3"])
        model = Pi05VLAClient(endpoints["vla"], embodiment="libero") if "vla" in endpoints else None
        toolkit = LiberoToolkit(runtime_kwargs={"env": primitives.env, "model": model, "sam3_client": sam3},
            dashboard_events=NullDashboardEventSink(), memory=MemoryManager(output/"empty_memory", memory_access="read_only"),
            state_output_dir=output)
        scene_flags = {key: value for key, value in config.items() if key in inspect.signature(MeasuredScene).parameters}
        scene_flags.update(dual_view_fusion_v1=True, furniture_parts_v1=True, instruction_queries_v1=True,
                           wrist_recall_v1=True, occluded_measurement_cache_v2=True)
        scene = MeasuredScene(toolkit, endpoints["sam3"], ep["seed"], **scene_flags)
        flags = {key: value for key, value in config.items()
                 if key in inspect.signature(V5Executor).parameters and key not in {"toolkit", "scene", "max_chunks", "instruction"}}
        # Whole-task use is controlled by candidate generation, not an
        # executor constructor option. Validate this exact constructor on CPU.
        max_chunks = int(config.get("max_chunks", 40))
        executor = V5Executor(toolkit, scene, max_chunks, **flags)
        initial = toolkit.execute_tool("view_env_state", {}).result
        instruction = initial["task_language"]
        scene.instruction = executor.instruction = instruction
        if arm.startswith(('oracle', 'model')) or arm == 'call_vla':
            # A simulator inventory is not a sensor measurement. Keep its
            # category counts out of the new bounded skill-package path.
            scene.refresh(public_vocabulary(instruction))
        else:
            scene.instance_limits = Counter(category(name) for name in initial["state"]["object_names"])
            scene.refresh(scene_vocabulary(initial["state"]["object_names"], instruction))
        p = executor.p
        rpc = LocalRPC(facade)
        adapter = None
        if arm.startswith(("oracle", "model")) or arm == "call_vla":
            xml = Path(robosuite.__file__).parent/"models/assets/grippers/panda_gripper.xml"
            adapter = MeasuredSkillAdapter(executor, xml, allow_vla=arm == "call_vla")
            policy = None if arm.startswith("model") else BoundedOracle(rpc, adapter)
            if arm.startswith("model"):
                from robots.libero.bounded_async import AsyncSkillDecisions, http_choice
                choose = http_choice(choice_endpoint)
                async_choices = AsyncSkillDecisions(choose, decision_latency_s=decision_latency_s,
                    preparation_latency_s=preparation_latency_s)
        else:
            policy = OriginalOraclePolicy(rpc, persist_retries=True)
        records, skill_steps = [], Counter()
        maximum = 8 if startup else 10000 if arm == "pi05_only" else 160
        decision_count = 0
        terminal_diagnostic = None
        with (output/"choices.jsonl").open("x") as ledger:
            for index in range(maximum):
                if p.env.terminated or p.env.truncated:
                    break
                decision_count += 1
                before = p.env.execution_budget()["used_sim_steps"]
                if arm.startswith(("oracle", "model")) or arm == "call_vla":
                    request_started = time.perf_counter()
                    prefetched = async_choices.take(adapter, wait=True) if async_choices is not None else None
                    if prefetched is not None:
                        request, decision = prefetched
                    elif startup:
                        profiler = cProfile.Profile()
                        request = profiler.runcall(adapter.request, k=1 if arm == "oracle_k1" else 4)
                        profiler.dump_stats(str(output/"request_profile.pstats"))
                    else:
                        request = adapter.request(k=1 if arm == "oracle_k1" else 4)
                    request_s = time.perf_counter()-request_started
                    if prefetched is None:
                        try:
                            decision = choose(request) if arm.startswith("model") else policy.choose(request)
                        except NoPublicOption as exc:
                            terminal_diagnostic = str(exc)
                            ledger.write(json.dumps({"index": index, "event": "no_remaining_public_option",
                                "request": request, "error": str(exc), "sim_steps": before})+"\n")
                            ledger.flush()
                            break
                    if arm == "call_vla":
                        fallback = next(c for c in request["candidates"] if c["skill"] == "call_vla")
                        decision["candidate_ids"] = [fallback["id"]]
                    receipts = adapter.execute(request, decision, async_decisions=async_choices)
                    row = {"request": request, "decision": decision, "receipts": receipts, "request_generation_s": request_s,
                           "candidate_screen_diagnostics": adapter.candidate_diagnostics,
                           "prefetched_decision": prefetched is not None,
                           "async_events": async_choices.events[-1:] if async_choices is not None else [],
                           "execution_details": adapter.details[-max(1, len(receipts)):]}
                    for receipt in receipts:
                        skill_steps[receipt["skill"]] += receipt["steps_used"]
                    if adapter.receipts and adapter.receipts[-1]["skill"] == "finish" and p.env.terminated:
                        break
                elif arm == "pi05_only":
                    traces = []
                    # Whole official instruction is confined to this control
                    # arm, never exposed as a bounded skill candidate.
                    p._vlm_chunk(instruction, trace_callback=traces.append)
                    row = {"skill": "pi05_full_instruction_control", "trace": traces}
                    skill_steps["pi05_only"] += p.env.execution_budget()["used_sim_steps"]-before
                else:
                    entities = list(scene.entities.values())
                    macros = subtask_candidates(entities, instruction, tuple(p._last_obs_eef_pos), executor.held,
                                               view_axes=scene.view_axes)
                    choices = candidates(entities, instruction, tuple(p._last_obs_eef_pos), executor.held,
                        executor.receipts, random.Random(ep["seed"]+index), persist_attempts=True,
                        vla_subtasks=macros, use_cached_measurements=True, gripper_opening=float(p._last_obs_gripper))
                    action = policy.choose(entities, choices, executor.held, executor.receipts, instruction, scene.view_axes)
                    receipt = executor.execute(action)
                    row = {"action": action.text(), "receipt": receipt}
                    skill_steps[action.tool] += p.env.execution_budget()["used_sim_steps"]-before
                row.update(index=index, sim_steps_before=before, sim_steps_after=p.env.execution_budget()["used_sim_steps"])
                ledger.write(json.dumps(row, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x))+"\n")
                ledger.flush()
                records.append(row)
                if p.env.execution_budget()["used_sim_steps"] > before:
                    write(output/"first_physical_request.json", {"arm": arm, "index": index,
                        "sim_steps": p.env.execution_budget()["used_sim_steps"], "source": "public_execution_budget"})
                    if startup:
                        break
        truth = rpc.call("oracle.status")
        if adapter and not arm.startswith("model"):
            write(output/"private_oracle_trace.json", policy.private_trace)
        write(output/"private_task_result.json", truth)
        summary = {"case": case, "arm": arm, "success": bool(p.env.terminated or truth["done"]),
            "decisions": decision_count, "sim_steps": p.env.execution_budget()["used_sim_steps"],
            "skill_sim_steps": dict(skill_steps), "wall_s": time.perf_counter()-started,
            "failure_phase": None, "source": "official_original_task_predicates_private",
            "status": "startup_physical" if startup else "physical_result", "training": False,
            "pi05_calls": 0 if arm.startswith(("oracle", "model")) else decision_count if arm == "pi05_only" else None,
            "fusion_version": "rgbd_dual_view/1", "k": 1 if arm == "oracle_k1" else 4 if arm == "oracle_k4" else None}
        summary["terminal_diagnostic"] = terminal_diagnostic
        if not startup and not summary["success"] and adapter:
            failures = [r["phase"] for r in adapter.receipts if r["phase"]]
            summary["failure_phase"] = Counter(failures).most_common(1)[0][0] if failures else "contact_failure"
            if terminal_diagnostic and not failures:
                summary["failure_phase"] = "planning_unreachable"
        if startup and not (output/"first_physical_request.json").exists():
            raise RuntimeError("startup reached no physical request")
        write(output/"summary.json", summary)
        return summary
    except Exception:
        if adapter is not None:
            write(output/"partial_execution.json", {"details": adapter.details,
                "vla_trace": getattr(adapter, "vla_trace", []), "receipts": adapter.receipts})
        raise
    finally:
        if async_choices is not None:
            async_choices.close()
        if toolkit is not None:
            toolkit.close()
        facade.close()


def legacy_episode(case, endpoints, output, config, source, *, allow_original90_adapter=False):
    """Keep the historical control in its own import namespace/process."""
    output.mkdir(parents=True, exist_ok=False)
    payload = {"case": case, "budget": config, "source": str(source), "output": str(output),
        "allow_original90_adapter": allow_original90_adapter,
        "choice_package": "/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a",
        "sam3_endpoint": endpoints["sam3"]._base_url, "vla_endpoint": endpoints["vla"]._base_url}
    write(output/"legacy_payload.json", payload)
    environment = {**os.environ, "PYTHONPATH": str(source)}
    infrastructure_attempts = []
    for attempt in range(2):
        trial_output = output if attempt == 0 else output/"infrastructure_retry1"
        if attempt:
            trial_output.mkdir()
            write(trial_output/"legacy_payload.json", {**payload, "output": str(trial_output)})
        with (trial_output/"legacy_worker.log").open("x") as log:
            proc = subprocess.run([os.sys.executable, str(Path(__file__).with_name("probe_bounded_legacy_worker.py")),
                "--payload", str(trial_output/"legacy_payload.json")], cwd=source, env=environment, stdout=log,
                stderr=subprocess.STDOUT, check=False)
        if not proc.returncode:
            data = json.loads((trial_output/"legacy_result.json").read_text())
            break
        saved = trial_output/"legacy/result.json"
        raw = json.loads(saved.read_text()) if saved.is_file() else {}
        if not raw.get("infrastructure_failure") or attempt:
            raise subprocess.CalledProcessError(proc.returncode, proc.args)
        infrastructure_attempts.append({"attempt": attempt, "status": "infrastructure_failure",
            "error": raw.get("error"), "raw_result": str(saved), "physical_decisions": raw.get("decisions", 0)})
        write(output/"infrastructure_attempts.json", infrastructure_attempts)
    result = data["legacy_result"]
    adapted = case.get("episode", {}).get("suite") == "libero_90"
    row = {"case": case, "arm": "v5_expert_original90_adapter" if adapted else "v5_expert", "success": bool(result["official_success"]),
        "status": "physical_result", "decisions": result.get("decisions"),
        "wall_s": result.get("wall_s"), "sim_steps": data.get("public_execution_budget", {}).get("used_sim_steps"),
        "failure_phase": result.get("termination_category"), "legacy_source": str(source),
        "legacy_error": result.get("error"),
        "infrastructure_attempts": infrastructure_attempts,
        "original90_diagnostic_admission_adapter": adapted,
        "source_files": data["source_files"], "training": False}
    write(output/"summary.json", row)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-plan", type=Path)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--legacy-source", type=Path)
    parser.add_argument("--arms", default="oracle_k1,oracle_k4,v5_expert,pi05_only")
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--startup", action="store_true")
    parser.add_argument("--resume-ledger", type=Path, action="append", default=[])
    parser.add_argument("--choice-endpoint")
    parser.add_argument("--decision-latency-s", type=float, default=.9853)
    parser.add_argument("--preparation-latency-s", type=float, default=0.)
    parser.add_argument("--legacy-original90-adapter", action="store_true")
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("LIBERO_TYPE=standard required; PRO inputs are not permitted")
    if args.build_plan:
        build_plan(args.build_plan.resolve(), args.count)
        return
    if args.manifest is None or args.output is None:
        parser.error("manifest and output are required")
    manifest = args.manifest.resolve(strict=True)
    plan = json.loads(manifest.read_text())
    cases = plan["cases"][args.shard::args.shards]
    if args.startup:
        cases = cases[:1]
    if not cases:
        raise ValueError("empty shard")
    for case in cases:
        if case["episode"]["suite"] not in ORIGINAL_SUITES:
            raise ValueError("only original tasks permitted")
        path = Path(case["bddl"]["path"])
        if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest() != case["bddl"]["sha256"]:
            raise ValueError("registered original BDDL identity changed")
    from scripts.v5_probe_preflight import validate_registered_states
    validate_registered_states(cases)
    exclusion_report = None
    if plan.get('permanent_exclusions'):
        from scripts.bounded_state_exclusions import check_exclusions
        exclusion_report = check_exclusions(cases, plan['permanent_exclusions'])
    config = json.loads(args.config.resolve(strict=True).read_text()) if args.config else {}
    config = config.get("budget", config)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    if exclusion_report is not None:
        write(args.output/'state_exclusion_check.json', exclusion_report)
    arms = args.arms.split(",")
    if any(arm.startswith("model") for arm in arms) and not args.choice_endpoint:
        parser.error("model arms require an explicit bounded-choice endpoint")
    completed = {(row["case"]["name"], "v5_expert" if row["arm"] == "v5_expert_original90_adapter" else row["arm"])
                 for path in args.resume_ledger for line in path.read_text().splitlines()
                 if (row := json.loads(line)).get("status") == "physical_result"}
    if "v5_expert" in arms and (args.config is None or args.legacy_source is None):
        raise ValueError("v5_expert requires the exact historical config and source")
    with services(args.output, vla=any(arm in {"v5_expert", "pi05_only", "call_vla"} for arm in arms)) as endpoints:
        with (args.output/"episodes.jsonl").open("x") as ledger:
            for case in cases:
                for arm in arms:
                    if (case["name"], arm) in completed:
                        continue
                    try:
                        output = args.output/(case["name"]+"_"+arm)
                        if arm == "v5_expert":
                            result = legacy_episode(case, endpoints, output, config, args.legacy_source.resolve(strict=True),
                                allow_original90_adapter=args.legacy_original90_adapter)
                        else:
                            result = episode(case, arm, endpoints, output, config, startup=args.startup,
                                choice_endpoint=args.choice_endpoint, decision_latency_s=args.decision_latency_s,
                                preparation_latency_s=args.preparation_latency_s)
                    except Exception as exc:
                        result = {"case": case, "arm": arm, "status": "startup_error" if args.startup else "execution_error",
                                  "error": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc(), "training": False}
                        ledger.write(json.dumps(result)+"\n");ledger.flush()
                        raise
                    ledger.write(json.dumps(result)+"\n");ledger.flush()


if __name__ == "__main__":
    main()
