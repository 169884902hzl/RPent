"""Human assistance is an explicit public capability, never a task option."""
import copy

import pytest

from robots.libero.bounded_async import public_model_request
from rpent.skill_package.contract import legal_after
from tests.unit_tests.robots.libero.test_bounded_skills import adapter


@pytest.mark.parametrize('available', [False, True])
def test_measured_request_and_model_view_agree_with_human_capability(adapter, available):
    adapter.human_available = available
    request = adapter.request(k=4)
    assert request['human_available'] is available
    candidates = [c for c in request['candidates'] if c['skill'] == 'ask_help']
    assert bool(candidates) is available
    assert public_model_request(request)['human_available'] is available
    if available:
        assert candidates[0]['id'] in legal_after(request, [])


@pytest.mark.parametrize('available', [None, False])
def test_absent_or_unavailable_assistance_is_not_legal_even_at_stagnation(adapter, available):
    adapter.human_available = True
    request = copy.deepcopy(adapter.request(k=4))
    help_id = next(c['id'] for c in request['candidates'] if c['skill'] == 'ask_help')
    if available is None:
        request.pop('human_available')
    else:
        request['human_available'] = available
    request['progress'] = {'limit': 1, 'stagnant_decisions': 1, 'loop_detected': True}
    legal = legal_after(request, [])
    assert help_id not in legal
    assert {c['skill'] for c in request['candidates'] if c['id'] in legal} == {'finish'}
    with pytest.raises(ValueError, match='public preconditions'):
        legal_after(request, [help_id])
