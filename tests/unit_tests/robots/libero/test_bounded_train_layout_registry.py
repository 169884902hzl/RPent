"""Permanent layout geometry is consumed without releasing unexecuted rows."""
import hashlib
import json

import pytest

from scripts.generate_bounded_train_layouts import confirmation_geometry


def test_native_witness_uses_last_saved_control_not_terminal_summary():
    from scripts.generate_bounded_train_layouts import saved_control_rows
    row = {'private_pre_execution_snapshot': {'path': 'actual_snapshot'},
        'execution_details': [{'execution': {'trace': [{'action': [0.]*7}]}}]}
    assert saved_control_rows([{'kind': 'header'}, row, {'success': True}]) == [row]
    with pytest.raises(ValueError, match='no saved physical'):
        saved_control_rows([{'success': True}])


def test_cpu_constructor_keeps_physics_and_proprioception_without_rendered_camera_buffers(monkeypatch):
    from types import SimpleNamespace
    from scripts import generate_bounded_train_layouts as generator
    captured = []
    monkeypatch.setattr(generator, 'restore_actuators', lambda env, state: captured.append(state))
    applied = []
    env = SimpleNamespace(env=SimpleNamespace(_observables={'robot0_eef_pos': object()}),
        sim=SimpleNamespace(set_state_from_flattened=applied.append))
    sensors = {'observables': {'robot0_eef_pos': {'value': [1., 2., 3.]},
        'agentview_image': {'value': [[0, 0, 0]]}},
        'cache': {'robot0_eef_pos': [1., 2., 3.], 'agentview_image': [[0, 0, 0]]}}
    state = {'integration': 'exact', 'native_data': 'exact', 'rng': 'exact',
        'observation_state': sensors}
    assert generator.restore(env, {'sim_state': [7.], 'actuator_state': state}) == ['agentview_image']
    assert applied == [[7.]] and captured[0]['integration'] == captured[0]['native_data'] == 'exact'
    assert set(captured[0]['observation_state']['observables']) == {'robot0_eef_pos'}
    assert 'agentview_image' in sensors['observables']
    env.env._observables['unrecorded_joint'] = object()
    with pytest.raises(ValueError, match='proprioceptive observable identity'):
        generator.restore(env, {'sim_state': [7.], 'actuator_state': state})


def test_collision_surface_overrides_incorrect_arena_offset_and_xy_origin():
    from types import SimpleNamespace
    import numpy as np
    from scripts.generate_bounded_train_layouts import construction_support

    # Real rejected cup constructor: arena offset z=.41; collision top=.43676.
    domain = SimpleNamespace(workspace_name='living_room_table',
        workspace_offset=(0., 0., .41), living_room_table_full_size=(.7, 1.6, .024))
    model = SimpleNamespace(ngeom=2, geom_type=np.array([6, 6]),
        geom_bodyid=np.array([1, 2]), body_id2name=lambda i:
            {1: 'living_room_table_col', 2: 'unrelated_obstacle'}[i],
        geom_contype=np.ones(2), geom_conaffinity=np.ones(2),
        geom_size=np.array([[.01184, .44432, .67171], [2., 2., 2.]]))
    rotation = np.array([[0., -1., 0.], [0., 0., 1.], [-1., 0., 0.]])
    data = SimpleNamespace(geom_xmat=np.array([rotation.ravel(), np.eye(3).ravel()]),
        geom_xpos=np.array([[-.25, .05239, .42492], [0., 0., 1.]]))
    support = construction_support(SimpleNamespace(env=domain,
        sim=SimpleNamespace(model=model, data=data)))
    assert support['source'] == 'original_workspace_collision_box_top'
    assert np.allclose(support['lower_m'], [-.69432, -.61932, .41308])
    assert np.allclose(support['upper_m'], [.19432, .72410, .43676])


@pytest.mark.parametrize('workspace', ['main_table', 'kitchen_table', 'living_room_table'])
def test_construction_uses_the_actual_workspace_dimension_attribute(workspace):
    from types import SimpleNamespace
    from scripts.generate_bounded_train_layouts import construction_support
    name = 'table_full_size' if workspace == 'main_table' else workspace+'_full_size'
    domain = SimpleNamespace(workspace_name=workspace, workspace_offset=(0., 0., .9),
        **{name: (1., 1.2, .05)})
    support = construction_support(SimpleNamespace(env=domain))
    assert support['upper_m'] == [.5, .6, .9]
    assert support['lower_m'] == [-.5, -.6, .85]


def test_floor_uses_collision_plane_and_initial_regions_not_goal_region():
    from types import SimpleNamespace
    import numpy as np
    from scripts.generate_bounded_train_layouts import construction_support
    domain = SimpleNamespace(workspace_name='floor', workspace_offset=(0., 0., -.035),
        parsed_problem={'initial_state': [['on', 'item', 'initial']],
            'regions': {'initial': {'target': 'floor', 'ranges': [[-.2, -.1, .2, .3]]},
                'goal': {'target': 'floor', 'ranges': [[3., 3., 4., 4.]]}}})
    model = SimpleNamespace(ngeom=1, geom_id2name=lambda _: 'floor',
        geom_type=[0], geom_size=np.array([[3., 3., .125]]))
    support = construction_support(SimpleNamespace(env=domain,
        sim=SimpleNamespace(model=model, data=SimpleNamespace(geom_xpos=np.zeros((1, 3))))))
    np.testing.assert_allclose(support['lower_m'], [-.32, -.22, -.125])
    np.testing.assert_allclose(support['upper_m'], [.32, .42, 0.])


@pytest.mark.parametrize('split,domain,same_seed,expected', [
    ('train', 'original', True, True), ('init_holdout', 'original', True, False),
    ('train', 'd2', True, False), ('train', 'original', False, False)])
def test_witness_replays_recorded_native_success_only_from_original_train(tmp_path, split, domain, same_seed, expected):
    import pickle
    from robots.libero.bounded_hybrid_diagnostic import snapshot_digest
    from scripts.generate_bounded_train_layouts import training_witness_controls
    case = {'name': 'same_original_task', 'episode': {'suite': 'libero_object', 'task': 0, 'seed': 2},
        'diagnostic': {'domain': domain}, 'source_training_parent_ids': ['original-train']}
    physics = {'sim_state': [0., 1.], 'actuator_state': {}}
    folder = tmp_path/case['name']; folder.mkdir()
    (folder/'private_branchpoint.pkl').write_bytes(pickle.dumps({'physics': physics}))
    choices = pin(tmp_path/'choices.jsonl', {'execution_details': [
        {'execution': {'trace': [{'action': [0., 0., .01, 0., 0., 0., 1.]}]}}]})
    worker = pin(tmp_path/'worker_summary.json', {'case': case, 'result': {'trials': [{
        'trial_seed': 7, 'vla_variant': {'name': 'full_task'}, 'success': True,
        'truth_source': 'unchanged_native_task_completion', 'choices': choices,
        'initial_physics_sha256': snapshot_digest(physics)}]}})
    reference = {'worker': worker, 'trial_seed': 7}
    parents = {'original-train': {'split': split}}
    if not same_seed:
        case = {**case, 'episode': {**case['episode'], 'seed': 3}}
    if expected:
        restored, controls, provenance = training_witness_controls(reference, case, parents)
        assert restored == physics and controls == [[0., 0., .01, 0., 0., 0., 1.]]
        assert provenance['choices'] == choices
    else:
        with pytest.raises(ValueError, match='same original train task'):
            training_witness_controls(reference, case, parents)


def pin(path, value):
    raw = json.dumps(value).encode()
    path.write_bytes(raw)
    return {'path':str(path), 'sha256':hashlib.sha256(raw).hexdigest()}


def registry(tmp_path):
    pool = pin(tmp_path/'pool.json', {'permanent_training_exclusion':True,
        'rows':[{'permanent_training_exclusion':True, 'status':status,
            'preparation_provenance':{'settled_geometry':{'bottle_1':[x,0.,.1]}}}
            for status,x in [('executed',0.),('unexecuted',.2),('invalid',.4)]]})
    moka = pin(tmp_path/'moka.json', {'records':[{'permanent_training_exclusion':True,
        'layout_parameters':{'rule':{'moved_object_symbol':'moka_pot_1'}},
        'settled_moka_xy_m':[.1,.2]}]})
    return pin(tmp_path/'registry.json', {
        'fiveclass_pool_reconciliation':{'pool_metadata':[{'pool':pool}]},
        'source_index':{'moka100':moka},
        'counts':{'official_original_confirmation_states':665}}), pool


def test_all_reserved_geometry_is_kept_and_partial_coverage_is_explicit(tmp_path):
    ref, _ = registry(tmp_path)
    layouts, evidence = confirmation_geometry(ref)
    assert layouts == [{'bottle_1':[0.,0.,.1]}, {'bottle_1':[.2,0.,.1]},
        {'bottle_1':[.4,0.,.1]}, {'moka_pot_1':[.1,.2,0.]}]
    assert evidence['geometry_records_checked'] == 4
    assert evidence['original_confirmation_geometry_records_missing'] == 665
    assert evidence['coverage_complete'] is False
    assert evidence['training_admission'] is False


def test_pool_bytes_cannot_change_under_a_registered_hash(tmp_path):
    ref, pool = registry(tmp_path)
    from pathlib import Path
    Path(pool['path']).write_text('{}')
    with pytest.raises(ValueError, match='registered original source changed'):
        confirmation_geometry(ref)


def test_known_original_geometry_requires_exact_registered_state_set(tmp_path):
    ref, _ = registry(tmp_path)
    from pathlib import Path

    data = json.loads(Path(ref['path']).read_bytes())
    plan = pin(tmp_path/'original_plan.json', {'cases': [{'state_sha256': 'state-a'}]})
    data['original665'] = {'source_plans': [plan]}
    data['counts']['official_original_confirmation_states'] = 1
    ref = pin(tmp_path/'registry.json', data)
    row = {'state_sha256': 'state-a', 'permanent_training_exclusion': True,
        'body_origins_world_m': {'bottle_1': [.3, .4, .1]}}
    raw = (json.dumps(row)+'\n').encode()
    path = tmp_path/'original_geometry.jsonl'
    path.write_bytes(raw)
    summary = {'registry': ref, 'controls_executed': 0,
        'data': {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}}
    original = pin(tmp_path/'original_summary.json', summary)
    layouts, evidence = confirmation_geometry(ref, original)
    assert layouts[-1] == row['body_origins_world_m']
    assert evidence['known_original_geometry_records_checked'] == 1
    assert evidence['original_confirmation_geometry_records_missing'] == 0
    assert evidence['training_admission'] is False and evidence['coverage_complete'] is False
    path.write_bytes(raw+raw)
    summary['data']['sha256'] = hashlib.sha256(raw+raw).hexdigest()
    duplicate = pin(tmp_path/'duplicate_summary.json', summary)
    with pytest.raises(ValueError, match='incomplete or duplicated'):
        confirmation_geometry(ref, duplicate)
