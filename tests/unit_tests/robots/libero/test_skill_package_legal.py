"""One frozen public sequence contract for oracle labels and model decoding."""
import copy

import pytest

from rpent.skill_package.contract import legal_after


@pytest.fixture
def public_request():
    candidates = [dict(id='c'+str(i), skill=skill, parameters=params,
        consequences={'collision': collision, 'ik_reachable': reachable})
        for i, (skill, params, collision, reachable) in enumerate([
            ('nudge', {'axis': 'x', 'distance_m': .01}, False, True),
            ('lift', {'anchor_id': 'e1'}, True, True),
            ('descend', {'anchor_id': 'e1'}, False, False),
            ('observe', {'mode': 'refresh'}, False, None),
            ('finish', {}, False, None)])]
    return dict(candidates=candidates, max_actions=4, execution_prefix=None)


def test_public_legality_preserves_order_and_does_not_predict_feasibility(public_request):
    original = copy.deepcopy(public_request)
    assert legal_after(public_request, []) == ('c0', 'c1', 'c2', 'c3', 'c4')
    assert legal_after(public_request, ['c0']) == ('c1', 'c2', 'c3', 'c4')
    assert public_request == original


def test_committed_identity_is_excluded_even_after_id_regeneration(public_request):
    public_request['execution_prefix'] = {'steps': [{**public_request['candidates'][0], 'id': 'previous-id'}]}
    assert legal_after(public_request, []) == ('c1', 'c2', 'c3', 'c4')
    with pytest.raises(ValueError, match='already committed'):
        legal_after(public_request, ['c0'])


@pytest.mark.parametrize('skill', ['observe', 'call_vla', 'finish', 'ask_help'])
def test_only_handoff_steps_end_a_sequence(public_request, skill):
    public_request['candidates'][3]['skill'] = skill
    assert legal_after(public_request, ['c0', 'c3']) == ()
    with pytest.raises(ValueError, match='boundary'):
        legal_after(public_request, ['c3', 'c0'])


def test_public_requested_k_ends_sequence(public_request):
    public_request['max_actions'] = 2
    assert legal_after(public_request, ['c0', 'c1']) == ()
    with pytest.raises(ValueError, match='exceeds'):
        legal_after(public_request, ['c0', 'c1', 'c2'])


@pytest.mark.parametrize('prefix,match', [(['c0', 'c0'], 'repeats'), (['unknown'], 'unknown')])
def test_invalid_prefix_is_not_silently_accepted(public_request, prefix, match):
    with pytest.raises(ValueError, match=match):
        legal_after(public_request, prefix)


def test_duplicate_public_ids_are_rejected(public_request):
    public_request['candidates'].append(copy.deepcopy(public_request['candidates'][0]))
    with pytest.raises(ValueError, match='duplicate'):
        legal_after(public_request, [])
