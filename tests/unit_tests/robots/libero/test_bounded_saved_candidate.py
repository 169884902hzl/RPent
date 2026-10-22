"""A measurement must execute the model's exact option, not a subtask rewrite."""
import copy

import pytest

from scripts.evaluate_bounded_saved_candidate import digest, frozen_choice_request


def frozen_case():
    candidate = {'id': 'selected', 'skill': 'call_vla',
        'parameters': {'anchor_id': 'bowl', 'mode': 'pick', 'preparation': 'in_place'}}
    request = {'candidates': [candidate], 'instruction': 'place the bowl on the plate'}
    contract = {'subtask': {'mode': 'on'}}
    query = {'candidate_id': 'selected', 'candidate': copy.deepcopy(candidate),
        'prefix': [], 'snapshot': {'sha256': 'snapshot'}, 'training_admission': False,
        'evaluation_only': True, 'outcome_contract': contract,
        'binding': {'request_sha256': digest(request), 'outcome_contract_sha256': digest(contract),
            'snapshot_sha256': 'snapshot', 'prefix': []}}
    return query, {'request': request}


def test_pick_selected_for_an_on_outcome_keeps_its_original_mode():
    query, saved = frozen_case()
    before = copy.deepcopy(saved)
    request, selected = frozen_choice_request(query, saved)
    assert request == saved['request'] and saved == before
    assert selected['parameters']['mode'] == 'pick'
    assert query['outcome_contract']['subtask']['mode'] == 'on'
    selected['parameters']['mode'] = 'in'
    assert saved == before


@pytest.mark.parametrize('changed', ['request', 'contract', 'snapshot', 'parameters'])
def test_changed_frozen_binding_never_acquires_a_measurement(changed):
    query, saved = frozen_case()
    if changed == 'request':
        saved['request']['instruction'] = 'changed'
    elif changed == 'contract':
        query['outcome_contract']['subtask']['mode'] = 'pick'
    elif changed == 'snapshot':
        query['snapshot']['sha256'] = 'replacement-context'
    else:
        query['candidate']['parameters']['mode'] = 'on'
    with pytest.raises(ValueError):
        frozen_choice_request(query, saved)


def test_return_packet_keeps_exact_binding_and_three_raw_failures(tmp_path):
    import json
    from coordination.bounded_skills_20261016.scripts.export_onpolicy_measurements_CPU_20261023 import measured_row
    from coordination.bounded_skills_20261016.scripts.export_original_schema6_measured_CPU_20261021 import reference
    query, saved = frozen_case()
    saved['request']['anchors'] = [{'id': 'bowl'}]
    query['public_request'] = saved['request']
    query['binding'].update(request_sha256=digest(saved['request']), source_revision='old-source')
    query.update(query_id='query', record_id='old-record', record_aliases=['old-record'],
        source_episode_id='episode', split='holdout', requested_valid_repeats=3)
    trials = []
    for seed in range(3):
        directory = tmp_path/str(seed)
        directory.mkdir()
        result = {'binding': query['binding'], 'query_id': 'query', 'candidate_id': 'selected',
            'candidate_parameters': query['candidate']['parameters'], 'source_revision': 'old-source',
            'seed': seed, 'status': 'closed', 'success': False, 'reason': 'preparation_rejected',
            'sim_steps': 0, 'wall_s': 1., 'private_metrology_s': 0., 'vla_inputs': []}
        path = directory/'summary.json'
        path.write_text(json.dumps(result))
        (directory/'choices.jsonl').write_text(json.dumps({'request': saved['request'],
            'decision': {'candidate_ids': ['selected']}, 'execution_details': []})+'\n')
        trials.append({'result': result, 'summary': reference(path)})
    report = {'binding': query['binding'], 'query_id': 'query', 'candidate': query['candidate'],
        'case': {'category': 'bowl'}, 'trials': trials}
    row = measured_row(query, report, 'policy-hash')
    assert row['binding'] == query['binding'] and row['record_id'] == 'old-record'
    assert len(row['branches'][0]['trials']) == 3 and row['unknown_trials'] == []
    assert all(t['success'] is False and t['sim_steps'] == 0 for t in row['branches'][0]['trials'])
    assert row['training_admission'] is False
    report['binding'] = dict(query['binding'], snapshot_sha256='new-context')
    with pytest.raises(ValueError, match='context changed'):
        measured_row(query, report, 'policy-hash')
