"""Repair diagnostics retain scope and cannot hand control back to VLA."""
from types import SimpleNamespace

import pytest

from scripts.probe_bounded_hybrid_repair import first_self_chunk, validate_plan


def test_own_layout_fork_uses_the_same_original_train_input_validator(monkeypatch):
    from coordination.bounded_skills_20261016.scripts import run_own_layout_pi_pilot_20261022 as pilot
    from scripts.probe_bounded_hybrid_repair import constructed_original_start

    references = {'generated_state': {'path':'state','sha256':'state-hash'},
        'construction_report': {'path':'report','sha256':'report-hash'},
        'frozen_parent_index': {'path':'train-index','sha256':'index-hash'}}
    case = {'diagnostic': {'domain':'original','kind':'original_fork','own_layout':references}}
    plan = {'training':False,'confirmation':False}
    generated, seen = {'private_layout':'validated'}, []
    def validate(row, registered):
        seen.append((row, registered));return generated, {}
    monkeypatch.setattr(pilot, 'validate_job', validate)
    assert constructed_original_start(case, plan) is generated
    assert seen == [({'kind':'layout_pilot','case':case,**references},plan)]


@pytest.mark.parametrize('domain,kind', [('d2','original_fork'),('original','replay')])
def test_own_layout_fork_cannot_change_evaluation_domains(domain, kind):
    from scripts.probe_bounded_hybrid_repair import constructed_original_start
    with pytest.raises(ValueError, match='original train fork'):
        constructed_original_start({'diagnostic':{'domain':domain,'kind':kind,'own_layout':{}}}, {})


@pytest.mark.parametrize('old_version', ['bounded-skills/3', 'bounded-skills/4'])
def test_scope_diagnostic_migrates_only_the_public_version_header(old_version, monkeypatch):
    from copy import deepcopy

    from scripts.probe_bounded_hybrid_repair import migrate_replay_header
    monkeypatch.setattr('rpent.skill_package.VERSION', 'bounded-skills/5')

    request = {'schema_version': old_version, 'candidates': [{'id': 'same', 'parameters': {'mode': 'pick'}}]}
    adapter = SimpleNamespace(latest_request=deepcopy(request))
    updated = migrate_replay_header(adapter, request)
    assert request['schema_version'] == old_version
    assert updated == adapter.latest_request == request | {'schema_version': 'bounded-skills/5'}
    adapter.latest_request['candidates'][0]['id'] = 'different'
    with pytest.raises(ValueError, match='differs'):
        migrate_replay_header(adapter, request)


def test_schema6_replay_rebuilds_measured_options_after_legacy_runtime_restore():
    from copy import deepcopy

    from rpent.skill_package.progress import PublicProgress
    from scripts.probe_bounded_hybrid_repair import rebuild_schema6_replay

    old = {'schema_version': 'bounded-skills/3', 'candidates': [
        {'id': 'old', 'skill': 'move_to', 'parameters': {'anchor_id': 'e1', 'approach': 'above', 'path': 'over'}}]}
    current = {'schema_version': 'bounded-skills/6', 'candidates': [
        {'id': 'new', 'skill': 'move_to', 'parameters': {'anchor_id': 'e1'}}]}
    memory = object()
    adapter = SimpleNamespace(latest_request=deepcopy(old), memory=memory)
    events = []
    def refresh():
        assert adapter.schema6_v1 and adapter.public_progress.limit == 31
        events.append('fresh_public_measurements')
    def request(**kwargs):
        assert events == ['fresh_public_measurements'] and kwargs == {'k': 4}
        events.append('new_catalog')
        adapter.latest_request = current
        return current
    adapter.refresh, adapter.request = refresh, request
    defaults = {'schema6_v1': True, 'public_progress': PublicProgress(31), '_failed_move_anchors': set()}
    updated = rebuild_schema6_replay(adapter, old, defaults)
    assert updated is current and adapter.memory is memory
    assert old['schema_version'] == 'bounded-skills/3' and old['candidates'][0]['id'] == 'old'
    assert events == ['fresh_public_measurements', 'new_catalog']
    adapter._failed_move_anchors.add('e1')
    assert defaults['_failed_move_anchors'] == set()


def test_scope_diagnostic_rejects_unregistered_schema_migrations():
    from scripts.probe_bounded_hybrid_repair import migrate_replay_header

    for version in ('bounded-skills/1', 'bounded-skills/5', 'bounded-skills/6'):
        request = {'schema_version': version}
        with pytest.raises(ValueError, match='unsupported'):
            migrate_replay_header(SimpleNamespace(latest_request=dict(request)), request)


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


@pytest.mark.parametrize('count', [0, -1, True, 1.5])
def test_repair_rejects_invalid_self_repeat_registration(tmp_path, count):
    value = plan(tmp_path)
    value['cases'][0]['diagnostic']['self_repeats'] = count
    with pytest.raises(ValueError, match='self_repeats'):
        validate_plan(value)


@pytest.mark.parametrize('own_world', [False, True])
@pytest.mark.parametrize('vla_repeats', [3, 10])
def test_original_self_repeats_restore_the_same_branchpoint(tmp_path, monkeypatch, own_world, vla_repeats):
    from contextlib import contextmanager
    from scripts import probe_bounded_hybrid_repair as repair

    facade = SimpleNamespace(goal_status=lambda: {
        'goals': [['on', 'bowl', 'plate']], 'satisfied': [False]})
    request, saved = {}, {}
    adapter = SimpleNamespace(ex=SimpleNamespace(instruction='put the bowl on the plate'),
        request=lambda **_: request)
    constructed = {'private_validated_layout': True} if own_world else None
    monkeypatch.setattr(repair, 'constructed_original_start', lambda *_: constructed)
    runtime_arguments = []
    @contextmanager
    def runtime(*_args, **_kwargs):
        runtime_arguments.append(_kwargs)
        yield facade, adapter, object(), object()
    monkeypatch.setattr(repair.probe, 'runtime', runtime)
    monkeypatch.setattr(repair.probe, 'save_checkpoint', lambda *_args: (saved, {}))
    restored, calls = [], []
    monkeypatch.setattr(repair.probe, 'restore_checkpoint', lambda *args: restored.append(args[-1]))
    def run_trial(_facade, _adapter, _policy, _timings, _spec, method, seed, output, actual, **kwargs):
        assert actual is request
        calls.append((method, seed, output.name))
        return {'success': True, 'decisions': 1}, {}
    monkeypatch.setattr(repair, 'run_trial', run_trial)
    case = {'diagnostic': {'domain': 'original', 'kind': 'original_fork',
        'budget': {}, 'subtask_mode': 'pick', 'trial_seed_base': 1000,
        'self_repeats': 2, 'vla_repeats': vla_repeats}}
    result = repair.evaluate_case(case, {}, tmp_path/'case', {'source_commit': 'test'})
    assert calls == [('call_vla', 1000+j*1000, f'call_vla_{j}')
        for j in range(1, vla_repeats+1)] + [('self', 1000, 'self_0'), ('self', 2000, 'self_1')]
    assert len(restored) == vla_repeats+2 and all(value is saved for value in restored)
    assert len(result['trials']) == vla_repeats+2
    assert runtime_arguments == [{'domain':'original',
        **({'constructed_start':constructed} if own_world else {})}]


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
@pytest.mark.parametrize('include_self', [None, False])
def test_original_fork_reaches_the_registered_second_goal_and_phase_before_branching(
        tmp_path, monkeypatch, prefix_success, include_self):
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
    if include_self is not None:
        case['diagnostic']['include_self'] = include_self
    result = repair.evaluate_case(case, {}, tmp_path/'case', {'source_commit': 'test'})
    if prefix_success:
        assert calls == [('g0:pick', 'self'), ('g0:on', 'self'), ('g1:pick', 'self'),
            ('g1:on', 'call_vla'), ('g1:on', 'call_vla'), ('g1:on', 'call_vla')]+(
                [('g1:on', 'self')] if include_self is not False else [])
        assert result['status'] == 'physical_result' and len(result['prefix']) == 3
    else:
        assert calls == [('g0:pick', 'self')]
        assert result['status'] == 'prefix_not_reached' and result['trials'] == []
