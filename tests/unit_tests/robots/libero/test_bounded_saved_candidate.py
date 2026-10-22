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
