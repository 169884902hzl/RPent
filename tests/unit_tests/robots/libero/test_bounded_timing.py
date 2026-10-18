"""Timers preserve binding and separate nested work from its caller."""
import copy

import pytest

from robots.libero.bounded_timing import EpisodeTimings


def test_nested_work_is_not_double_counted_and_exception_restores_stack():
    now = [0.]
    timer = EpisodeTimings(clock=lambda: now[0])
    with timer.measure('decision'):
        now[0] = 2.
        with pytest.raises(ValueError), timer.measure('planning'):
            now[0] = 5.
            raise ValueError('diagnostic')
        now[0] = 7.
    report = timer.summary(8.)
    assert report['main_thread_exclusive_s'] == {'planning': 3., 'decision': 4.}
    assert report['main_thread_unattributed_s'] == 1.
    assert report['main_thread_exclusive_by_root_s'] == {'decision': {'planning': 3., 'decision': 4.}}


def test_class_instrumentation_keeps_copied_predictor_bound_to_its_own_state():
    class State:
        value = 1
        def read(self):
            return self.value
    original = State.read
    timer = EpisodeTimings()
    timer.wrap(State, 'read', 'planning')
    try:
        measured = State()
        prediction = copy.copy(measured)
        prediction.value = 9
        assert measured.read() == 1
        assert prediction.read() == 9
    finally:
        timer.close()
    assert State.read is original
