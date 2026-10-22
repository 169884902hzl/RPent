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


@pytest.mark.parametrize('peer_visible', [False, True])
def test_subtask_binding_retains_public_identity_without_resolving_ambiguous_source(peer_visible):
    import copy

    from robots.libero.v5_oracle_policy import OriginalOraclePolicy
    from scripts.probe_bounded_hybrid_d2 import bind_subtask

    source = SimpleNamespace(id='source', name='cream cheese', visible=True)
    peer = SimpleNamespace(id='peer', name='cream cheese', visible=peer_visible)
    basket = SimpleNamespace(id='basket', name='basket', visible=True)
    axes = ([1., 0., 0.], [0., 1., 0.])
    binding = OriginalOraclePolicy(object())
    policy = SimpleNamespace(binding=binding)
    adapter = SimpleNamespace(scene=SimpleNamespace(
        entities={e.id: e for e in (source, peer, basket)}, view_axes=axes),
        ex=SimpleNamespace(instruction='pick up the cream cheese and place it in the basket'))
    spec = {'source_symbol': 'cream_cheese_1', 'target_symbol': 'basket_1_contain_region'}
    chosen, target = bind_subtask(policy, adapter, spec)
    assert target is basket and binding._bindings['basket_1_contain_region'] == 'basket'
    if peer_visible:
        assert chosen is None and 'cream_cheese_1' not in binding._bindings
    else:
        assert chosen is source and binding._bindings['cream_cheese_1'] == 'source'
        assert binding._binding_peers['cream_cheese_1'] == {'peer'}
        # The bounded oracle also exposes cached anchors. They must not undo
        # the identity resolved before contact, or rebind to a known peer.
        cached = copy.copy(peer)
        cached.visible = True
        assert binding.bind('cream_cheese_1', [source, cached], '', axes) is source
        source.visible = False
        assert binding.bind('cream_cheese_1', [source, cached], '', axes) is None


def test_hybrid_executor_loads_registered_sensor_calibration_for_thin_rim_hold(tmp_path):
    import json

    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from scripts.probe_bounded_hybrid_d2 import make_executor, reference
    from tests.unit_tests.robots.libero.test_bounded_motion import FakePrimitives

    path = tmp_path/'public_gripper.json'
    path.write_text(json.dumps({'opening_calibration': {
        'closed_empty_max_m': .00185, 'tolerance_m': .00085, 'open_empty_min_m': .07815},
        'grip_site_geometry': {}, 'robot_rigid_transform_validation': {},
        'source_report': {'sha256': '0'*64}}))
    case = {'grasp_measurement_calibration': reference(path)}
    executor = make_executor(SimpleNamespace(primitives=FakePrimitives()), SimpleNamespace(), case)
    probe = SimpleNamespace(ex=executor)
    permitted, evidence = MeasuredSkillAdapter.holding_aperture(probe, .00376)
    assert permitted and evidence['source'] == 'original_empty_gripper_proprioception'
    assert not MeasuredSkillAdapter.holding_aperture(probe, .0018)[0]
    assert not MeasuredSkillAdapter.holding_aperture(probe, .079)[0]
    path.write_text('{}')
    with pytest.raises(ValueError, match='calibration changed'):
        make_executor(SimpleNamespace(primitives=FakePrimitives()), SimpleNamespace(), case)


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


@pytest.mark.parametrize('size,stride', [(65536, 1), (1048593, 1), (262144, 2)])
def test_native_byte_stream_hash_matches_legacy_canonical_json(size, stride):
    import hashlib
    import json
    blob = np.arange(size*stride, dtype=np.uint8)[::stride]
    snapshot = {'actuator_state': {'native_data': {'values': blob, 'version': 'native/1'},
        'controller': np.array([-0., 1.25]), 'rng': (3, np.int64(7))},
        'escaped\nfield': ['雪', {False: 'f', True: 't'}],
        'numeric_keys': {3: [blob], 1: None}}
    def convert(value):
        return value.tolist() if isinstance(value, np.ndarray) else value.item()
    expected = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':'),
        default=convert, allow_nan=False).encode()).hexdigest()
    assert snapshot_digest(snapshot) == expected
    blob[0] ^= 1
    assert snapshot_digest(snapshot) != expected


def test_native_byte_hash_keeps_nonfinite_scalar_rejection():
    snapshot = {'native': np.zeros(65536, np.uint8), 'bad': float('nan')}
    with pytest.raises(ValueError, match='Out of range float'):
        snapshot_digest(snapshot)


def test_runtime_restore_selects_captured_rgbd_and_keeps_sibling_files(tmp_path):
    from rpent.session import EnvState

    store = EnvState(tmp_path)
    with store.record_step(state={'frame': 0}):
        store.save('world.npz', np.array([[1., 2., 3.]]))
    initial_file = store.artifact_path('world.npz')
    original_bytes = initial_file.read_bytes()
    toolkit = SimpleNamespace(_state=store, _state_output_dir=tmp_path)
    scene = SimpleNamespace(toolkit=toolkit, rpc=object(), entities={})
    adapter = SimpleNamespace(ex=object(), p=SimpleNamespace(), scene=scene)
    policy = SimpleNamespace(binding=SimpleNamespace(rpc=object()), private_trace=[])
    captured = capture_runtime(adapter, policy)
    with store.record_step(state={'frame': 1}):
        store.save('world.npz', np.array([[4., 5., 6.]]))
    sibling = store.artifact_path('world.npz')
    restore_runtime(adapter, policy, captured)
    assert toolkit._state is store and store.latest_step == 0
    np.testing.assert_array_equal(store.load('world.npz'), [[1., 2., 3.]])
    branch_file = store.artifact_path('world.npz')
    assert branch_file != initial_file and branch_file.read_bytes() == original_bytes
    # Planning artifacts written after restore stay in that branch. Even an
    # atomic replacement of a hard-linked capture cannot change the source.
    store.save('world.npz', np.array([[7., 8., 9.]]))
    assert initial_file.read_bytes() == original_bytes
    assert sibling.exists()
    restore_runtime(adapter, policy, captured)
    assert store.latest_step == 0 and store.artifact_path('world.npz') != branch_file
    np.testing.assert_array_equal(store.load('world.npz'), [[1., 2., 3.]])
    with store.record_step(state={'frame': 2}):
        store.save('world.npz', np.array([[10., 11., 12.]]))
    assert store.latest_step == 1
    np.testing.assert_array_equal(np.load(sibling)['array'], [[4., 5., 6.]])


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


def test_unchanged_observations_do_not_spend_recovery_on_recorded_d2_receipts():
    import json
    from pathlib import Path
    from scripts.probe_bounded_hybrid_d2 import consumes_recovery

    path = Path(__file__).parent / 'fixtures/observe_recovery_receipts_20261022.json'
    rows = json.loads(path.read_text())['rows']
    for row in rows:
        unchanged = [r for r in row['receipts'] if r['skill'] == 'observe'
            and r['stop_reason'] == 'no_measured_scene_change']
        assert unchanged
        assert not any(consumes_recovery(r) for r in unchanged)
        # A physical action failure remains charged, even with the same text.
        assert consumes_recovery({**unchanged[0], 'skill': 'lift'})
        assert consumes_recovery({**unchanged[0], 'outcome': 'failure',
            'stop_reason': 'measured_sweep_collision'})


def test_stale_chunk_anchor_does_not_charge_an_unexecuted_action():
    from scripts.probe_bounded_hybrid_d2 import consumes_recovery

    # object_swap_t1 recovery0: opening moved the source down 7.4cm; the
    # following move correctly stopped before executing stale parameters.
    receipt = {'skill': 'move_to', 'outcome': 'failure', 'phase': 'perception',
        'stop_reason': 'predicted_anchor_changed', 'steps_used': 0}
    assert not consumes_recovery(receipt)
    assert consumes_recovery(dict(receipt, steps_used=1))
    assert consumes_recovery(dict(receipt, stop_reason='measured_sweep_collision'))


def test_recorded_retry_uses_fresh_seed_before_repeating_a_failed_action(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from contextlib import nullcontext
    from scripts import probe_bounded_hybrid_d2 as probe

    records = json.loads((Path(__file__).parent/'fixtures/vla_retry_before_loop_20261023.json').read_text())
    first, second = [r['request'] for r in records]
    executed = []
    physics = lambda: {'sim_state': [0.], 'counters': {'_elapsed_steps': 5*len(executed)}}
    facade = SimpleNamespace(snapshot=physics,
        goal_status=lambda: {'done': len(executed) == 2, 'satisfied': [len(executed) == 2]})
    monkeypatch.setattr(probe, 'bind_subtask', lambda *_: (None, None))
    monkeypatch.setattr(probe, 'save_checkpoint', lambda *_: ({'physics': physics()}, {}))
    adapter = SimpleNamespace(details=[], last_chunk={}, held=None, hybrid_recovery_budget=1,
        request=lambda **_: second, ex=SimpleNamespace(instruction=first['instruction']),
        p=SimpleNamespace(model=object(), env=SimpleNamespace(terminated=False, truncated=False,
            execution_budget=lambda: {'used_sim_steps': 5*len(executed)})))
    def execute(_request, decision):
        executed.extend(decision['candidate_ids'])
        return [{'skill': 'call_vla', 'steps_used': 5,
            'outcome': 'failure' if len(executed) == 1 else 'success',
            'stop_reason': 'no_progress_blocks' if len(executed) == 1 else 'native_success'}]
    adapter.execute = execute
    spec = {'mode': 'pick', 'goal_index': 0, 'source_symbol': 'registered_object', 'target_symbol': None}
    result, _ = probe.trial(facade, adapter, SimpleNamespace(rpc=object()),
        SimpleNamespace(measure=lambda *_: nullcontext()), spec, 'call_vla', 1,
        tmp_path/'branch', first, vla_parameters={'mode': 'task',
            'preparation': 'in_place', 'prompt_style': 'full_task'})
    assert executed == ['9cb9f09d6d190d7b', 'aa0192a89b2c28ba']
    assert result['success'] is True and result['native_task_success'] is True
    assert result['decisions'] == 2 and result['recovery_used'] == 1


def test_missing_vla_candidate_never_falls_back_to_an_oracle_action(tmp_path, monkeypatch):
    from scripts import probe_bounded_hybrid_d2 as probe

    physics = {"sim_state": [1.], "counters": {"_elapsed_steps": 0}}
    facade = SimpleNamespace(snapshot=lambda: physics, goal_status=lambda: {"satisfied": [False], "done": False})
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


@pytest.mark.parametrize('preferred_available', [False, True])
@pytest.mark.parametrize('binding_case', ['missing', 'bound_source', 'bound_wrong_target_kind'])
def test_registered_variant_with_missing_binding_executes_public_task_fallback(tmp_path, monkeypatch, preferred_available, binding_case):
    from contextlib import nullcontext
    from scripts import probe_bounded_hybrid_d2 as probe

    source = None if binding_case == 'missing' else SimpleNamespace(id='e1')
    target = SimpleNamespace(id='measured_surface') if binding_case == 'bound_wrong_target_kind' else None
    monkeypatch.setattr(probe, 'bind_subtask', lambda *_: (source, target))
    executed = []
    physics = lambda: {'sim_state': [1.], 'counters': {'_elapsed_steps': len(executed)}}
    facade = SimpleNamespace(snapshot=physics, grasp_reference=lambda *_: {},
        goal_status=lambda: {'satisfied': [True], 'done': True})
    monkeypatch.setattr(probe, 'save_checkpoint', lambda *_: ({'physics': physics()}, {}))
    base = {'schema_version': 'test', 'observation_id': 'o1', 'revision': 1,
        'max_actions': 4, 'robot': {'held_anchor_id': None}, 'anchors': []}
    parameters = {'mode': 'task', 'preparation': 'in_place', 'prompt_style': 'full_task'}
    request = base | {'candidates': [{'id': 'public_full_task', 'skill': 'call_vla',
        'parameters': parameters, 'consequences': {'collision': False, 'ik_reachable': True,
            'screen_scope': 'measured'}}]}
    selected_id = 'public_full_task'
    if preferred_available:
        parameters = {**parameters, 'preparation': 'initial_pose'}
        selected_id = 'public_full_task_initial'
        request['candidates'].append({'id': selected_id, 'skill': 'call_vla',
            'parameters': parameters, 'consequences': {'collision': False,
                'ik_reachable': True, 'screen_scope': 'measured'}})
    def execute(_, decision):
        executed.append(decision['candidate_ids'])
        return [{'stop_reason': 'native_success'}]
    adapter = SimpleNamespace(held=None, details=[], last_chunk={}, execute=execute,
        ex=SimpleNamespace(instruction='pick up the bowl and place it on the plate'),
        p=SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False,
            execution_budget=lambda: {'used_sim_steps': len(executed)}), model=object()))
    spec = {'mode': 'pick', 'source_symbol': 'bowl_1', 'target_symbol': None, 'goal_index': 0}
    if binding_case == 'bound_wrong_target_kind':
        spec.update(mode='in', target_symbol='cabinet_top_region')
    requested = {'preparation': 'initial_pose'}
    row, _ = probe.trial(facade, adapter, SimpleNamespace(rpc=object()),
        SimpleNamespace(measure=lambda *_: nullcontext()), spec, 'call_vla', 123,
        tmp_path/'branch', request, vla_parameters=requested)
    assert executed == [[selected_id]]
    assert row['reason'] == 'native_success' and row['success'] is True
    assert row['truth_source'] == 'unchanged_native_task_completion'
    assert row['source_public_id'] == (source.id if source is not None else None)
    assert row['vla_variant_fallbacks'] == [{'decision': 0, 'reason': ('public_binding_missing'
        if binding_case == 'missing' else 'requested_public_option_unavailable'),
        'requested_parameters': requested, 'actual_parameters': parameters,
        'candidate_id': selected_id}]
    assert row['executed_vla_variants'][0]['parameters'] == parameters


def test_unbound_call_never_uses_an_illegal_or_unmeasured_anchor_candidate():
    from scripts.probe_bounded_hybrid_d2 import unbound_vla_candidate

    request = {'max_actions': 4, 'robot': {'held_anchor_id': None}, 'anchors': [],
        'candidates': [{'id': 'bad', 'skill': 'call_vla',
            'parameters': {'mode': 'task', 'preparation': 'in_place'},
            'consequences': {'collision': True, 'ik_reachable': True}}]}
    assert unbound_vla_candidate(request, 'pick up the bowl', 'pick') is None


@pytest.mark.parametrize('method', ['self', 'call_vla'])
@pytest.mark.parametrize('recovery_budget', [None, 0])
def test_ambiguous_binding_observes_then_rebinds_without_private_instance_selection(tmp_path, monkeypatch, method, recovery_budget):
    from contextlib import nullcontext

    from scripts import probe_bounded_hybrid_d2 as probe

    source = SimpleNamespace(id='measured1')
    bindings = iter([(None, None), (source, None)])
    monkeypatch.setattr(probe, 'bind_subtask', lambda *_: next(bindings))
    executed = []
    def physics():
        return {'sim_state': [1.], 'counters': {'_elapsed_steps': len(executed)}}
    facade = SimpleNamespace(snapshot=physics,
        goal_status=lambda: {'satisfied': [len(executed) == 2], 'done': len(executed) == 2})
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
        hybrid_recovery_budget=recovery_budget,
        ex=SimpleNamespace(instruction='open the cabinet'),
        p=SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False,
            execution_budget=lambda: {'used_sim_steps': len(executed)}), model=object()))
    def execute(_, decision):
        executed.append(decision['candidate_ids'])
        return [{'skill': 'observe', 'outcome': 'no_effect', 'steps_used': 23,
            'stop_reason': 'no_measured_scene_change'}] if len(executed) == 1 else [
            {'skill': 'descend', 'outcome': 'success', 'steps_used': 8,
             'stop_reason': 'measured_success'}]
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
    assert result['recovery_used'] == 0
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
                                                  'satisfied': [False], 'done': False})
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


@pytest.mark.parametrize('unknown', [False, True])
@pytest.mark.parametrize('metrology_done', [False, True])
def test_full_replay_executes_measured_zero_zero_tie_but_not_unknown_method(tmp_path, monkeypatch, unknown, metrology_done):
    from contextlib import contextmanager, nullcontext
    import time

    from robots.libero import bounded_offline_labels
    from scripts import probe_bounded_hybrid_d2 as probe

    case = {'name': 'D2', 'episode': {'suite': 'libero_spatial_swap', 'task': 0, 'seed': 40}}
    plan = {'cases': [case], 'source_commit': 'tested', 'trial_seed_base': 1000,
            'vla_options_v2': True}
    state = {'done': False}
    facade = SimpleNamespace(goal_status=lambda: {
        'goals': [['open', 'cabinet_1']], 'satisfied': [state['done']], 'done': state['done']})
    adapter = SimpleNamespace(request=lambda **_: {'candidates': []},
        ex=SimpleNamespace(instruction='open the cabinet'))
    timings = SimpleNamespace(measure=lambda *_: nullcontext(), started=time.perf_counter(),
        summary=lambda *_: {})

    @contextmanager
    def runtime(*_):
        yield facade, adapter, object(), timings

    methods = []

    def trial(*args, **kwargs):
        assert args[1].vla_options_v2 is True
        methods.append(args[5])
        state['done'] = metrology_done
        return {'success': None if unknown and args[5] == 'call_vla' else False,
            'native_task_success': False, 'decisions': 1, 'request_sha256': 'same'}, {'done': False}

    monkeypatch.setattr(probe, 'runtime', runtime)
    monkeypatch.setattr(probe, 'save_checkpoint', lambda *_: (dict(state), {}))
    monkeypatch.setattr(probe, 'restore_checkpoint', lambda *args: state.update(args[-1]))
    monkeypatch.setattr(probe, 'trial', trial)
    monkeypatch.setattr(bounded_offline_labels, 'capture_annotation_state', lambda *_: {})
    monkeypatch.setattr(bounded_offline_labels, 'save_annotation_state', lambda *_: {})
    native_calls = []
    def native_replay(*_):
        native_calls.append(True)
        return {'success':False,'wall_s':1.,'sim_steps':5,'method':'call_vla_full_instruction'}
    monkeypatch.setattr(probe,'native_instruction_replay',native_replay)
    result = probe.evaluate_case(case, {}, tmp_path / 'episode', plan)
    assert result['sampled_envelope_native_success'] is False
    assert methods[:4] == ['self', 'call_vla', 'call_vla', 'call_vla']
    if unknown:
        assert len(methods) == 4 and len(result['full_replay']) == 1
        assert native_calls == [True] and result['full_replay'][0]['sim_steps'] > 0
        assert result['conditional_rate_product'] is None
        assert result['independent_replay_wall_s'] >= 0.
    else:
        assert methods[4:] == ['self']
        assert len(result['full_replay']) == 1 and result['full_replay'][0]['success'] is False
        assert result['conditional_rate_product'] == 0.
        assert result['independent_replay_wall_s'] >= 0.


@pytest.mark.parametrize('preparation,whole_task', [('in_place', False), ('initial_pose', False), ('in_place', True)])
def test_registered_vla_variant_executes_exact_option_with_its_own_outcome_scope(tmp_path, monkeypatch, preparation, whole_task):
    from contextlib import nullcontext
    from scripts import probe_bounded_hybrid_d2 as probe

    source = SimpleNamespace(id='source')
    monkeypatch.setattr(probe, 'bind_subtask', lambda *_: (source, None))
    executed = []
    physics = lambda: {'sim_state': [1.], 'counters': {'_elapsed_steps': len(executed)}}
    facade = SimpleNamespace(snapshot=physics,
        goal_status=lambda: {'satisfied': [bool(executed)], 'done': bool(executed)})
    monkeypatch.setattr(probe, 'save_checkpoint', lambda *_: ({'physics': physics()}, {}))
    base = {'schema_version': 'test', 'observation_id': 'o', 'revision': 1,
        'max_actions': 4, 'robot': {'held_anchor_id': None}, 'anchors': []}
    candidates = [{'id': name, 'skill': 'call_vla', 'parameters': parameters,
        'consequences': {'collision': False, 'ik_reachable': True, 'screen_scope': 'measured'}}
        for name, parameters in [('in_place', {'anchor_id': 'source', 'mode': 'open', 'preparation': 'in_place'}),
            ('initial_pose', {'anchor_id': 'source', 'mode': 'open', 'preparation': 'initial_pose'}),
            ('full_task', {'mode': 'task', 'preparation': 'in_place', 'prompt_style': 'full_task'})]]
    request = base | {'candidates': candidates}
    adapter = SimpleNamespace(details=[], last_chunk={}, held=None,
        p=SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False,
            execution_budget=lambda: {'used_sim_steps': len(executed)}), model=object()))
    def execute(_, decision):
        executed.extend(decision['candidate_ids'])
        return [{'stop_reason': 'native_success' if whole_task else 'measured_success'}]
    adapter.execute = execute
    variant = {'mode': 'task', 'preparation': 'in_place', 'prompt_style': 'full_task'} if whole_task else {'preparation': preparation}
    spec = {'mode': 'pick' if whole_task else 'open', 'source_symbol': 'cabinet', 'target_symbol': None, 'goal_index': 0}
    row, _ = probe.trial(facade, adapter, SimpleNamespace(rpc=object()),
        SimpleNamespace(measure=lambda *_: nullcontext()), spec, 'call_vla', 123,
        tmp_path/'branch', request, vla_parameters=variant)
    assert executed == ['full_task' if whole_task else preparation]
    assert row['success'] is True
    assert row['truth_source'] == ('unchanged_native_task_completion' if whole_task else 'unchanged_registered_task_predicate')


def test_native_endpoint_completion_survives_failed_hold_and_metrology_steps(tmp_path, monkeypatch):
    from scripts import probe_bounded_hybrid_d2 as probe

    state = {'done': True}
    physics = {'counters': {'_elapsed_steps': 9}}
    def measure(*_):
        state['done'] = False
        return {'truth_v3': {'success': False}}
    facade = SimpleNamespace(snapshot=lambda: physics, grasp_reference=lambda *_: {},
        goal_status=lambda: {'done': state['done'], 'satisfied': [state['done']]},
        measure_grasp_hold=measure)
    monkeypatch.setattr(probe, 'bind_subtask', lambda *_: (SimpleNamespace(id='source'), None))
    monkeypatch.setattr(probe, 'save_checkpoint', lambda *_: ({'physics': physics}, {}))
    adapter = SimpleNamespace(p=SimpleNamespace(model=object(), env=SimpleNamespace(
        execution_budget=lambda: {'used_sim_steps': 9})))
    spec = {'mode': 'pick', 'source_symbol': 'object', 'target_symbol': None, 'goal_index': 0}
    row, _ = probe.trial(facade, adapter, SimpleNamespace(rpc=object()), None,
        spec, 'call_vla', 1, tmp_path/'branch', {'candidates': [], 'max_actions': 4,
            'robot': {'held_anchor_id': None}, 'anchors': []}, decision_limit=0)
    assert row['success'] is False
    assert row['native_task_success'] is True and state['done'] is False
    assert row['sim_steps'] == 0
    assert row['native_completion_scope'] == 'saved_endpoint_before_private_metrology'


@pytest.mark.parametrize('unknown', [False, True])
def test_variant_selection_uses_separate_three_trial_rates_and_keeps_unknown(unknown):
    from scripts.probe_bounded_hybrid_d2 import choose_variant_branch

    variants = [{'name': 'in_place', 'parameters': {'preparation': 'in_place'}},
        {'name': 'initial_pose', 'parameters': {'preparation': 'initial_pose'}}]
    outcomes = [False, True, False, False, True, True, None if unknown else False]
    result = choose_variant_branch([{'success': v} for v in outcomes], variants)
    assert [group['vla_n'] for group in result['variant_groups'] if 'vla_n' in group] == ([3] if unknown else [3, 3])
    if unknown:
        assert result['method'] is None and result['rate'] is None
    else:
        assert result['rate'] == 2/3
        assert result['vla_variant'] == 'initial_pose' and result['trial_indices'] == [4, 5, 6]
        assert result['vla_parameters'] == {'preparation': 'initial_pose'}


def test_d2_independent_replay_uses_the_selected_variant_and_shared_seed_triplets(tmp_path, monkeypatch):
    from contextlib import contextmanager, nullcontext
    import time

    from robots.libero import bounded_offline_labels
    from scripts import probe_bounded_hybrid_d2 as probe

    case = {'name': 'D2', 'episode': {'suite': 'libero_spatial_swap', 'task': 0, 'seed': 40}}
    variants = [{'name': 'in_place', 'parameters': {'preparation': 'in_place'}},
        {'name': 'initial_pose', 'parameters': {'preparation': 'initial_pose'}},
        {'name': 'full_task', 'parameters': {'mode': 'task', 'preparation': 'in_place', 'prompt_style': 'full_task'}}]
    plan = {'cases': [case], 'source_commit': 'tested', 'trial_seed_base': 1000,
        'vla_options_v2': True, 'vla_variants': variants}
    state = {'done': False}
    facade = SimpleNamespace(goal_status=lambda: {
        'goals': [['open', 'cabinet_1']], 'satisfied': [state['done']], 'done': state['done']})
    adapter = SimpleNamespace(request=lambda **_: {'candidates': []},
        ex=SimpleNamespace(instruction='open the cabinet'))
    timings = SimpleNamespace(measure=lambda *_: nullcontext(), started=time.perf_counter(), summary=lambda *_: {})

    @contextmanager
    def runtime(*_):
        yield facade, adapter, object(), timings

    calls = []
    def trial(*args, **kwargs):
        parameters = kwargs.get('vla_parameters')
        calls.append({'method': args[5], 'seed': args[6], 'parameters': parameters})
        # Only the whole-instruction strategy succeeds; replay must not
        # silently revert to the first available subtask call.
        success = parameters is not None and parameters.get('mode') == 'task'
        return {'success': success, 'decisions': 1, 'sim_steps': 1,
            'vla_inference_calls': int(args[5] == 'call_vla'), 'request_sha256': 'same'}, {'done': success}

    monkeypatch.setattr(probe, 'runtime', runtime)
    monkeypatch.setattr(probe, 'save_checkpoint', lambda *_: ({'done': False}, {}))
    monkeypatch.setattr(probe, 'restore_checkpoint', lambda _, __, ___, snapshot: state.update(snapshot))
    monkeypatch.setattr(probe, 'trial', trial)
    monkeypatch.setattr(bounded_offline_labels, 'capture_annotation_state', lambda *_: {})
    monkeypatch.setattr(bounded_offline_labels, 'save_annotation_state', lambda *_: {})
    result = probe.evaluate_case(case, {}, tmp_path/'episode', plan)
    assert len(calls) == 11
    assert [c['seed'] for c in calls[1:4]] == [c['seed'] for c in calls[4:7]] == [c['seed'] for c in calls[7:10]]
    assert calls[-1]['parameters'] == variants[2]['parameters']
    assert calls[-1]['seed'] == 1000001000
    assert result['subtasks'][0]['selection']['vla_variant'] == 'full_task'
    assert result['full_replay'][0]['selected_vla_variant'] == 'full_task'
    assert result['actual_full_replay_success'] is True
    assert result['conditional_rate_product'] == 1.


def test_native_instruction_replay_executes_public_task_candidate_without_private_rules(tmp_path):
    from contextlib import nullcontext
    from scripts import probe_bounded_hybrid_d2 as probe

    count = []
    request = {'schema_version': 'test', 'observation_id': 'o', 'revision': 1,
        'max_actions': 4, 'robot': {'held_anchor_id': None}, 'anchors': [],
        'candidates': [{'id': 'full', 'skill': 'call_vla',
            'parameters': {'mode': 'task', 'preparation': 'in_place'},
            'consequences': {'collision': False, 'ik_reachable': True, 'screen_scope': 'measured'}}]}
    def execute(_, decision):
        count.extend(decision['candidate_ids'])
        return [{'steps_used': 5}]
    adapter = SimpleNamespace(p=SimpleNamespace(model=object(),
        env=SimpleNamespace(terminated=False, truncated=False)),
        request=lambda **_: request, execute=execute)
    result = probe.native_instruction_replay(SimpleNamespace(goal_status=lambda: {'done': bool(count)}),
        adapter, object(), SimpleNamespace(measure=lambda *_: nullcontext()), tmp_path/'replay', 42)
    assert count == ['full'] and result['success'] is True and result['sim_steps'] == 5


def test_recorded_original_partial_completion_preserves_failed_invocation_label():
    import copy
    import json
    from pathlib import Path
    from robots.libero.bounded_hybrid_diagnostic import trial_progress_success
    from scripts.probe_bounded_hybrid_d2 import choose_variant_branch

    source=json.loads((Path(__file__).parent/'fixtures/original_partial_goal_20261023.json').read_bytes())
    rows=[{'success':r['recorded_local_success'],
        'private_goal_satisfied_at_endpoint':r['requested_goal_satisfied'],
        'native_task_success':r['native_complete']} for r in source['rows']]
    before=copy.deepcopy(rows)
    assert len(rows)==2
    assert all(trial_progress_success(row) is True for row in rows)
    variant={'name':'full_task','parameters':{'mode':'task','preparation':'in_place'}}
    # Two recorded witnesses plus a controlled no-progress sample exercise
    # selection; this is a unit scenario, not a new measured three-seed rate.
    trials=[{'success':False},*rows,{'success':False}]
    result=choose_variant_branch(trials,[variant])
    assert result['method']=='call_vla' and result['rate']==2/3
    assert rows==before and all(r['success'] is False and r['native_task_success'] is False for r in rows)
    assert trial_progress_success({'success':False}) is False
    assert trial_progress_success({'success':None}) is None
    assert trial_progress_success({'success':None,'private_goal_satisfied_at_endpoint':False}) is None


def test_completed_registered_goal_hands_back_without_repeating_a_failed_full_task(tmp_path,monkeypatch):
    import json
    from pathlib import Path
    from contextlib import nullcontext
    from scripts import probe_bounded_hybrid_d2 as probe

    first=json.loads((Path(__file__).parent/'fixtures/vla_retry_before_loop_20261023.json').read_bytes())[0]['request']
    executed=[]
    physics=lambda:{'sim_state':[0.],'counters':{'_elapsed_steps':5*len(executed)}}
    facade=SimpleNamespace(snapshot=physics,
        goal_status=lambda:{'done':False,'satisfied':[bool(executed),False]})
    monkeypatch.setattr(probe,'bind_subtask',lambda *_:(None,None))
    monkeypatch.setattr(probe,'save_checkpoint',lambda *_:({'physics':physics()},{}))
    def execute(_request,decision):
        executed.extend(decision['candidate_ids'])
        return [{'skill':'call_vla','steps_used':5,'outcome':'failure','stop_reason':'task_not_completed'}]
    adapter=SimpleNamespace(details=[],last_chunk={},held=None,hybrid_recovery_budget=0,
        execute=execute,ex=SimpleNamespace(instruction=first['instruction']),
        p=SimpleNamespace(model=object(),env=SimpleNamespace(terminated=False,truncated=False,
            execution_budget=lambda:{'used_sim_steps':5*len(executed)})))
    spec={'mode':'pick','goal_index':0,'source_symbol':'registered_object','target_symbol':None}
    result,_=probe.trial(facade,adapter,SimpleNamespace(rpc=object()),
        SimpleNamespace(measure=lambda *_:nullcontext()),spec,'call_vla',1,tmp_path/'branch',first,
        vla_parameters={'mode':'task','preparation':'in_place','prompt_style':'full_task'})
    assert len(executed)==1 and result['recovery_used']==0
    assert result['reason']=='registered_goal_completed'
    assert result['success'] is False and result['native_task_success'] is False
    assert result['private_goal_satisfied_at_endpoint'] is True
    assert result['private_progress_success'] is True
