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
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from robots.libero.bounded_hybrid_diagnostic import (
    PROGRESS_VERSION,
    SPLIT_VERSION,
    capture_runtime,
    choose_branch,
    d2_session,
    restore_runtime,
    snapshot_digest,
    split_subtasks,
    trial_progress_success,
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
def runtime(case, endpoints, output, *, domain='d2', artifact_compression_level=1,
            record_public_geometry=False, constructed_start=None):
    """Use the same public adapter/perception as the original feasibility arm."""
    if constructed_start is not None and domain != 'original':
        raise ValueError('own training-layout construction cannot materialize in PRO/D2')
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
        world = ({'constructed_start': constructed_start}
            if constructed_start is not None and constructed_start.get('authored_world') else {})
        facade, primitives = original_session(ep['suite'], ep['task'], ep['seed'],
            10000, rgbd_no_msaa_v1=True, **world)
    else:
        raise ValueError('unsupported diagnostic domain')
    toolkit = None
    timings = EpisodeTimings()
    try:
        if constructed_start is not None:
            from robots.libero.bounded_generated_start import materialize_original_layout
            audit = materialize_original_layout(facade, primitives, constructed_start,
                bddl_sha256=case['bddl']['sha256'])
            write(output/'private_layout_materialization.json', audit)
        model = Pi05VLAClient(endpoints["vla"], embodiment="libero")
        toolkit = LiberoToolkit(runtime_kwargs={"env": primitives.env, "model": model,
            "sam3_client": Sam3Client(endpoints["sam3"])}, dashboard_events=NullDashboardEventSink(),
            memory=MemoryManager(output / "empty_memory", memory_access="read_only"), state_output_dir=output,
            artifact_compression_level=artifact_compression_level)
        from robots.libero.bounded_artifacts import AsyncEnvState
        AsyncEnvState.enable(toolkit._state)
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
            record_public_geometry=record_public_geometry, precontact_instance_surface_v1=True)
        policy = BoundedOracle(LocalRPC(facade), adapter)
        yield facade, adapter, policy, timings
    finally:
        timings.close()
        if toolkit is not None:
            if hasattr(toolkit._state,'close'):
                toolkit._state.close()
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
    from robots.libero.bounded_success_loop import restore_feedback
    restore_feedback(adapter, facade, saved['public_runtime'])
    actual = facade.snapshot()
    legacy_observation = ('actuator_state' in saved['physics']
        and 'observation_state' not in saved['physics']['actuator_state'])
    complete_integration = saved['physics'].get('actuator_state',{}).get('integration') is not None
    native_data = saved['physics'].get('actuator_state',{}).get('native_data') is not None
    if not complete_integration or not native_data:
        from robots.libero.v5_branch_state import captured_projection
        comparable = captured_projection(actual,saved['physics'])
    else:
        comparable = actual
    if snapshot_digest(comparable) != snapshot_digest(saved["physics"]):
        raise RuntimeError("fork did not restore full physics/controller/RNG/counter identity")
    adapter._branch_observation_restore = ('legacy_missing_phase_canonical_fresh'
        if legacy_observation else 'captured_sensor_phase_and_buffers_v1')
    adapter._branch_complete_integration_available = complete_integration
    adapter._branch_native_derived_available = native_data


def bind_subtask(policy, adapter, spec):
    """Reuse original binding; no simulator coordinate becomes an anchor."""
    from robots.libero.v5_oracle_policy import goal_clause

    entities = list(adapter.scene.entities.values())
    phrase = goal_clause(adapter.ex.instruction, spec["source_symbol"])
    source = policy.binding.bind(spec["source_symbol"], entities, phrase, adapter.scene.view_axes)
    target = (policy.binding.bind(spec["target_symbol"], entities, phrase,
        adapter.scene.view_axes, source_reference=False) if spec["target_symbol"] else None)
    # This diagnostic calls bind() directly, bypassing the ordinary selector's
    # identity bookkeeping. Retain its publicly resolved IDs before VLA contact
    # changes visibility. Otherwise a cached peer becomes an apparent new
    # ambiguity when the bounded selector admits cached anchors after handoff.
    for symbol, entity in ((spec['source_symbol'], source), (spec['target_symbol'], target)):
        if entity is not None:
            policy.binding._bindings[symbol] = entity.id
            policy.binding._binding_peers.setdefault(symbol, {
                e.id for e in entities if e.id != entity.id and e.name == entity.name})
    return source, target


def least_failed_vla_candidate(request, required):
    """Choose an eligible invocation with the least public failure history."""
    from rpent.skill_package.contract import legal_after

    legal = set(legal_after(request, []))
    return min((c for c in request['candidates'] if c['id'] in legal
        and c['skill'] == 'call_vla'
        and all(c['parameters'].get(key) == value for key, value in required.items())),
        key=lambda c: c.get('recent_failures', 0), default=None)


def unbound_vla_candidate(request, instruction, mode, *, preparation='in_place'):
    """Select an existing legal public clause/task call when identity is absent."""
    from robots.libero.bounded_vla_options import clause_for_mode
    phrase = clause_for_mode(instruction, mode)
    clauses = request.get('instruction_clauses', [])
    clause_id = clauses.index(phrase) if phrase in clauses else None
    for selected_preparation in dict.fromkeys((preparation, 'in_place')):
        clause = (least_failed_vla_candidate(request, {'mode': 'instruction',
            'clause_id': clause_id, 'preparation': selected_preparation})
            if clause_id is not None else None)
        selected = clause or least_failed_vla_candidate(request,
            {'mode': 'task', 'preparation': selected_preparation})
        if selected is not None:
            return selected
    return None


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
        options = dict(options or {})
        offset = options.pop('sampling_seed_offset',0)
        options['sampling_seed'] = self.seed+self.calls+offset
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


def consumes_recovery(receipt):
    """Charge failed actions, not an unchanged observation or unexecuted plan."""
    if receipt.get('outcome') == 'success':
        return False
    if receipt.get('steps_used') == 0 and receipt.get('phase') == 'planning_unreachable':
        return False
    if (receipt.get('steps_used') == 0
            and receipt.get('stop_reason') == 'predicted_anchor_changed'):
        # A predecessor invalidated the chunk's measured parameters. Request
        # a new decision; no attempted control or recovery was performed.
        return False
    return not (receipt.get('skill') == 'observe'
        and receipt.get('outcome') == 'no_effect'
        and receipt.get('stop_reason') == 'no_measured_scene_change')


def trial(facade, adapter, policy, timings, spec, method, seed, output, first_request, *,
          decision_limit=160, vla_parameters=None):
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
    whole_task = vla_parameters is not None and vla_parameters.get('mode') == 'task'
    reference_grasp = (grasp_trial_reference(facade, spec["source_symbol"])
        if spec["mode"] == "pick" and not whole_task else None)
    reason, decisions, endpoint = "decision_limit", 0, None
    recovery_budget = getattr(adapter, 'hybrid_recovery_budget', None)
    recovery_used = 0
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
                unbound = None
                forced = None
                if method == 'call_vla' and vla_parameters is not None:
                    required = dict(vla_parameters)
                    if required.get('mode') != 'task':
                        required['mode'] = spec['mode']
                        if source is not None:
                            required['anchor_id'] = source.id
                        if target is not None:
                            required['target_id'] = target.id
                    forced = (least_failed_vla_candidate(request, required)
                        if whole_task or not recovering_binding else None)
                    if forced is None:
                        unbound = unbound_vla_candidate(request, adapter.ex.instruction, spec['mode'],
                            preparation=required.get('preparation', 'in_place'))
                        if unbound is not None:
                            result.setdefault('vla_variant_fallbacks', []).append({
                                'decision': index, 'reason': ('public_binding_missing'
                                    if recovering_binding else 'requested_public_option_unavailable'),
                                'requested_parameters': dict(vla_parameters),
                                'actual_parameters': dict(unbound['parameters']),
                                'candidate_id': unbound['id']})
                            forced = unbound
                    if forced is None:
                        reason = 'requested_vla_variant_unavailable'
                        break
                    whole_task = forced['parameters']['mode'] == 'task'
                    if whole_task:
                        unbound = forced
                        recovering_binding = False
                elif recovering_binding and method=='call_vla':
                    unbound = unbound_vla_candidate(request, adapter.ex.instruction, spec['mode'])
                    whole_task = unbound is not None and unbound['parameters']['mode'] == 'task'
                    if whole_task:
                        recovering_binding = False
                if forced is not None:
                    decision = {key:request[key] for key in ('schema_version','observation_id','revision')}
                    decision.update(kind='decision', candidate_ids=[forced['id']])
                elif unbound is not None:
                    decision = {key:request[key] for key in ('schema_version','observation_id','revision')}
                    decision.update(kind='decision',candidate_ids=[unbound['id']])
                    result.setdefault('unbound_instruction_calls',[]).append(unbound['parameters'])
                elif recovering_binding:
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
                        and all(c['parameters'].get(k)==v for k,v in parameters.items())
                        and c['id'] in set(legal_after(request,[]))), None)
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
                if (not recovering_binding or unbound is not None) and result["selected_candidate_id"] is None:
                    result["selected_candidate_id"] = decision["candidate_ids"][0]
                    result["source_public_id"] = source.id if source else None
                    result["target_public_id"] = target.id if target else None
                if method == 'call_vla':
                    selected = next(c for c in request['candidates']
                        if c['id'] == decision['candidate_ids'][0])
                    if selected['skill'] == 'call_vla':
                        result.setdefault('executed_vla_variants', []).append({
                            'decision': index, 'candidate_id': selected['id'],
                            'parameters': dict(selected['parameters'])})
                with timings.measure("execution.other"):
                    receipts = adapter.execute(request, decision)
                record = {"index": index, "request": request, "decision": decision, "receipts": receipts,
                    "chunk_execution": adapter.last_chunk, "execution_details": adapter.details[detail_start:]}
                ledger.write(json.dumps(record, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x)) + "\n")
                ledger.flush()
                if getattr(adapter, 'schema6_v1', False) and any(
                        (r.get('skill') == 'finish' or r.get('skill') == 'ask_help'
                         and r.get('outcome') == 'rejected') for r in receipts):
                    reason = 'public_terminal_selection'
                    break
                private_status = facade.goal_status()
                goal_completed = private_status['satisfied'][spec['goal_index']]
                if goal_completed:
                    # A policy may finish placement while its temporary
                    # sustained-grasp milestone is no longer true. Continue
                    # from the registered task progress, preserving both labels.
                    reason = (receipts[-1]['stop_reason'] if method == 'call_vla' and receipts
                        else 'subtask_completed') if private_status['done'] else 'registered_goal_completed'
                    break
                completed = (source is not None and adapter.held == source.id
                    if spec['mode'] == 'pick' else goal_completed)
                failed = recovery_budget is not None and any(consumes_recovery(r) for r in receipts)
                retry_exhausted = False
                if failed and recovery_budget is not None:
                    retry_exhausted = recovery_used >= recovery_budget
                    if not retry_exhausted:
                        recovery_used += 1
                if retry_exhausted:
                    reason = 'failed_chunk_recovery_budget'
                    break
                if completed or (method == "call_vla" and not recovering_binding
                        and (recovery_budget is None or not failed)):
                    reason = receipts[-1]["stop_reason"] if method == "call_vla" and receipts else "subtask_completed"
                    break
        endpoint, endpoint_ref = save_checkpoint(facade, adapter, policy, output / "private_endpoint.pkl")
        endpoint_goals = facade.goal_status()
        result['native_task_success'] = bool(endpoint_goals['done'])
        result['private_goal_satisfied_at_endpoint'] = bool(endpoint_goals['satisfied'][spec['goal_index']])
        result['private_progress_contract'] = PROGRESS_VERSION
        result['native_completion_scope'] = 'saved_endpoint_before_private_metrology'
        metrology_started = time.perf_counter()
        if whole_task:
            truth = endpoint_goals
            success = bool(truth['done'])
            result['truth_source'] = 'unchanged_native_task_completion'
        elif reference_grasp is not None:
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
        result['private_progress_success'] = trial_progress_success(result)
    finally:
        policy.rpc, adapter.p.model = original_rpc, original_model
    # Metrology has stepped physics; costs come from the saved branch endpoint.
    used = int(np.asarray(endpoint["physics"]["counters"]["_elapsed_steps"]).item()) - before
    result.update(reason=reason, wall_s=time.perf_counter() - started, sim_steps=used,
                  decisions=decisions, vla_inference_calls=seeded.calls, vla_inputs=seeded.inputs,
                  vla_predictions=seeded.predictions, recovery_budget=recovery_budget,
                  recovery_used=recovery_used)
    write(output / "summary.json", result)
    return result, endpoint


def native_instruction_replay(facade, adapter, policy, timings, output, seed):
    """Physically replay uncovered instructions with the public full-task option.

    This does not supply missing private subtask rules or impute a sampled
    bound. Its outcome uses only the benchmark's native completion signal.
    """
    output.mkdir()
    original_model = adapter.p.model
    seeded = SeededPolicy(original_model, seed, input_ledger=output/'vla_inputs.jsonl')
    adapter.p.model = seeded
    started = time.perf_counter()
    steps, choices, reason = 0, [], 'call_budget'
    budget = 1+getattr(adapter,'hybrid_recovery_budget',0)
    try:
        for _ in range(budget):
            if adapter.p.env.terminated or adapter.p.env.truncated:
                reason = 'native_stop'
                break
            with timings.measure('planning.request'):
                request = adapter.request(k=4)
            option = least_failed_vla_candidate(request,
                {'mode': 'task', 'preparation': 'in_place'})
            if option is None:
                reason = 'full_instruction_option_unavailable'
                break
            decision = {k:request[k] for k in ('schema_version','observation_id','revision')}
            decision.update(kind='decision',candidate_ids=[option['id']])
            receipts = adapter.execute(request,decision)
            choices.append({'request':request,'decision':decision,'receipts':receipts})
            steps += sum(r['steps_used'] for r in receipts)
        native = facade.goal_status()
        result = {'method':'call_vla_full_instruction','success':bool(native['done']),
            'truth_source':'unchanged_native_task_completion','status':'physical_result',
            'sim_steps':steps,'decisions':len(choices),'reason':reason,
            'wall_s':time.perf_counter()-started,'vla_inference_calls':seeded.calls,
            'scope':'native-only replay; private subtask rules remain uncovered',
            'choices':choices,'training':False}
        write(output/'summary.json',result)
        if not steps and not native['done']:
            raise RuntimeError('native-only replay made no physical request: '+reason)
        return result
    finally:
        adapter.p.model = original_model


def choose_variant_branch(trials, variants):
    """Compare each three-seed invocation separately; never pool nine seeds."""
    if not variants or len(trials) != 1+3*len(variants):
        raise ValueError('one self trial and three trials per registered variant required')
    groups = [choose_branch(trial_progress_success(trials[0]),
        [trial_progress_success(row) for row in trials[1+3*i:4+3*i]]) for i in range(len(variants))]
    evidence = [{'variant': variant, **group,
        'selection_success_contract': PROGRESS_VERSION,
        'local_vla_success': sum(t['success'] is True for t in trials[1+3*i:4+3*i]),
        'local_vla_unknown': sum(t['success'] is None for t in trials[1+3*i:4+3*i]),
        'registered_goal_success': sum(t.get('private_goal_satisfied_at_endpoint') is True
            for t in trials[1+3*i:4+3*i])}
        for i, (variant, group) in enumerate(zip(variants, groups))]
    if any(group['method'] is None for group in groups):
        return {'method': None, 'status': 'incomplete_measurement', 'rate': None,
                'variant_groups': evidence}
    at = max(range(len(groups)), key=lambda i: groups[i]['rate'])
    result = dict(groups[at], variant_groups=evidence)
    result['trial_indices'] = [0] if result['method'] == 'self' else list(range(1+3*at, 4+3*at))
    if result['method'] == 'call_vla':
        result['vla_parameters'] = variants[at]['parameters']
        result['vla_variant'] = variants[at]['name']
    return result


def grasp_trial_reference(facade, symbol):
    """Keep current grasp pose while using the registered episode's support."""
    current = facade.grasp_reference(symbol)
    origin = getattr(facade, '_episode_initial_grasp_supports', {}).get(symbol)
    if origin is not None:
        for key in ('original_support_plane_z_m', 'original_support_plane_evidence', 'support_proxy_source'):
            current[key] = copy.deepcopy(origin[key])
        current['support_reference_scope'] = 'registered_original_episode_initial; current grip pose unchanged'
    return current


def evaluate_case(case, endpoints, output, plan, *, startup=False):
    output.mkdir()
    variants = plan.get('vla_variants')
    if variants is not None and (not plan.get('vla_options_v2') or not variants
            or len({v['name'] for v in variants}) != len(variants)):
        raise ValueError('distinct registered variants require the B2 development catalog')
    with runtime(case, endpoints, output) as (facade, adapter, policy, timings):
        configure_development_catalog(adapter, plan)
        if 'recovery_budget' in plan:
            if type(plan['recovery_budget']) is not int or plan['recovery_budget'] not in (0,1,2):
                raise ValueError('registered hybrid recovery budget must be 0, 1 or 2')
            adapter.hybrid_recovery_budget = plan['recovery_budget']
        registered_initial = plan.get('initial_state_by_case', {}).get(case['name'])
        episode_origin = plan.get('episode_origin_by_case', {}).get(case['name'])
        if episode_origin is not None:
            if registered_initial is None:
                raise ValueError('episode-origin support requires an explicitly registered continuation state')
            if reference(episode_origin['path']) != episode_origin:
                raise ValueError('registered episode origin changed')
            original = pickle.loads(Path(episode_origin['path']).read_bytes())
            facade.restore(original['physics'])
            facade._native_success_events = copy.deepcopy(original.get('private_native_success_events', []))
            if snapshot_digest(facade.snapshot()) != snapshot_digest(original['physics']):
                raise ValueError('episode origin did not restore exactly for private support metrology')
            goals = facade.goal_status()['goals']
            origin_subtasks, _ = split_subtasks(goals, adapter.ex.instruction)
            symbols = {spec['source_symbol'] for spec in origin_subtasks if spec['mode'] == 'pick'}
            facade._episode_initial_grasp_supports = {symbol: facade.grasp_reference(symbol) for symbol in symbols}
        if registered_initial is not None:
            from coordination.bounded_skills_20261016.scripts.original_model_closedloop_20261021 import restore_registered_physics
            restore_registered_physics(sys.modules[__name__], facade, adapter, registered_initial)
        adapter.human_available = False
        initial, initial_ref = save_checkpoint(facade, adapter, policy, output / "private_initial.pkl")
        status = facade.goal_status()
        subtasks, unsupported = split_subtasks(status["goals"], adapter.ex.instruction)
        write(output / "private_subtask_plan.json", {"version": SPLIT_VERSION,
            "subtasks": subtasks, "unsupported": unsupported, "initial": initial_ref})
        if unsupported:
            # Missing private rules remain unknown in the sampled bound;
            # they must not silently turn into an unexecuted failed episode.
            replay = native_instruction_replay(facade,adapter,policy,timings,
                output/'full_replay_native',plan['trial_seed_base']+1000000000)
            result = {"case": case, "status": "oracle_rule_uncovered", "success": None,
                      "unsupported": unsupported, "training": False,
                      'actual_full_replay_success':replay['success'],'full_replay':[replay],
                      'conditional_rate_product':None,'independent_replay_wall_s':replay['wall_s'],
                      'source_commit':plan['source_commit']}
            write(output / "summary.json", result)
            return result
        chosen, rows, envelope_rate, decisions_used = [], [], 1., 0
        envelope_done = bool(status['done'])
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
            if variants is None:
                methods = [(0, 'call_vla', None)] if startup else [(0, 'self', None),
                    *[(j, 'call_vla', None) for j in (1, 2, 3)]]
            else:
                methods = [(j, 'call_vla', variant) for variant in variants for j in (1, 2, 3)]
                methods = methods[:1] if startup else [(0, 'self', None), *methods]
            for j, method, variant in methods:
                restore_checkpoint(facade, adapter, policy, branchpoint)
                seed = plan["trial_seed_base"] + 1000000 * plan["cases"].index(case) + 10000 * index + 1000 * j
                trial_name = f'{method}_{j}' if variant is None else f'call_vla_{variant["name"]}_{j}'
                options = {'vla_parameters': variant['parameters']} if variant is not None else {}
                row, endpoint = trial(facade, adapter, policy, timings, spec, method, seed,
                    directory / trial_name, request, decision_limit=160 - decisions_used, **options)
                if variant is not None:
                    row['vla_variant'] = variant
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
            selection = (choose_variant_branch(trials, variants) if variants is not None else
                choose_branch(trial_progress_success(trials[0]),
                    [trial_progress_success(row) for row in trials[1:]]))
            selection['selection_success_contract'] = PROGRESS_VERSION
            choice = {'subtask': spec, 'method': selection['method']}
            if 'vla_parameters' in selection:
                choice.update(vla_parameters=selection['vla_parameters'], vla_variant=selection['vla_variant'])
            row = {"subtask": spec, "trials": trials, "selection": selection}
            rows.append(row)
            write(directory / "paired.json", row)
            if selection["method"] is None or selection["status"] == "both_failed":
                envelope_rate = 0. if selection["status"] == "both_failed" else None
                if selection["method"] is not None:
                    # Even the best measured method can fail. Independently
                    # replay it instead of calling an unexecuted replay false.
                    chosen.append(choice)
                break
            envelope_rate *= selection["rate"]
            candidates = selection.get('trial_indices', [0] if selection['method'] == 'self' else [1, 2, 3])
            continuation = next(i for i in candidates if trial_progress_success(trials[i]) is True)
            chosen.append(choice)
            decisions_used += trials[continuation]["decisions"]
            restore_checkpoint(facade, adapter, policy, endpoints_saved[continuation])
            selected_trial = trials[continuation]
            envelope_done = (selected_trial['native_task_success']
                if 'native_task_success' in selected_trial else facade.goal_status()['done'])
            if envelope_done:
                break
        from robots.libero.bounded_hybrid_paths import select_complete_path, replay_complete_path

        sampled = {"status": "physical_result", "subtasks": rows,
            "sampled_envelope_native_success": envelope_done,
            "conditional_rate_product": envelope_rate}
        complete_selection = select_complete_path(sampled)
        # Independently execute the selected method sequence from the original
        # full state, never splice saved successful endpoints into this replay.
        restore_checkpoint(facade, adapter, policy, initial)
        replay_started = time.perf_counter()
        replay, replay_decisions = [], 0
        if complete_selection['reason'] == 'measured_native_complete_path':
            complete = replay_complete_path(sys.modules[__name__], facade, adapter, policy,
                timings, complete_selection,
                plan['trial_seed_base'] + 1000000000 + 1000000 * plan['cases'].index(case),
                output / 'full_replay_complete')
            replay = complete['full_replay']
        elif any(row['selection']['method'] is None for row in rows):
            # No method can be inferred from unknown labels. Exercise the
            # explicit public whole-instruction candidate and keep the
            # sampled bound unknown, separate from the native replay result.
            replay.append(native_instruction_replay(facade,adapter,policy,timings,
                output/'full_replay_native',plan['trial_seed_base']+1000000000))
        else:
            for index, choice in enumerate(chosen):
                with timings.measure("planning.request"):
                    request = adapter.request(k=4)
                seed = plan["trial_seed_base"] + 1000000000 + 1000000 * plan["cases"].index(case) + 10000 * index
                row, endpoint = trial(facade, adapter, policy, timings, choice["subtask"],
                    choice["method"], seed, output / f"full_replay_{index:02d}", request,
                    decision_limit=160 - replay_decisions,
                    **({'vla_parameters': choice['vla_parameters']} if 'vla_parameters' in choice else {}))
                if 'vla_variant' in choice:
                    row['selected_vla_variant'] = choice['vla_variant']
                replay.append(row)
                replay_decisions += row["decisions"]
                restore_checkpoint(facade, adapter, policy, endpoint)
                if trial_progress_success(row) is not True:
                    break
        result = {"case": case, "status": "physical_result", "subtasks": rows,
            "sampled_envelope_native_success": complete_selection['sampled_native_success'],
            "conditional_rate_product": complete_selection['conditional_rate'],
            "path_selection": complete_selection,
            "local_path_native_success": envelope_done,
            "local_path_conditional_rate_product": envelope_rate,
            "actual_full_replay_success": facade.goal_status()["done"], "full_replay": replay,
            "independent_replay_wall_s": time.perf_counter() - replay_started if replay else None,
            "independent_replay_wall_scope": "after restoring initial physics/public cache; includes replay planning, execution and private measurement; excludes forks, method selection and simulator construction",
            "wall_time_breakdown": timings.summary(time.perf_counter() - timings.started),
            "training": False, "confirmation": False, "source_commit": plan["source_commit"],
            'registered_vla_variants': variants}
        result['private_progress_contract'] = PROGRESS_VERSION
        write(output / "summary.json", result)
        return result


def configure_development_catalog(adapter, plan):
    """Enable the registered B2 catalog for explicit development plans only.

    Model training and serving keep their separate catalog activation. This
    option changes neither the adapter default nor a historical request.
    """
    enabled = plan.get('vla_options_v2', False)
    if type(enabled) is not bool:
        raise ValueError('vla_options_v2 must be a boolean')
    adapter.vla_options_v2 = enabled


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
