"""Repair diagnostics retain scope and cannot hand control back to VLA."""
from types import SimpleNamespace

import pytest

from scripts.probe_bounded_hybrid_repair import first_self_chunk, validate_plan


def test_scope_diagnostic_migrates_only_the_public_version_header():
    from copy import deepcopy

    from scripts.probe_bounded_hybrid_repair import migrate_replay_header

    request = {'schema_version': 'bounded-skills/3', 'candidates': [{'id': 'same', 'parameters': {'mode': 'pick'}}]}
    adapter = SimpleNamespace(latest_request=deepcopy(request))
    updated = migrate_replay_header(adapter, request)
    assert request['schema_version'] == 'bounded-skills/3'
    assert updated == adapter.latest_request == request | {'schema_version': 'bounded-skills/4'}
    adapter.latest_request['candidates'][0]['id'] = 'different'
    with pytest.raises(ValueError, match='differs'):
        migrate_replay_header(adapter, request)


def plan(tmp_path):
    import json
    from scripts.probe_bounded_hybrid_d2 import reference

    path = tmp_path/'calibration.json'
    path.write_text(json.dumps({'opening_calibration': {}, 'grip_site_geometry': {},
        'robot_rigid_transform_validation': {}}))
    return {'evaluation':'hybrid_repair', 'training':False, 'confirmation':False,
        'cases':[{'episode':{'suite':'libero_spatial_swap','task':2,'seed':40},
            'grasp_measurement_calibration': reference(path),
            'diagnostic':{'domain':'d2','budget':{'no_progress_blocks':None,'max_controls':220}}}]}


def test_repair_accepts_registered_d2_replays_but_never_test_tasks_or_training(tmp_path):
    value = plan(tmp_path)
    validate_plan(value)
    value['cases'][0]['episode']['task'] = 5
    with pytest.raises(ValueError):
        validate_plan(value)
    value = plan(tmp_path)
    value['training'] = True
    with pytest.raises(ValueError):
        validate_plan(value)


def test_self_continuation_cannot_silently_call_vla_again(tmp_path):
    request = {'candidates':[{'id':'vla','skill':'call_vla'}]}
    rpc = object()
    policy = SimpleNamespace(rpc=rpc, choose=lambda _: {'candidate_ids':['vla']})
    adapter = SimpleNamespace(request=lambda **_:request,
        p=SimpleNamespace(env=SimpleNamespace(execution_budget=lambda:{'used_sim_steps':0})))
    with pytest.raises(ValueError, match='bounded skills'):
        first_self_chunk(object(), adapter, policy, {}, tmp_path)
    assert policy.rpc is rpc


def test_original_microwave_fork_accepts_its_libero90_task_only(tmp_path):
    value = plan(tmp_path)
    value['cases'][0] = {**value['cases'][0], 'episode': {'suite': 'libero_90', 'task': 35, 'seed': 0},
        'diagnostic': {'domain': 'original', 'budget': {}}}
    validate_plan(value)
    value['cases'][0]['episode']['task'] = 90
    with pytest.raises(ValueError):
        validate_plan(value)


def test_original_saved_start_is_never_admitted_to_d2(tmp_path):
    value = plan(tmp_path)
    value['cases'][0]['diagnostic'].update(kind='original_fork', original_subtask_start={})
    with pytest.raises(ValueError, match='cannot be used for D2'):
        validate_plan(value)


def test_saved_original_start_remeasures_instead_of_importing_private_object_positions(tmp_path, monkeypatch):
    import pickle
    from dataclasses import replace

    from robots.libero.v5_state import Entity
    from scripts import probe_bounded_hybrid_repair as repair
    from tests.unit_tests.robots.libero.test_bounded_motion import FakePrimitives

    prior = Entity('e1', 'cup', (.1, .1, .9), (.08, .08, .88), (.12, .12, .92), True, 50)
    missing = replace(prior, id='e2', visible=False)
    old = SimpleNamespace(scene=SimpleNamespace(entities={'e1': prior, 'e2': missing}),
        held='e1', p=SimpleNamespace(_bounded_control_index=123))
    monkeypatch.setattr('robots.libero.bounded_offline_labels.load_annotation_state',
        lambda *args: {'adapter': old})
    physics = {'actuator_state': {'model': {'private_object_position': 999}}}
    path = tmp_path/'physics.pkl'
    path.write_bytes(pickle.dumps(physics))
    facade = SimpleNamespace(restore=lambda value: {'public_sensor': True},
        snapshot=lambda: {'actuator_state': {**physics['actuator_state'], 'observation_state': {}}})
    primitives = FakePrimitives()
    primitives.env.raw_obs = lambda: {'robot0_eef_pos': [0., 0., 1.],
        'robot0_eef_quat': [0., 0., 0., 1.], 'robot0_gripper_qpos': [.01, -.01],
        'robot0_joint_pos': [0.]*7}
    primitives.set_obs = lambda obs: None
    scene = SimpleNamespace(entities={}, _ids=['e1', 'e2', 'e3'])
    adapter = SimpleNamespace(p=primitives, scene=scene, held=None, active=None,
        ex=SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=1))),
        holding_aperture=lambda _: (True, {}), preparation='original familiar pose',
        _instance_cache={}, _screen_cache={})
    def refresh():
        assert scene.entities == {'e1': prior, 'e2': missing}
        scene.entities['e1'] = replace(prior, xyz=(.2, .1, .9), source_step=1)
    adapter.refresh = refresh
    adapter._capture_payload_reference = lambda key: {'measured_id': key}
    result = repair.restore_original_subtask(facade, adapter, object(), {
        'physics': {'path': str(path)}, 'annotation': {'path': 'annotation', 'sha256': 'fixed'}})
    assert scene.entities['e1'].xyz == (.2, .1, .9)
    assert list(scene.entities) == ['e1'] and scene._ids == ['e3']
    assert adapter.held == adapter.active == 'e1'
    assert adapter.payload_reference == {'measured_id': 'e1'}
    assert adapter.preparation == 'original familiar pose'
    assert primitives._bounded_control_index == 123 and adapter.gripper_command == 1.
    assert result['same_captured_physics'] is True
    assert result['simulation_object_coordinates_imported_to_public_state'] is False


def test_saved_start_selects_the_first_matching_logged_phase_and_keeps_missing_explicit():
    from coordination.bounded_skills_20261016.scripts.prepare_original_saved_forks_20261020 import select_start

    states = {'0': (0, None), '1': (1, None), '2': (1, 'held'), '3': (1, None)}
    def load(ref):
        goal, held = states[ref['path']]
        return {'private_status': {'satisfied': [goal == 1, False],
                'goals': [['on', 'first', 'plate'], ['on', 'second', 'plate']]},
            'binding': {'_bindings': {'second': 'held'}},
            'adapter': SimpleNamespace(held=held)}
    rows = [{'index': i, 'private_prefix_annotation_state': {'path': str(i)},
        'private_pre_execution_snapshot': {'path': f'physics{i}'}} for i in range(4)]
    wanted = {'goal_index': 1, 'subtask_mode': 'pick'}
    selected = select_start(rows, wanted, load)
    assert selected['decision_index'] == 1 and selected['physics']['path'] == 'physics1'
    assert select_start(rows, {**wanted, 'subtask_mode': 'on'}, load)['decision_index'] == 2
    with pytest.raises(ValueError, match='no logged'):
        select_start(rows[:1], wanted, load)


def test_holding_another_object_is_not_a_placement_start_for_the_requested_source():
    from coordination.bounded_skills_20261016.scripts.prepare_original_saved_forks_20261020 import recorded_phase

    state = {'private_status': {'goals': [['on', 'yellow_cup', 'plate']]},
        'binding': {'_bindings': {'yellow_cup': 'yellow'}}, 'adapter': SimpleNamespace(held='white')}
    assert recorded_phase(state, 0) == 'pick'
    state['adapter'].held = 'yellow'
    assert recorded_phase(state, 0) == 'on'


@pytest.mark.parametrize('prefix_success', [False, True])
def test_original_fork_reaches_the_registered_second_goal_and_phase_before_branching(tmp_path, monkeypatch, prefix_success):
    from contextlib import contextmanager

    from scripts import probe_bounded_hybrid_repair as repair

    goals = [['on', 'white_cup', 'left_plate'], ['on', 'yellow_cup', 'right_plate']]
    satisfied = [False, False]
    facade = SimpleNamespace(goal_status=lambda: {'goals': goals, 'satisfied': satisfied})
    adapter = SimpleNamespace(ex=SimpleNamespace(instruction='put the cups on their plates'),
        request=lambda **_: {})
    @contextmanager
    def runtime(*args, **kwargs):
        yield facade, adapter, object(), object()
    monkeypatch.setattr(repair.probe, 'runtime', runtime)
    monkeypatch.setattr(repair.probe, 'save_checkpoint', lambda *args: ({}, {}))
    monkeypatch.setattr(repair.probe, 'restore_checkpoint', lambda *args: None)
    calls = []
    def run_trial(facade, adapter, policy, timings, spec, method, seed, output, request, **kwargs):
        calls.append((spec['id'], method))
        if spec['mode'] == 'on' and prefix_success:
            satisfied[spec['goal_index']] = True
        return {'success': prefix_success, 'decisions': 1}, {}
    monkeypatch.setattr(repair, 'run_trial', run_trial)
    case = {'diagnostic': {'domain': 'original', 'kind': 'original_fork',
        'budget': {}, 'subtask_mode': 'on', 'goal_index': 1, 'trial_seed_base': 1000}}
    result = repair.evaluate_case(case, {}, tmp_path/'case', {'source_commit': 'test'})
    if prefix_success:
        assert calls == [('g0:pick', 'self'), ('g0:on', 'self'), ('g1:pick', 'self'),
            ('g1:on', 'call_vla'), ('g1:on', 'call_vla'), ('g1:on', 'call_vla'), ('g1:on', 'self')]
        assert result['status'] == 'physical_result' and len(result['prefix']) == 3
    else:
        assert calls == [('g0:pick', 'self')]
        assert result['status'] == 'prefix_not_reached' and result['trials'] == []
