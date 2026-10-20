"""One frozen public sequence contract for oracle labels and model decoding."""
import copy

import pytest

from rpent.skill_package.contract import legal_after


@pytest.mark.parametrize('mode', ['pick','open','close','on','in','task','instruction'])
def test_vla_family_and_binding_requirement_cover_all_finite_invocation_modes(mode):
    from rpent.skill_package.contract import method_family,action_binding_required
    candidate={'skill':'call_vla','parameters':{'mode':mode,'preparation':'in_place',
        'prompt_style':'full_task','seed_variant':2}}
    before=copy.deepcopy(candidate)
    assert method_family(candidate)=='vla'
    assert action_binding_required(candidate)==(mode not in {'task','instruction'})
    assert candidate==before


@pytest.fixture
def public_request():
    candidates = [dict(id='c'+str(i), skill=skill, parameters=params,
        consequences={'collision': collision, 'ik_reachable': reachable, 'screen_scope': 'nonmotion'},
        expected_receipt=[])
        for i, (skill, params, collision, reachable) in enumerate([
            ('nudge', {'axis': 'x', 'distance_m': .01}, False, True),
            ('lift', {'anchor_id': 'e1'}, True, True),
            ('descend', {'anchor_id': 'e1'}, False, False),
            ('observe', {'mode': 'refresh'}, False, None),
            ('finish', {}, False, None)])]
    return dict(candidates=candidates, max_actions=4, execution_prefix=None,
                robot={'held_anchor_id': None}, anchors=[{'id': 'e1'}, {'id': 'e2'}])


def test_public_legality_preserves_order_and_excludes_known_blockers(public_request):
    original = copy.deepcopy(public_request)
    assert legal_after(public_request, []) == ('c0', 'c3', 'c4')
    assert legal_after(public_request, ['c0']) == ('c3', 'c4')
    assert public_request == original


def test_committed_identity_is_excluded_even_after_id_regeneration(public_request):
    public_request['execution_prefix'] = {'steps': [{**public_request['candidates'][0], 'id': 'previous-id'}]}
    assert legal_after(public_request, []) == ('c3', 'c4')
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
    assert legal_after(public_request, ['c0', 'c3']) == ()
    with pytest.raises(ValueError, match='exceeds'):
        legal_after(public_request, ['c0', 'c1', 'c2'])


@pytest.mark.parametrize('prefix', [['c1'], ['c2'], ['c0', 'c1'], ['c1', 'c4']])
def test_blocked_prefix_is_rejected_even_at_k_or_terminal(public_request, prefix):
    public_request['max_actions'] = len(prefix)
    with pytest.raises(ValueError, match='public preconditions'):
        legal_after(public_request, prefix)


@pytest.mark.parametrize('maximum', [1., None])
def test_conditional_transport_uses_public_held_postcondition(public_request, maximum):
    lift = public_request['candidates'][1]
    lift['consequences']['collision'] = False
    lift['expected_receipt'] = [dict(metric='held', anchor_id='e1', minimum=1., maximum=maximum)]
    for cid, skill in [('carry', 'carry_to'), ('lower', 'lower')]:
        public_request['candidates'].append(dict(id=cid, skill=skill, parameters={'target_id': 'e2'},
            consequences={'collision': None, 'ik_reachable': None, 'screen_scope': 'conditional_on_prefix'},
            expected_receipt=[]))
    assert 'carry' not in legal_after(public_request, [])
    assert 'lower' not in legal_after(public_request, ['c0'])
    assert legal_after(public_request, ['c1'])[-2:] == ('carry', 'lower')
    assert legal_after(public_request, ['c1', 'carry'])[-1] == 'lower'
    public_request['candidates'][0]['skill'] = 'set_gripper'
    public_request['candidates'][0]['parameters'] = {'mode': 'open'}
    assert 'carry' not in legal_after(public_request, ['c1', 'c0'])
    public_request['execution_prefix'] = {'steps': [], 'predicted_state': {'robot': {'held_anchor_id': 'e1'}}}
    assert 'carry' in legal_after(public_request, [])


def test_unknown_conditional_action_and_unknown_held_anchor_stay_closed(public_request):
    public_request['robot']['held_anchor_id'] = 'missing'
    public_request['candidates'][0]['consequences']['screen_scope'] = 'conditional_on_prefix'
    assert 'c0' not in legal_after(public_request, [])
    public_request['candidates'][0]['skill'] = 'carry_to'
    assert 'c0' not in legal_after(public_request, [])


@pytest.mark.parametrize('prefix,match', [(['c0', 'c0'], 'repeats'), (['unknown'], 'unknown')])
def test_invalid_prefix_is_not_silently_accepted(public_request, prefix, match):
    with pytest.raises(ValueError, match=match):
        legal_after(public_request, prefix)


def test_duplicate_public_ids_are_rejected(public_request):
    public_request['candidates'].append(copy.deepcopy(public_request['candidates'][0]))
    with pytest.raises(ValueError, match='duplicate'):
        legal_after(public_request, [])
