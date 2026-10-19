# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Evaluate private same-state self/VLA branches on the existing forty D2 cases.

This is an oracle diagnostic, not a model evaluation or training producer.
All raw branch failures, unknown labels and uncovered task rules are retained.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pickle
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from robots.libero.bounded_hybrid_diagnostic import (
    SPLIT_VERSION,
    capture_runtime,
    choose_branch,
    d2_session,
    restore_runtime,
    snapshot_digest,
    split_subtasks,
    validate_d2_episode,
)
from scripts.probe_bounded_feasibility import (
    BOUNDED_SCENE_FLAGS,
    public_vocabulary,
    services,
)
from scripts.probe_bounded_motion import LocalRPC, write


def reference(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load_public_gripper_calibration(calibration_ref):
    """Load the pinned robot sensor calibration, never scene truth."""
    from harness_v5_eval import load_grasp_measurement_calibration

    if reference(calibration_ref['path']) != calibration_ref:
        raise ValueError('registered public gripper calibration changed')
    calibration, _ = load_grasp_measurement_calibration(calibration_ref['path'])
    return calibration


def make_executor(toolkit, scene, case):
    """Keep the diagnostic's verifier on the registered robot calibration."""
    from robots.libero.v5_runtime import V5Executor

    calibration = load_public_gripper_calibration(case['grasp_measurement_calibration'])
    return V5Executor(toolkit, scene, 40, grasp_measurement_calibration=calibration)


def build_plan(output, calibration_ref):
    """Pin D2 BDDL/init bytes before observing policy outcomes."""
    from libero.libero import get_libero_path
    from rlinf.envs.libero.utils import benchmark

    source = Path(__file__).resolve().parents[1] / "configs/d2_development_40.json"
    registered = json.loads(source.read_text())["episodes"]
    if len(registered) != 40 or len({tuple(e.values()) for e in registered}) != 40:
        raise ValueError("D2 registration must contain forty distinct cases")
    cases = []
    for ep in registered:
        validate_d2_episode(ep)
        suite = benchmark.get_benchmark(ep["suite"])()
        task = suite.get_task(ep["task"])
        bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
        state = np.asarray(suite.get_task_init_states(ep["task"])[ep["seed"]], dtype="<f8")
        cases.append({"name": f"{ep['suite']}_t{ep['task']}_s{ep['seed']}", "episode": ep,
            "grasp_measurement_calibration": calibration_ref,
            "bddl": reference(bddl), "state_sha256": hashlib.sha256(state.tobytes()).hexdigest()})
    plan = {"version": "D2-private-hybrid/1", "registration": reference(source),
        "cases": cases, "source_commit": os.environ.get("SOURCE_COMMIT"),
        "subtask_split": SPLIT_VERSION, "budget": {"sim_steps": 10000, "decisions": 160},
        "vla_trials": 3, "trial_seed_base": 10400000,
        "selection": "higher observed success rate; self on ties; incomplete stays unknown",
        "continuation": "first successful branch in fixed self,VLA0,VLA1,VLA2 order; optimistic envelope only",
        "replay": "one independent full episode following chosen methods; seed base +1000000000",
        "targets_not_gates": {"task_success_percent": 92, "choice_accuracy_percent": 99},
        "scope": "PRO D2 development only; no PRO test targets or training",
        "training": False, "confirmation": False, "model_visible_private_labels": False}
    write(output, plan)
    return plan


@contextmanager
def runtime(case, endpoints, output, *, domain='d2'):
    """Use the same public adapter/perception as the original feasibility arm."""
    import robosuite

    from robots.libero import tools
    from robots.libero.bounded_oracle import BoundedOracle
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from robots.libero.bounded_timing import EpisodeTimings, install_episode_timers
    from robots.libero.toolkit import LiberoToolkit
    from robots.libero.v5_runtime import MeasuredScene
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.memory import MemoryManager
    from rpent.robots.components.pi05_vla_client import Pi05VLAClient
    from rpent.robots.components.sam3_client import Sam3Client

    if domain == 'd2':
        facade, primitives = d2_session(case["episode"])
    elif domain == 'original':
        from scripts.probe_bounded_motion import original_session
        ep = case['episode']
        facade, primitives = original_session(ep['suite'], ep['task'], ep['seed'],
            10000, rgbd_no_msaa_v1=True)
    else:
        raise ValueError('unsupported diagnostic domain')
    toolkit = None
    timings = EpisodeTimings()
    try:
        model = Pi05VLAClient(endpoints["vla"], embodiment="libero")
        toolkit = LiberoToolkit(runtime_kwargs={"env": primitives.env, "model": model,
            "sam3_client": Sam3Client(endpoints["sam3"])}, dashboard_events=NullDashboardEventSink(),
            memory=MemoryManager(output / "empty_memory", memory_access="read_only"), state_output_dir=output)
        scene = MeasuredScene(toolkit, endpoints["sam3"], case["episode"]["seed"],
            dual_view_fusion_v1=True, furniture_parts_v1=True, instruction_queries_v1=True,
            wrist_recall_v1=True, occluded_measurement_cache_v2=True, **BOUNDED_SCENE_FLAGS)
        executor = make_executor(toolkit, scene, case)
        write(output/'public_gripper_calibration.json', {
            'reference': case['grasp_measurement_calibration'],
            'opening_calibration': executor.grasp_measurement_calibration['opening_calibration'],
            'source': 'original_empty_gripper_proprioception', 'model_visible': False})
        install_episode_timers(timings, tools=tools, env=executor.p.env,
                               toolkit=toolkit, scene=scene, model=model)
        instruction = toolkit.execute_tool("view_env_state", {}).result["task_language"]
        executor.instruction = scene.instruction = instruction
        scene.refresh(public_vocabulary(instruction))
        xml = Path(robosuite.__file__).parent / "models/assets/grippers/panda_gripper.xml"
        adapter = MeasuredSkillAdapter(executor, xml, allow_vla=True,
            record_public_geometry=True, precontact_instance_surface_v1=True)
        policy = BoundedOracle(LocalRPC(facade), adapter)
        yield facade, adapter, policy, timings
    finally:
        timings.close()
        if toolkit is not None:
            toolkit.close()
        facade.close()


def save_checkpoint(facade, adapter, policy, path, request=None):
    saved = {"physics": facade.snapshot(), "public_runtime": capture_runtime(adapter, policy),
             "private_native_success_events": copy.deepcopy(facade._native_success_events),
             "client_stop_flags": {"terminated": adapter.p.env.terminated,
                                   "truncated": adapter.p.env.truncated},
             "request": request, "model_visible": False, "training": False}
    path.write_bytes(pickle.dumps(saved, protocol=5))
    return saved, {**reference(path), "physics_sha256": snapshot_digest(saved["physics"])}


def restore_checkpoint(facade, adapter, policy, saved):
    # The facade can truncate history to a prefix, but a count cannot restore
    # an endpoint after sibling branches removed or replaced those events.
    facade._native_success_events = copy.deepcopy(saved["private_native_success_events"])
    observed = facade.restore(saved["physics"])
    adapter.p.env.last_obs = observed
    adapter.p.env.terminated = saved["client_stop_flags"]["terminated"]
    adapter.p.env.truncated = saved["client_stop_flags"]["truncated"]
    adapter.p.set_obs(observed)
    restore_runtime(adapter, policy, saved["public_runtime"])
    actual = facade.snapshot()
    legacy_observation = ('actuator_state' in saved['physics']
        and 'observation_state' not in saved['physics']['actuator_state'])
    comparable = ({**actual, 'actuator_state': {k:v for k,v in actual['actuator_state'].items()
        if k != 'observation_state'}} if legacy_observation else actual)
    if snapshot_digest(comparable) != snapshot_digest(saved["physics"]):
        raise RuntimeError("fork did not restore full physics/controller/RNG/counter identity")
    adapter._branch_observation_restore = ('legacy_missing_phase_canonical_fresh'
        if legacy_observation else 'captured_sensor_phase_and_buffers_v1')


def bind_subtask(policy, adapter, spec):
    """Reuse original binding; no simulator coordinate becomes an anchor."""
    from robots.libero.v5_oracle_policy import goal_clause

    entities = list(adapter.scene.entities.values())
    phrase = goal_clause(adapter.ex.instruction, spec["source_symbol"])
    source = policy.binding.bind(spec["source_symbol"], entities, phrase, adapter.scene.view_axes)
    target = (policy.binding.bind(spec["target_symbol"], entities, phrase,
        adapter.scene.view_axes, source_reference=False) if spec["target_symbol"] else None)
    return source, target


class SubtaskRPC:
    """Select a registered existing goal, without adding new progress rules."""
    def __init__(self, facade, spec):
        self.facade, self.spec = facade, spec

    def call(self, method, *args, **kwargs):
        if method != "oracle.status":
            return LocalRPC(self.facade).call(method, *args, **kwargs)
        full = self.facade.goal_status()
        i = self.spec["goal_index"]
        return {**full, "goals": [full["goals"][i]], "satisfied": [full["satisfied"][i]],
                "done": full["satisfied"][i]}


class SeededPolicy:
    """Seed each owned-server inference; ordinary clients are untouched."""
    def __init__(self, client, seed, *, input_ledger=None):
        self.client, self.seed, self.calls = client, seed, 0
        self.inputs = []
        self.predictions = []
        self.input_ledger = input_ledger

    def predict(self, obs, options=None):
        options = {**(options or {}), "sampling_seed": self.seed + self.calls}
        encoded = self.client.encode_obs(obs)
        fields = {}
        for key, value in encoded.items():
            if isinstance(value, np.ndarray):
                array = np.ascontiguousarray(value)
                header = json.dumps({'dtype': array.dtype.str, 'shape': array.shape}, sort_keys=True).encode()
                fields[key] = hashlib.sha256(header+b'\0'+array.tobytes()).hexdigest()
            else:
                fields[key] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        self.inputs.append({'sampling_seed': options['sampling_seed'], 'fields': fields,
            'states': np.asarray(encoded['states']).tolist(),
            'wire_observation_sha256': hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()})
        if self.input_ledger is not None:
            with Path(self.input_ledger).open('a') as stream:
                stream.write(json.dumps(self.inputs[-1])+'\n')
        self.calls += 1
        value = self.client.predict(obs, options=options)
        actions = np.ascontiguousarray(value)
        self.predictions.append({'sampling_seed': options['sampling_seed'],
            'actions_sha256': hashlib.sha256(actions.tobytes()).hexdigest(),
            'shape': list(actions.shape), 'first_action': actions[0].tolist()})
        if self.input_ledger is not None:
            with Path(self.input_ledger).with_name('vla_predictions.jsonl').open('a') as stream:
                stream.write(json.dumps(self.predictions[-1])+'\n')
        return value


def trial(facade, adapter, policy, timings, spec, method, seed, output, first_request, *, decision_limit=160):
    """Execute one branch, preserving its private endpoint before metrology."""
    from robots.libero.bounded_oracle import NoPublicOption
    from rpent.skill_package.contract import legal_after

    output.mkdir()
    before = adapter.p.env.execution_budget()["used_sim_steps"]
    started = time.perf_counter()
    source, target = bind_subtask(policy, adapter, spec)
    initial = facade.snapshot()
    legacy_physics = (dict(initial, actuator_state={k:v for k,v in initial['actuator_state'].items()
        if k != 'observation_state'}) if 'actuator_state' in initial else initial)
    result = {"subtask": spec, "method": method, "trial_seed": seed,
        "initial_physics_sha256": snapshot_digest(initial), "prefix": [],
        "initial_legacy_captured_physics_sha256": snapshot_digest(legacy_physics),
        "observation_restore": getattr(adapter, '_branch_observation_restore', 'not_restored'),
        "request_sha256": hashlib.sha256(json.dumps(first_request, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest(),
        "legal": list(legal_after(first_request, [])), "selected_candidate_id": None,
        "source_public_id": source.id if source else None,
        "target_public_id": target.id if target else None, "success": None,
        "status": "physical_result", "model_visible": False, "training": False,
        "binding_recovery": []}
    original_rpc, original_model = policy.rpc, adapter.p.model
    policy.rpc = SubtaskRPC(facade, spec)
    seeded = SeededPolicy(original_model, seed, input_ledger=output/'vla_inputs.jsonl')
    if method == "call_vla":
        adapter.p.model = seeded
    reference_grasp = facade.grasp_reference(spec["source_symbol"]) if spec["mode"] == "pick" else None
    reason, decisions, endpoint = "decision_limit", 0, None
    try:
        with (output / "choices.jsonl").open("x") as ledger:
            for index in range(decision_limit):
                if adapter.p.env.terminated or adapter.p.env.truncated:
                    reason = "native_stop"
                    break
                if index == 0:
                    request = copy.deepcopy(first_request)
                else:
                    with timings.measure("planning.request"):
                        request = adapter.request(k=4)
                    source, target = bind_subtask(policy, adapter, spec)
                decisions += 1
                recovering_binding = source is None or (spec["target_symbol"] and target is None)
                if recovering_binding:
                    # Missing/ambiguous public identity is not permission to
                    # choose a private instance. Give both arms the existing
                    # screened observation recovery before declaring it absent.
                    reason = "source_binding_missing" if source is None else "target_binding_missing"
                    legal = set(legal_after(request, []))
                    option = next((c for mode in ("wrist_scan", "refresh")
                        for c in request["candidates"] if c["id"] in legal
                        and c["skill"] == "observe" and c["parameters"]["mode"] == mode), None)
                    if option is None:
                        break
                    decision = {key: request[key] for key in ("schema_version", "observation_id", "revision")}
                    decision.update(kind="decision", candidate_ids=[option["id"]])
                    result["binding_recovery"].append({"decision": index, "reason": reason,
                        "candidate_id": option["id"], "mode": option["parameters"]["mode"]})
                elif method == "call_vla":
                    parameters = {"anchor_id": source.id, "mode": spec["mode"]}
                    if target is not None:
                        parameters["target_id"] = target.id
                    option = next((c for c in request["candidates"] if c["skill"] == "call_vla"
                                   and c["parameters"] == parameters), None)
                    if option is None:
                        reason = "matching_call_vla_candidate_unavailable"
                        break
                    decision = {key: request[key] for key in ("schema_version", "observation_id", "revision")}
                    decision.update(kind="decision", candidate_ids=[option["id"]])
                else:
                    try:
                        with timings.measure("decision.oracle"):
                            decision = policy.choose(request)
                    except NoPublicOption:
                        reason = "no_public_option"
                        break
                    # A pick subtask ends at measured lift, before a transfer.
                    if spec["mode"] == "pick":
                        by_id = {c["id"]: c for c in request["candidates"]}
                        ids = decision["candidate_ids"]
                        stop = next((j + 1 for j, cid in enumerate(ids) if by_id[cid]["skill"] == "lift"), len(ids))
                        decision["candidate_ids"] = ids[:stop]
                detail_start = len(adapter.details)
                if not recovering_binding and result["selected_candidate_id"] is None:
                    result["selected_candidate_id"] = decision["candidate_ids"][0]
                    result["source_public_id"] = source.id
                    result["target_public_id"] = target.id if target else None
                with timings.measure("execution.other"):
                    receipts = adapter.execute(request, decision)
                record = {"index": index, "request": request, "decision": decision, "receipts": receipts,
                    "chunk_execution": adapter.last_chunk, "execution_details": adapter.details[detail_start:]}
                ledger.write(json.dumps(record, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x)) + "\n")
                ledger.flush()
                completed = (source is not None and adapter.held == source.id if spec["mode"] == "pick"
                             else facade.goal_status()["satisfied"][spec["goal_index"]])
                if completed or (method == "call_vla" and not recovering_binding):
                    reason = receipts[-1]["stop_reason"] if method == "call_vla" and receipts else "subtask_completed"
                    break
        endpoint, endpoint_ref = save_checkpoint(facade, adapter, policy, output / "private_endpoint.pkl")
        metrology_started = time.perf_counter()
        if reference_grasp is not None:
            # Private diagnostic integration is outside the executed branch's
            # budget and endpoint, and never supplies its public stop rule.
            truth = facade.measure_grasp_hold(spec["source_symbol"], reference_grasp)
            success = truth["truth_v3"]["success"]
            result["truth_source"] = "private_sustained_grasp_v3_post_branch_window"
        else:
            truth = facade.goal_status()
            success = truth["satisfied"][spec["goal_index"]]
            result["truth_source"] = "unchanged_registered_task_predicate"
        write(output / "private_truth.json", truth)
        result.update(success=success, endpoint=endpoint_ref,
            private_metrology_s=time.perf_counter() - metrology_started,
            evidence=reference(output / "private_truth.json"),
            choices=reference(output / "choices.jsonl"))
    finally:
        policy.rpc, adapter.p.model = original_rpc, original_model
    # Metrology has stepped physics; costs come from the saved branch endpoint.
    used = int(np.asarray(endpoint["physics"]["counters"]["_elapsed_steps"]).item()) - before
    result.update(reason=reason, wall_s=time.perf_counter() - started, sim_steps=used,
                  decisions=decisions, vla_inference_calls=seeded.calls, vla_inputs=seeded.inputs,
                  vla_predictions=seeded.predictions)
    write(output / "summary.json", result)
    return result, endpoint


def evaluate_case(case, endpoints, output, plan, *, startup=False):
    output.mkdir()
    with runtime(case, endpoints, output) as (facade, adapter, policy, timings):
        initial, initial_ref = save_checkpoint(facade, adapter, policy, output / "private_initial.pkl")
        status = facade.goal_status()
        subtasks, unsupported = split_subtasks(status["goals"], adapter.ex.instruction)
        write(output / "private_subtask_plan.json", {"version": SPLIT_VERSION,
            "subtasks": subtasks, "unsupported": unsupported, "initial": initial_ref})
        if unsupported:
            result = {"case": case, "status": "oracle_rule_uncovered", "success": None,
                      "unsupported": unsupported, "training": False}
            write(output / "summary.json", result)
            return result
        chosen, rows, envelope_rate, decisions_used = [], [], 1., 0
        for index, spec in enumerate(subtasks):
            if facade.goal_status()["satisfied"][spec["goal_index"]]:
                continue
            directory = output / (f"subtask{index:02d}_" + spec["mode"])
            directory.mkdir()
            with timings.measure("planning.request"):
                request = adapter.request(k=4)
            branchpoint, branch_ref = save_checkpoint(facade, adapter, policy,
                directory / "private_branchpoint.pkl", request)
            from robots.libero.bounded_offline_labels import (
                capture_annotation_state,
                save_annotation_state,
            )
            annotation = save_annotation_state(directory / "private_annotation.pkl", capture_annotation_state(policy, request))
            trials, endpoints_saved = [], []
            # Startup proves the VLA service/control path directly; it must
            # not spend a full oracle branch's budget before its first call.
            methods = ("call_vla",) if startup else ("self", "call_vla", "call_vla", "call_vla")
            for j, method in enumerate(methods):
                restore_checkpoint(facade, adapter, policy, branchpoint)
                seed = plan["trial_seed_base"] + 1000000 * plan["cases"].index(case) + 10000 * index + 1000 * j
                row, endpoint = trial(facade, adapter, policy, timings, spec, method, seed,
                    directory / f"{method}_{j}", request, decision_limit=160 - decisions_used)
                row.update(branchpoint=branch_ref, offline_annotation_state=annotation,
                           prefix_identity={"candidate_ids": [], "request_sha256": row["request_sha256"]})
                trials.append(row)
                endpoints_saved.append(endpoint)
                if startup and row["sim_steps"] > 0 and row["vla_inference_calls"] > 0:
                    write(output / "first_physical_vla_request.json", row)
                    result = {"case": case, "status": "startup_physical", "trials": trials,
                              "training": False, "source_commit": plan["source_commit"]}
                    write(output / "summary.json", result)
                    return result
            if startup:
                result = {"case": case, "status": "startup_no_vla_physics", "trials": trials,
                          "training": False, "source_commit": plan["source_commit"]}
                write(output / "summary.json", result)
                return result
            selection = choose_branch(trials[0]["success"], [row["success"] for row in trials[1:]])
            row = {"subtask": spec, "trials": trials, "selection": selection}
            rows.append(row)
            write(directory / "paired.json", row)
            if selection["method"] is None or selection["status"] == "both_failed":
                envelope_rate = 0. if selection["status"] == "both_failed" else None
                break
            envelope_rate *= selection["rate"]
            candidates = [0] if selection["method"] == "self" else [1, 2, 3]
            continuation = next(i for i in candidates if trials[i]["success"])
            chosen.append({"subtask": spec, "method": selection["method"]})
            decisions_used += trials[continuation]["decisions"]
            restore_checkpoint(facade, adapter, policy, endpoints_saved[continuation])
        envelope_done = facade.goal_status()["done"]
        # Independently execute the selected method sequence from the original
        # full state, never splice saved successful endpoints into this replay.
        restore_checkpoint(facade, adapter, policy, initial)
        replay, replay_decisions = [], 0
        if len(chosen) == len([row for row in rows if row["selection"]["status"] == "measured"]):
            for index, choice in enumerate(chosen):
                with timings.measure("planning.request"):
                    request = adapter.request(k=4)
                seed = plan["trial_seed_base"] + 1000000000 + 1000000 * plan["cases"].index(case) + 10000 * index
                row, endpoint = trial(facade, adapter, policy, timings, choice["subtask"],
                    choice["method"], seed, output / f"full_replay_{index:02d}", request,
                    decision_limit=160 - replay_decisions)
                replay.append(row)
                replay_decisions += row["decisions"]
                restore_checkpoint(facade, adapter, policy, endpoint)
                if not row["success"]:
                    break
        result = {"case": case, "status": "physical_result", "subtasks": rows,
            "sampled_envelope_native_success": envelope_done,
            "conditional_rate_product": envelope_rate,
            "actual_full_replay_success": facade.goal_status()["done"], "full_replay": replay,
            "wall_time_breakdown": timings.summary(time.perf_counter() - timings.started),
            "training": False, "confirmation": False, "source_commit": plan["source_commit"]}
        write(output / "summary.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-plan", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--startup", action="store_true")
    parser.add_argument("--grasp-calibration", type=Path)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "pro":
        parser.error("LIBERO_TYPE=pro is required for this isolated D2 diagnostic")
    if args.build_plan:
        if args.grasp_calibration is None:
            parser.error('--grasp-calibration is required to build a calibrated diagnostic plan')
        calibration_ref = reference(args.grasp_calibration)
        load_public_gripper_calibration(calibration_ref)
        build_plan(args.build_plan.resolve(), calibration_ref)
        return
    plan = json.loads(args.manifest.resolve(strict=True).read_text())
    if plan["training"] or plan["confirmation"] or len(plan["cases"]) != 40:
        raise ValueError("only the isolated forty-case D2 evaluation plan is admitted")
    for case in plan["cases"]:
        validate_d2_episode(case["episode"])
        if reference(case["bddl"]["path"]) != case["bddl"]:
            raise ValueError("registered D2 BDDL changed")
    from scripts.v5_probe_preflight import validate_registered_states
    validate_registered_states(plan["cases"])
    case = plan["cases"][args.index]
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    write(args.output / "scope.json", {"manifest": reference(args.manifest),
        "domain": "libero_pro_D2_development_evaluation_only", "training": False})
    with services(args.output, vla=True) as endpoints:
        result = evaluate_case(case, endpoints, args.output / case["name"], plan, startup=args.startup)
    write(args.output / "summary.json", result)
    if args.startup and result["status"] != "startup_physical":
        raise RuntimeError("startup produced no actual pi0.5 physical request")


if __name__ == "__main__":
    main()
