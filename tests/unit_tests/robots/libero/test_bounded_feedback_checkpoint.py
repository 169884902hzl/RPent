# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""A live success callback is a runtime resource, not checkpoint payload."""
import pickle
from types import SimpleNamespace

import pytest

from robots.libero.bounded_hybrid_diagnostic import capture_runtime, restore_runtime
from rpent.skill_package.feedback import FeedbackConfig, SuccessFeedback, TaskAlreadySucceeded, configure


def test_feedback_checkpoint_pickles_and_restores_current_host_callback():
    p=SimpleNamespace(_bounded_control_index=7)
    scene=SimpleNamespace(toolkit=object(),rpc=object(),entities={'e1':[1]})
    adapter=SimpleNamespace(ex=object(),p=p,scene=scene,receipts=[],held='e1')
    policy=SimpleNamespace(binding=SimpleNamespace(rpc=object()),private_trace=[])
    configure(adapter,SuccessFeedback(FeedbackConfig(True),native_success=lambda:False),aggressive=True)
    adapter.success_feedback.read()
    saved=pickle.loads(pickle.dumps(capture_runtime(adapter,policy),protocol=5))
    assert 'success_feedback' not in saved['adapter']
    native=[False]
    current=SuccessFeedback(FeedbackConfig(False),native_success=lambda:native[0])
    adapter.success_feedback=current
    restore_runtime(adapter,policy,saved)
    assert adapter.success_feedback is current
    assert current.config==FeedbackConfig(True) and current.reads==1
    native[0]=True
    with pytest.raises(TaskAlreadySucceeded):current.read()
    assert adapter.held=='e1' and p._bounded_control_index==7


def test_checkpoint_rebinds_native_and_subgoal_feedback_to_restored_host(tmp_path):
    from scripts import probe_bounded_hybrid_d2 as probe

    class Facade:
        def __init__(self):
            self._native_success_events = []
            self.success = False
            self.satisfied = False
            worker = SimpleNamespace(env_call=lambda _: self.success)
            self._env = SimpleNamespace(env=SimpleNamespace(workers=[worker]))

        def snapshot(self):
            return {'sim_state': [1.], 'native_success_event_count': 0}

        def restore(self, state):
            return {'restored': True}

        def goal_status(self):
            return {'goals': [('in', 'object', 'region')], 'satisfied': [self.satisfied]}

    def runtime():
        primitive = SimpleNamespace(
            env=SimpleNamespace(terminated=False, truncated=False), set_obs=lambda _: None)
        scene = SimpleNamespace(toolkit=object(), rpc=object(), entities={})
        adapter = SimpleNamespace(ex=object(), p=primitive, scene=scene, held='e1', receipts=[])
        policy = SimpleNamespace(binding=SimpleNamespace(rpc=object()), private_trace=[])
        return adapter, policy

    original = Facade()
    adapter, policy = runtime()
    configure(adapter, SuccessFeedback(FeedbackConfig(True, True),
        native_success=lambda: original.success, subgoals=lambda: []), aggressive=True)
    adapter.success_feedback.read()
    path = tmp_path / 'failure_history.pkl'
    probe.save_checkpoint(original, adapter, policy, path)
    saved = pickle.loads(path.read_bytes())

    current = Facade()
    restored, current_policy = runtime()
    probe.restore_checkpoint(current, restored, current_policy, saved)
    # Neither the original facade nor its callbacks may survive in the fork.
    original.success = True
    current.satisfied = True
    fields = restored.success_feedback.read()
    assert fields['task_success'] is False
    assert fields['subgoal_status'] == [{
        'id': 'g0', 'predicate': 'in', 'arguments': ['object', 'region'], 'satisfied': True}]
    assert restored.success_feedback.reads == 2
    assert restored.episode_policy.aggressive and restored.held == 'e1'
    current.success = True
    with pytest.raises(TaskAlreadySucceeded):
        restored.success_feedback.read()
