"""New layout states retain real capture identity and original train lineage."""
import copy
import json

import pytest

from coordination.bounded_skills_20261016.scripts import prepare_own_layout_measured_CPU_20261022 as prepare


def inputs(tmp_path):
    def store(name, value):
        p = tmp_path / name
        p.write_text(json.dumps(value))
        return prepare.reference(p)
    bddl = store('original.bddl', {'original_task': 'put bowl on plate'})
    report = {'parent_id': 'train_parent', 'original_bddl': bddl,
        'layout': {'parent': {'suite': 'libero_spatial', 'task': 0, 'seed': 10,
            'split': 'train', 'initial_state_sha256': 'official_parent_hash'},
            'PRO': False, 'D2': False, 'confirmation': False}}
    point = {'index': 2, 'prefix_decisions': 3, 'phase': 'public_held',
        'label_eligible': True, 'subtask': {'mode': 'on', 'goal_index': 0},
        'layout_seed': 11020600, 'source_commit': 'capture_revision',
        'confirmation': False,
        'construction_report': store('construction.json', report),
        'frozen_parent_index': store('parents.json', {'parents': {'train_parent': {'split': 'train'}}}),
        'case': {'name': 'bowl_layout', 'episode': {'suite': 'libero_spatial', 'task': 0, 'seed': 10},
            'category': 'bowl_transfer', 'state_sha256': 'authored_world_hash', 'bddl': bddl}}
    for key in ('physics', 'annotation', 'generated_state', 'checkpoint'):
        point[key] = store(key, {'actual_capture': key})
    default = {'cases': [{'diagnostic': {'budget': {'max_controls': 520}}}]}
    return point, default


def test_measured_branches_use_actual_middle_capture_not_parent_state(tmp_path):
    point, default = inputs(tmp_path)
    point['annotation'].update(version='bounded-annotation/1', model_visible=False)
    point['checkpoint']['physics_sha256'] = point['physics']['sha256']
    case = prepare.measured_case(point, default, 0)
    assert case['state_sha256'] == 'official_parent_hash'
    assert case['source_training_parent_ids'] == ['train_parent']
    d = case['diagnostic']
    assert d['original_subtask_start']['physics'] == point['physics']
    assert d['original_subtask_start']['annotation'] == point['annotation']
    assert d['own_layout']['generated_state'] == point['generated_state']
    assert case['saved_start_phase'] == 'public_held'
    assert d['subtask_mode'] == 'on' and d['self_repeats'] == 2
    assert [v['name'] for v in d['vla_variants']] == ['in_place', 'initial_pose', 'full_task']
    assert 'diagnostic' not in point['case']


def test_edited_capture_cannot_acquire_measured_label(tmp_path):
    point, default = inputs(tmp_path)
    from pathlib import Path
    Path(point['physics']['path']).write_text('different state')
    with pytest.raises(ValueError, match='captured input changed'):
        prepare.measured_case(point, default, 0)


def test_test_or_confirmation_lineage_is_not_admitted(tmp_path):
    point, default = inputs(tmp_path)
    from pathlib import Path
    p = Path(point['frozen_parent_index']['path'])
    p.write_text(json.dumps({'parents': {'train_parent': {'split': 'init_holdout'}}}))
    point['frozen_parent_index'] = prepare.reference(p)
    with pytest.raises(ValueError, match='original train lineage'):
        prepare.measured_case(point, default, 0)
    point, default = inputs(tmp_path)
    changed = copy.deepcopy(point)
    changed['confirmation'] = True
    with pytest.raises(ValueError, match='original train lineage'):
        prepare.measured_case(changed, default, 0)
