"""Native success stops before sensing; failure does not remove all retries."""
import copy
import pytest

from rpent.skill_package.feedback import FeedbackConfig, SuccessFeedback, TaskAlreadySucceeded, configure
from rpent.skill_package.contract import FailureMemory, legal_after, validate, identity
from tests.unit_tests.robots.libero.test_bounded_skills import adapter  # noqa: F401


def test_success_read_once_stops_before_perception(adapter, monkeypatch):
    reads = []
    feedback = SuccessFeedback(FeedbackConfig(True, False), native_success=lambda: reads.append(1) or True)
    configure(adapter, feedback, aggressive=True)
    monkeypatch.setattr(adapter, '_refresh_held_measurement', lambda: pytest.fail('sensing after success'))
    with pytest.raises(TaskAlreadySucceeded):
        adapter.request()
    assert len(reads) == feedback.reads == 1


@pytest.mark.parametrize('a,b', [(False, False), (True, False), (False, True), (True, True)])
def test_feedback_switches_independent_and_no_false_finish(adapter, a, b):
    predicates = [{'id': 'g0', 'predicate': 'on', 'arguments': ['box', 'plate'], 'satisfied': False}]
    feedback = SuccessFeedback(FeedbackConfig(a, b), native_success=lambda: False, subgoals=lambda: predicates)
    configure(adapter, feedback, aggressive=True)
    request = adapter.request(k=1)
    validate(request)
    assert ('task_success' in request) == a and ('subgoal_status' in request) == b
    assert request['schema_version'] == 'bounded-skills/8'
    legal = set(legal_after(request, []))
    finish = next(c for c in request['candidates'] if c['skill'] == 'finish')
    assert (finish['id'] in legal) != a
    assert not any(c['skill'] == 'ask_help' for c in request['candidates'])
    invalid = copy.deepcopy(request)
    invalid['feedback']['task_success'] = not a
    with pytest.raises(ValueError):
        validate(invalid)


def test_aggressive_stagnation_keeps_measured_actions(adapter):
    configure(adapter, SuccessFeedback(FeedbackConfig(True), native_success=lambda: False), aggressive=True)
    request = adapter.request()
    request['progress'] = {'version': 'public-goal-progress/2', 'stagnant_decisions': 100,
                           'limit': 11, 'loop_detected': True}
    legal = set(legal_after(request, []))
    assert any(c['id'] in legal and c['skill'] not in {'finish', 'ask_help'} for c in request['candidates'])


def test_failure_history_remains_visible_without_permanent_retry_block():
    memory = FailureMemory()
    candidate = {'id': 'one', 'skill': 'call_vla', 'parameters': {'mode': 'task'}}
    for _ in range(3):
        memory.record(candidate, 'failure', 'block_budget')
    assert memory.apply([candidate]) == []
    retry = memory.apply([candidate], keep_retryable=True)
    assert retry[0]['recent_failures'] == 3 and memory.counts[identity(candidate)] == 3
