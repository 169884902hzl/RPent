"""Original-only goal variants for private skill diagnostics, never training."""

import copy


def goal_target_signatures(parsed_problems):
    """Reuse target types and region suffixes occurring in original goals."""
    signatures = set()
    for problem in parsed_problems:
        types = {name: kind for section in ('objects', 'fixtures')
                 for kind, names in problem[section].items() for name in names}
        for goal in problem['goal_state']:
            if len(goal) != 3 or goal[0] not in ('on', 'in'):
                continue
            destination = goal[2]
            if destination in problem['regions']:
                parent = problem['regions'][destination]['target']
                # Table initialization rectangles have no public target entity.
                if problem['regions'][destination]['ranges']:
                    continue
                suffix = destination.removeprefix(parent)
                signatures.add((goal[0], types[parent], suffix))
            elif destination in types:
                signatures.add((goal[0], types[destination], ''))
    return sorted(signatures)


def alternative_goals(problem, original_goal, signatures):
    """Match original goal vocabulary to objects already in this scene."""
    relation, source, original_target = original_goal
    objects = {name: kind for section in ('objects', 'fixtures')
               for kind, names in problem[section].items() for name in names}
    alternatives = set()
    for predicate, kind, suffix in signatures:
        if predicate != relation:
            continue
        for parent, parent_kind in objects.items():
            if parent_kind != kind or parent == source:
                continue
            target = parent + suffix
            if target == original_target:
                continue
            if suffix and (target not in problem['regions'] or
                           problem['regions'][target]['target'] != parent):
                continue
            alternatives.add(target)
    return [[relation, source, target] for target in sorted(alternatives)]


def apply_diagnostic_goal(wrapper, registered):
    """Align native success and private labels before any policy action."""
    if not registered.get('changed_goal'):
        return {'changed_goal': False}
    goal = registered['skill_goal']
    if goal not in registered['registered_goal_alternatives']:
        raise ValueError('Goal is outside the preregistered original-scene alternatives')
    env = wrapper.env
    if goal[1] not in env.objects_dict or goal[2] not in env.object_states_dict:
        raise ValueError('Registered goal object or target is absent from the original scene')
    env.parsed_problem['goal_state'] = [copy.deepcopy(goal)]
    env.parsed_problem['language_instruction'] = registered['diagnostic_instruction']
    # Evaluate through LIBERO itself so invalid predicate bindings fail early.
    predicate_satisfied = bool(env._eval_predicate(goal))
    native_satisfied = bool(env._check_success())
    if native_satisfied != predicate_satisfied:
        raise ValueError('Native success does not match registered diagnostic goal')
    return {'changed_goal': True, 'native_goal_matches_registered': True,
            'initially_satisfied': native_satisfied}
