"""Artifact explanations must distinguish perception, no-effect and collision."""
from coordination.bounded_skills_20261016.scripts.audit_D2_three_issues_CPU_20261022 import replay_choices
from coordination.bounded_skills_20261016.scripts.explain_D2_replay_gaps_CPU_20261022 import own_failure_cause


def test_in_batch_replay_keeps_the_actually_selected_variant():
    source = {'subtasks': [{'subtask': {'id': 'g0:pick'},
        'selection': {'method': 'call_vla', 'status': 'measured',
            'vla_parameters': {'preparation': 'in_place'}, 'vla_variant': 'in_place'}}]}
    assert replay_choices({}, source) == [{'subtask': {'id': 'g0:pick'},
        'method': 'call_vla', 'vla_parameters': {'preparation': 'in_place'}, 'vla_variant': 'in_place'}]
    separate = {'path_selection': {'choices': [{'method': 'self'}]}}
    assert replay_choices(separate, source) == [{'method': 'self'}]


def test_no_change_observation_is_not_a_zero_step_collision():
    receipt = {'skill': 'observe', 'stop_reason': 'no_measured_scene_change',
        'steps_used': 23, 'phase': None}
    assert own_failure_cause([receipt]) == 'own_observation_no_scene_change_consumed_recovery'
    receipt.update(skill='move_to', stop_reason='predicted_anchor_changed', steps_used=0, phase='perception')
    assert own_failure_cause([receipt]) == 'own_skill_predicted_anchor_changed'
    receipt.update(stop_reason='measured_sweep_collision', phase='collision')
    assert own_failure_cause([receipt]) == 'own_skill_zero_control_collision_guard'
