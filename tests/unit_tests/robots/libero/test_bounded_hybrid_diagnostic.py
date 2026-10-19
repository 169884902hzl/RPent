# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""D2-only admission, unchanged rules and branch state isolation."""

from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.bounded_hybrid_diagnostic import (
    D2_SUITES,
    capture_runtime,
    choose_branch,
    restore_runtime,
    snapshot_digest,
    split_subtasks,
    validate_d2_episode,
)


def test_d2_admission_is_exactly_the_registered_forty():
    for suite in D2_SUITES:
        for task in range(5):
            validate_d2_episode({"suite": suite, "task": task, "seed": 40})
    for update in ({"task": 5}, {"seed": 41}, {"suite": "libero_spatial"},
                   {"suite": "libero_goal_swap", "task": True}, {"extra": "test"}):
        with pytest.raises(ValueError):
            validate_d2_episode({"suite": "libero_spatial_swap", "task": 0, "seed": 40} | update)


def test_split_only_uses_existing_modes_and_reports_uncovered_rules():
    tasks, unsupported = split_subtasks([
        ["on", "bowl_1", "plate_1"], ["open", "cabinet_1"],
        ["turnoff", "stove_1"], ["touch", "cup_1"],
        ["and", ["open", "drawer_1"], ["close", "drawer_2"]],
    ])
    assert [t["mode"] for t in tasks] == ["pick", "on", "open", "turn_off"]
    assert [t["id"] for t in tasks] == ["g0:pick", "g0:on", "g1:open", "g2:turn_off"]
    assert [t["index"] for t in unsupported] == [3, 4]


def test_original_push_is_one_contact_subtask_without_a_pick_prerequisite():
    tasks, unsupported = split_subtasks([['on', 'plate_1', 'stove_front_region']],
        'push the plate to the front of the stove')
    assert [task['mode'] for task in tasks] == ['push']
    assert tasks[0]['target_symbol'] == 'stove_front_region' and not unsupported


def test_unknown_is_not_failure_and_tie_prefers_self():
    assert choose_branch(True, [True, True, True])["method"] == "self"
    assert choose_branch(False, [False, True, False])["rate"] == 1 / 3
    assert choose_branch(False, [False, False, False])["status"] == "both_failed"
    assert choose_branch(False, [False, None, False])["method"] is None
    with pytest.raises(ValueError):
        choose_branch(False, [True])


def test_seeded_policy_fingerprints_the_actual_wire_inputs_without_changing_them(tmp_path):
    import json

    from scripts.probe_bounded_hybrid_d2 import SeededPolicy

    seen = []
    client = SimpleNamespace(encode_obs=lambda obs: obs,
        predict=lambda obs, options: seen.append((obs, options)) or np.zeros((5, 7)))
    ledger = tmp_path/'vla_inputs.jsonl'
    policy = SeededPolicy(client, 100, input_ledger=ledger)
    obs = {'states': np.array([[.04, -.04]], dtype=np.float32),
        'main_images': np.zeros((1, 2, 2, 3), dtype=np.uint8), 'task_descriptions': ['pick up the bowl']}
    policy.predict(obs)
    policy.predict(obs)
    assert seen[0][0] is obs and [s[1]['sampling_seed'] for s in seen] == [100, 101]
    assert policy.inputs[0]['wire_observation_sha256'] == policy.inputs[1]['wire_observation_sha256']
    obs['states'][0, 0] += .00001
    policy.predict(obs)
    assert policy.inputs[-1]['fields']['states'] != policy.inputs[0]['fields']['states']
    assert policy.inputs[-1]['fields']['main_images'] == policy.inputs[0]['fields']['main_images']
    assert [json.loads(line) for line in ledger.read_text().splitlines()] == policy.inputs


def test_recognized_storage_predicates_do_not_claim_prerequisite_rule_coverage():
    tasks, unsupported = split_subtasks([
        ['close', 'cabinet_bottom_region'], ['in', 'bowl', 'cabinet_bottom_region']])
    assert [task['mode'] for task in tasks] == ['close', 'pick', 'in']
    assert unsupported == [{'index': 0, 'goal': ['close', 'cabinet_bottom_region'],
        'reason': 'existing_oracle_storage_insert_close_progress_not_covered'}]
    # Independent close/in goals on different fixtures do not imply this gap.
    _, unsupported = split_subtasks([
        ['close', 'microwave'], ['in', 'bowl', 'basket']])
    assert unsupported == []


def test_runtime_restore_does_not_leak_sibling_caches_or_retry_history():
    p = SimpleNamespace(_bounded_control_index=10, client=object())
    scene = SimpleNamespace(toolkit=object(), rpc=object(), entities={"e1": [1]}, calls=1)
    adapter = SimpleNamespace(ex=object(), p=p, scene=scene, receipts=[{"outcome": "failure"}],
                              held=None, memory={"tries": 1})
    policy = SimpleNamespace(binding=SimpleNamespace(rpc=object(), _bindings={"bowl": "e1"}),
                             private_trace=[{"goal": "g0"}])
    state = capture_runtime(adapter, policy)
    resource_ids = (id(scene.toolkit), id(adapter.ex), id(policy.binding.rpc))
    scene.entities["e1"].append(2)
    adapter.memory["tries"] = 99
    p._bounded_new_trace = [42]
    p._bounded_control_index = 40
    policy.binding._bindings["bowl"] = "wrong"
    restore_runtime(adapter, policy, state)
    assert (id(scene.toolkit), id(adapter.ex), id(policy.binding.rpc)) == resource_ids
    assert scene.entities == {"e1": [1]} and adapter.memory == {"tries": 1}
    assert p._bounded_control_index == 10 and not hasattr(p, "_bounded_new_trace")
    adapter.memory["tries"] = 2
    restore_runtime(adapter, policy, state)
    assert adapter.memory["tries"] == 1


def test_physical_identity_includes_controller_and_counter_state():
    first = {"sim_state": np.array([1., 2.]), "controller": {"goal_pos": [3., 4.]}, "counter": 10}
    assert snapshot_digest(first) == snapshot_digest(dict(reversed(list(first.items()))))
    assert snapshot_digest(first) != snapshot_digest(first | {"counter": 11})


def test_checkpoint_restores_success_history_and_client_stops_after_sibling(tmp_path):
    from scripts import probe_bounded_hybrid_d2 as probe

    class Facade:
        def __init__(self):
            self._native_success_events = []
            self.steps = 0

        def snapshot(self):
            return {"sim_state": [1.], "counters": {"_elapsed_steps": self.steps},
                    "native_success_event_count": len(self._native_success_events)}

        def restore(self, state):
            self.steps = state['counters']['_elapsed_steps']
            self._native_success_events = self._native_success_events[
                :state['native_success_event_count']]
            return {"restored": True}

    facade = Facade()
    env = SimpleNamespace(terminated=False, truncated=False)
    primitive = SimpleNamespace(env=env, set_obs=lambda *_: None)
    scene = SimpleNamespace(toolkit=object(), rpc=object(), entities={})
    adapter = SimpleNamespace(ex=object(), p=primitive, scene=scene, held=None)
    policy = SimpleNamespace(binding=SimpleNamespace(rpc=object()), private_trace=[])
    initial, _ = probe.save_checkpoint(facade, adapter, policy, tmp_path/'initial.pkl')
    facade.steps = 12
    facade._native_success_events.append({'elapsed_steps': 12, 'raw_termination': True})
    env.terminated = True
    endpoint, _ = probe.save_checkpoint(facade, adapter, policy, tmp_path/'endpoint.pkl')
    probe.restore_checkpoint(facade, adapter, policy, initial)
    assert not env.terminated and facade._native_success_events == []
    # A sibling branch can replace the diagnostics after the endpoint was saved.
    facade._native_success_events.append({'elapsed_steps': 7, 'raw_termination': False})
    env.truncated = True
    probe.restore_checkpoint(facade, adapter, policy, endpoint)
    assert facade._native_success_events == [{'elapsed_steps': 12, 'raw_termination': True}]
    assert env.terminated and not env.truncated and facade.steps == 12
    facade._native_success_events[0]['elapsed_steps'] = 99
    probe.restore_checkpoint(facade, adapter, policy, endpoint)
    assert facade._native_success_events[0]['elapsed_steps'] == 12


def test_missing_vla_candidate_never_falls_back_to_an_oracle_action(tmp_path, monkeypatch):
    from scripts import probe_bounded_hybrid_d2 as probe

    physics = {"sim_state": [1.], "counters": {"_elapsed_steps": 0}}
    facade = SimpleNamespace(snapshot=lambda: physics, goal_status=lambda: {"satisfied": [False]})
    source = SimpleNamespace(id="e1")
    monkeypatch.setattr(probe, "bind_subtask", lambda *args: (source, None))
    monkeypatch.setattr(probe, "save_checkpoint", lambda *args: ({"physics": physics}, {}))
    adapter = SimpleNamespace(p=SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False,
        execution_budget=lambda: {"used_sim_steps": 0}), model=object()))
    policy = SimpleNamespace(rpc=object())
    request = {"candidates": [], "max_actions": 4, "robot": {"held_anchor_id": None}, "anchors": []}
    spec = {"mode": "open", "source_symbol": "cabinet_1", "target_symbol": None, "goal_index": 0}
    row, _ = probe.trial(facade, adapter, policy, None, spec, "call_vla", 123,
                         tmp_path / "branch", request)
    assert row["reason"] == "matching_call_vla_candidate_unavailable"
    assert row["success"] is False and row["vla_inference_calls"] == 0
    assert row["sim_steps"] == 0 and row["selected_candidate_id"] is None
    assert (tmp_path / "branch/choices.jsonl").read_text() == ""


@pytest.mark.parametrize('method', ['self', 'call_vla'])
def test_ambiguous_binding_observes_then_rebinds_without_private_instance_selection(tmp_path, monkeypatch, method):
    from contextlib import nullcontext

    from scripts import probe_bounded_hybrid_d2 as probe

    source = SimpleNamespace(id='measured1')
    bindings = iter([(None, None), (source, None)])
    monkeypatch.setattr(probe, 'bind_subtask', lambda *_: next(bindings))
    executed = []
    def physics():
        return {'sim_state': [1.], 'counters': {'_elapsed_steps': len(executed)}}
    facade = SimpleNamespace(snapshot=physics,
        goal_status=lambda: {'satisfied': [len(executed) == 2]})
    monkeypatch.setattr(probe, 'save_checkpoint', lambda *_: ({'physics': physics()}, {}))
    base = {'schema_version': 'test', 'observation_id': 'o1', 'revision': 1,
        'max_actions': 4, 'robot': {'held_anchor_id': None}, 'anchors': []}
    consequences = {'collision': False, 'ik_reachable': True, 'screen_scope': 'measured'}
    observe = {'id': 'scan', 'skill': 'observe', 'parameters': {'mode': 'wrist_scan'},
        'consequences': consequences}
    action = {'id': 'open', 'skill': 'call_vla' if method == 'call_vla' else 'descend',
        'parameters': {'anchor_id': source.id, 'mode': 'open'}, 'consequences': consequences}
    request = base | {'candidates': [action]}
    adapter = SimpleNamespace(request=lambda **_: request, held=None, details=[], last_chunk={},
        p=SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False,
            execution_budget=lambda: {'used_sim_steps': len(executed)}), model=object()))
    def execute(_, decision):
        executed.append(decision['candidate_ids'])
        return [{'stop_reason': 'measured_success'}]
    adapter.execute = execute
    policy = SimpleNamespace(rpc=object(), choose=lambda _: base | {'candidate_ids': ['open']})
    timings = SimpleNamespace(measure=lambda *_: nullcontext())
    spec = {'mode': 'open', 'source_symbol': 'cabinet_1', 'target_symbol': None, 'goal_index': 0}
    result, _ = probe.trial(facade, adapter, policy, timings, spec, method, 123,
        tmp_path/'branch', base | {'candidates': [observe]})
    assert executed == [['scan'], ['open']]
    assert result['success'] is True and result['decisions'] == 2
    assert result['selected_candidate_id'] == 'open'
    assert result['source_public_id'] == source.id
    assert result['binding_recovery'] == [{'decision': 0, 'reason': 'source_binding_missing',
        'candidate_id': 'scan', 'mode': 'wrist_scan'}]


@pytest.mark.parametrize('physical', [False, True])
def test_startup_calls_vla_before_any_full_oracle_branch(tmp_path, monkeypatch, physical):
    from contextlib import contextmanager, nullcontext

    from robots.libero import bounded_offline_labels
    from scripts import probe_bounded_hybrid_d2 as probe

    case = {'name': 'D2', 'episode': {'suite': 'libero_spatial_swap', 'task': 0, 'seed': 40}}
    plan = {'cases': [case], 'source_commit': 'tested', 'trial_seed_base': 1000}
    facade = SimpleNamespace(goal_status=lambda: {'goals': [['on', 'bowl_1', 'plate_1']],
                                                  'satisfied': [False]})
    adapter = SimpleNamespace(request=lambda **kwargs: {'candidates': []},
        ex=SimpleNamespace(instruction='put the bowl on the plate'))
    timings = SimpleNamespace(measure=lambda *_: nullcontext())

    @contextmanager
    def runtime(*_):
        yield facade, adapter, object(), timings

    methods = []

    def trial(*args, **kwargs):
        methods.append(args[5])
        return {'sim_steps': int(physical), 'vla_inference_calls': int(physical),
                'request_sha256': 'same'}, {}

    monkeypatch.setattr(probe, 'runtime', runtime)
    monkeypatch.setattr(probe, 'save_checkpoint', lambda *_: ({}, {}))
    monkeypatch.setattr(probe, 'restore_checkpoint', lambda *_: None)
    monkeypatch.setattr(probe, 'trial', trial)
    monkeypatch.setattr(bounded_offline_labels, 'capture_annotation_state', lambda *_: {})
    monkeypatch.setattr(bounded_offline_labels, 'save_annotation_state', lambda *_: {})
    result = probe.evaluate_case(case, {}, tmp_path / 'episode', plan, startup=True)
    assert methods == ['call_vla']
    assert result['status'] == ('startup_physical' if physical else 'startup_no_vla_physics')
    assert (tmp_path / 'episode/first_physical_vla_request.json').exists() is physical
