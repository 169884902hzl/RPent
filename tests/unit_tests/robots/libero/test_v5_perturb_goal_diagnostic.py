"""Changed-goal diagnostics align their native and private success signals."""

from types import SimpleNamespace

import pytest

from scripts.v5_perturb_goal_diagnostic import (
    alternative_goals, apply_diagnostic_goal, goal_target_signatures)


def test_public_target_names_keep_cabinet_surface_distinct_from_drawer():
    from scripts.prepare_v5_perturb_skill_selection_20261009 import public_name

    assert public_name('wooden_cabinet_1_top_side') == 'cabinet top surface'
    assert public_name('wooden_cabinet_1_top_region') == 'cabinet top drawer'
    assert public_name('white_cabinet_1_middle_region') == 'cabinet middle drawer'


def problem():
    return {'objects': {'bowl': ['bowl_1'], 'plate': ['plate_1', 'plate_2']},
            'fixtures': {'table': ['table_1'], 'cabinet': ['cabinet_1']},
            'regions': {'table_1_init': {'target': 'table_1', 'ranges': [[0, 0, 1, 1]]},
                        'cabinet_1_middle_region': {'target': 'cabinet_1', 'ranges': []}},
            'goal_state': [['on', 'bowl_1', 'plate_1'], ['in', 'bowl_1', 'cabinet_1_middle_region'],
                           ['on', 'bowl_1', 'table_1_init']]}


def test_original_target_templates_match_only_existing_public_targets():
    parsed = problem()
    signatures = goal_target_signatures([parsed])
    assert ('on', 'table', '_init') not in signatures
    assert alternative_goals(parsed, ['on', 'bowl_1', 'plate_1'], signatures) == [
        ['on', 'bowl_1', 'plate_2']]
    parsed['regions'].clear()
    assert alternative_goals(parsed, ['in', 'bowl_1', 'plate_1'], signatures) == []


def test_source_cannot_be_its_own_target():
    assert alternative_goals(problem(), ['on', 'plate_1', 'plate_2'], [('on', 'plate', '')]) == []


def test_native_success_uses_the_new_goal_and_does_not_mutate_registration():
    parsed = problem()
    satisfied = {('on', 'bowl_1', 'plate_1')}
    env = SimpleNamespace(parsed_problem=parsed, objects_dict={'bowl_1': object()},
                          object_states_dict={'plate_2': object()},
                          _eval_predicate=lambda g: tuple(g) in satisfied)
    env._check_success = lambda: all(env._eval_predicate(g) for g in parsed['goal_state'])
    goal = ['on', 'bowl_1', 'plate_2']
    registration = {'changed_goal': True, 'skill_goal': goal,
                    'registered_goal_alternatives': [goal], 'diagnostic_instruction': 'put bowl on plate two'}
    evidence = apply_diagnostic_goal(SimpleNamespace(env=env), registration)
    assert evidence['initially_satisfied'] is False
    assert parsed['goal_state'] == [goal]
    satisfied.add(tuple(goal))
    assert env._check_success() is True
    parsed['goal_state'][0][2] = 'different'
    assert registration['skill_goal'][2] == 'plate_2'


def test_unregistered_or_absent_target_does_not_change_native_goal():
    env = SimpleNamespace(parsed_problem=problem(), objects_dict={'bowl_1': object()}, object_states_dict={})
    registered = {'changed_goal': True, 'skill_goal': ['on', 'bowl_1', 'plate_2'],
                  'registered_goal_alternatives': [], 'diagnostic_instruction': 'put bowl on plate'}
    with pytest.raises(ValueError, match='outside'):
        apply_diagnostic_goal(SimpleNamespace(env=env), registered)
    registered['registered_goal_alternatives'] = [registered['skill_goal']]
    with pytest.raises(ValueError, match='absent'):
        apply_diagnostic_goal(SimpleNamespace(env=env), registered)
    assert env.parsed_problem['goal_state'] == problem()['goal_state']
