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
