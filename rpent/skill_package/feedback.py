"""Explicit, separately enabled benchmark feedback and episode limits."""
from dataclasses import dataclass


class TaskAlreadySucceeded(Exception):
    """No further decision or control is needed after native success."""


@dataclass(frozen=True)
class FeedbackConfig:
    task_success: bool = False
    subgoal_status: bool = False

    def __post_init__(self):
        if type(self.task_success) is not bool or type(self.subgoal_status) is not bool:
            raise ValueError('feedback switches must be booleans')


@dataclass(frozen=True)
class EpisodePolicy:
    aggressive: bool = False
    max_decisions: int = 40
    max_sim_steps: int = 10000


class SuccessFeedback:
    """Read callbacks exactly once before a request; expose no coordinates."""

    def __init__(self, config, *, native_success, subgoals=None):
        if config.subgoal_status and subgoals is None:
            raise ValueError('subgoal feedback requires registered predicates')
        self.config = config
        self.native_success = native_success
        self.subgoals = subgoals
        self.reads = 0

    def read(self):
        fields = {'feedback': {'task_success': self.config.task_success,
                               'subgoal_status': self.config.subgoal_status}}
        if self.config.task_success:
            value = self.native_success()
            if type(value) is not bool:
                raise ValueError('native success callback must return bool')
            self.reads += 1
            fields['task_success'] = value
            if value:
                raise TaskAlreadySucceeded('native_task_success_before_decision')
        if self.config.subgoal_status:
            fields['subgoal_status'] = self.subgoals()
        return fields


def configure(adapter, feedback, *, aggressive=False):
    """Activate v8 explicitly; historical runs retain their original policy."""
    adapter.success_feedback = feedback
    adapter.episode_policy = EpisodePolicy(aggressive=aggressive)
    adapter.schema_version = 'bounded-skills/8'


def public_fields(adapter):
    feedback = getattr(adapter, 'success_feedback', None)
    if feedback is None:
        return {}
    fields = feedback.read()
    policy = adapter.episode_policy
    fields['episode_policy'] = {
        'aggressive': policy.aggressive, 'max_decisions': policy.max_decisions,
        'max_sim_steps': policy.max_sim_steps, 'recovery_budget': None if policy.aggressive else 1,
    }
    return fields
