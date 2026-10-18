"""Measured blockers shrink without deleting successor IDs or task-blind options."""
import copy

import pytest

from rpent.skill_package.contract import compact_candidate, committed_candidate_ids, selected, validate
from tests.unit_tests.robots.libero.test_bounded_skills import adapter as adapter
from tests.unit_tests.robots.libero.test_bounded_skills import decision


def test_compression_preserves_ids_order_and_unknown_consequences(adapter):
    adapter.compact_infeasible_candidates_v1 = False
    full = adapter.request()
    candidate = copy.deepcopy(full['candidates'][0])
    assert compact_candidate(candidate) == candidate
    candidate['consequences'].update(collision=None, ik_reachable=None)
    assert compact_candidate(candidate) == candidate
    for blocker in ({'collision': True}, {'ik_reachable': False}):
        blocked = copy.deepcopy(candidate)
        blocked['consequences'].update(blocker)
        small = compact_candidate(blocked)
        assert small['id'] == candidate['id']
        assert small['parameters'] == candidate['parameters']
        assert 'expected_receipt' not in small and 'history' not in small
        request = copy.deepcopy(full)
        request['candidates'][0] = small
        validate(request)


def test_blocked_marker_is_reexpanded_using_the_actual_public_prefix(adapter):
    request = adapter.request()
    movement = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'x', 'distance_m': .02})
    source = copy.deepcopy(request['candidates'][0])
    source['consequences']['collision'] = True
    request['candidates'][0] = compact_candidate(source)
    context = adapter.prefix_context(request, [movement['id']])
    successor = next(c for c in context['candidates'] if c['id'] == source['id'])
    assert successor['consequences']['collision'] is False
    assert 'expected_receipt' in successor
    assert 'expected_steps' in successor['consequences']


@pytest.mark.parametrize('mutation', ['duplicate', 'unknown_held', 'budget', 'boundary'])
def test_execution_prefix_requires_real_anchor_identities_and_budget(adapter, mutation):
    request = adapter.request()
    request['revision'] = 1
    candidate = next(c for c in request['candidates'] if c['skill'] == 'nudge')
    prefix = dict(source_revision=0, source_observation_id='public-0',
        steps=[{key: candidate[key] for key in ('id', 'skill', 'parameters')}],
        predicted_state=dict(robot=copy.deepcopy(request['robot']),
            anchors=copy.deepcopy(request['anchors']), remaining_sim_steps=request['remaining_sim_steps']),
        assumptions=[])
    request['execution_prefix'] = prefix
    validate(request)
    if mutation == 'duplicate':
        prefix['predicted_state']['anchors'].append(copy.deepcopy(request['anchors'][0]))
    elif mutation == 'unknown_held':
        prefix['predicted_state']['robot']['held_anchor_id'] = 'never-measured'
    elif mutation == 'budget':
        prefix['predicted_state']['remaining_sim_steps'] += 1
    else:
        prefix['steps'][0].update(skill='observe', parameters={'mode': 'refresh'})
    with pytest.raises(ValueError):
        validate(request)


def test_committed_actions_are_not_reselected_even_with_a_regenerated_id(adapter):
    request = adapter.request()
    request['revision'] = 1
    candidate = next(c for c in request['candidates'] if c['skill'] == 'nudge')
    request['execution_prefix'] = dict(source_revision=0, source_observation_id='public-0',
        steps=[{key: candidate[key] for key in ('id', 'skill', 'parameters')}],
        predicted_state=dict(robot=copy.deepcopy(request['robot']),
            anchors=copy.deepcopy(request['anchors']), remaining_sim_steps=request['remaining_sim_steps']),
        assumptions=[])
    replacement = copy.deepcopy(candidate)
    replacement['id'] = 'regenerated-id'
    request['candidates'].append(replacement)
    assert committed_candidate_ids(request) == {candidate['id'], 'regenerated-id'}
    for cid in committed_candidate_ids(request):
        with pytest.raises(ValueError, match='already committed'):
            selected(request, decision(request, [cid]))
    context = adapter.prefix_context(request, [])
    assert not committed_candidate_ids(request) & {c['id'] for c in context['candidates']}
