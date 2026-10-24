"""Registered native feedback and persistent, finite-budget evaluation loops."""
import copy

from rpent.skill_package.contract import identity, legal_after
from rpent.skill_package.feedback import FeedbackConfig, SuccessFeedback, configure


def native_success(facade):
    """The unchanged LIBERO native predicate check, without advancing physics."""
    return bool(facade._env.env.workers[0].env_call('_check_success'))


def predicate_feedback(facade):
    status = facade.goal_status()
    return [{'id': f'g{i}', 'predicate': str(goal[0]),
             'arguments': [str(value) for value in goal[1:]], 'satisfied': bool(done)}
            for i, (goal, done) in enumerate(zip(status['goals'], status['satisfied']))]


def restore_feedback(adapter, facade, captured):
    """Rebind checkpoint feedback to this live facade after physics restore."""
    state = captured.get('feedback_state')
    if state is not None:
        adapter.success_feedback = SuccessFeedback(state['config'],
            native_success=lambda: native_success(facade),
            subgoals=lambda: predicate_feedback(facade))
        adapter.success_feedback.reads = state['reads']


def enable(adapter, facade, *, level_b=False, permissive=False):
    configure(adapter, SuccessFeedback(FeedbackConfig(True, level_b),
        native_success=lambda: native_success(facade), subgoals=lambda: predicate_feedback(facade)),
        aggressive=True)
    adapter.human_available = False
    adapter.vla_options_v2 = True
    adapter.allow_vla = True
    adapter.permissive_measured_anchor = permissive
    # Adapt historical request/receipt headers only in the new live session.
    from robots.libero.bounded_vla_staged import receipt_format
    receipt_format(adapter, adapter.schema_version)


def decision(request, ids):
    return {'schema_version': request['schema_version'], 'kind': 'decision',
            'revision': request['revision'], 'observation_id': request['observation_id'],
            'candidate_ids': list(ids)}


def choose(probe, facade, adapter, policy, request, *, only_pi=False, measured_path=()):
    """Private rule selector with measured-path preference and retry diversity.

    This is an executable oracle diagnostic, not an exhaustive mathematical
    bound. Old sampled method preferences are evaluation-only evidence; all
    current actions still come from this exact public menu and legal set.
    """
    legal = set(legal_after(request, []))
    candidates = [c for c in request['candidates'] if c['id'] in legal]
    whole = [c for c in candidates if c['skill'] == 'call_vla'
             and c['parameters']['mode'] == 'task'
             and c['parameters'].get('preparation') == 'in_place']
    if only_pi:
        chosen = min(whole, key=lambda c: (c['recent_failures'], bool(c['parameters'].get('seed_variant'))))
        return decision(request, [chosen['id']]), {'selector': 'whole_task_only'}
    from robots.libero.bounded_storage_progress import ordered_status
    status = ordered_status(facade.goal_status())
    specs, unsupported = probe.split_subtasks(status['goals'], adapter.ex.instruction)
    current = None
    source = target = None
    for spec in specs:
        if status['satisfied'][spec['goal_index']]:
            continue
        one_source, one_target = probe.bind_subtask(policy, adapter, spec)
        if spec['mode'] == 'pick' and one_source is not None and adapter.held == one_source.id:
            continue
        current, source, target = spec, one_source, one_target
        break
    stage = (tuple(bool(done) for done in status['satisfied']),
        current['id'] if current else None, source.id if source else None, target.id if target else None)
    if stage != getattr(policy, '_ceiling_observation_stage', None):
        policy._ceiling_observation_stage = stage
        policy._ceiling_observation_repeats = 0
    options = []
    own = None
    from robots.libero.bounded_oracle import NoPublicOption
    try:
        own = policy.choose(request)
    except NoPublicOption:
        pass
    if own and own['candidate_ids']:
        by_id = {c['id']: c for c in request['candidates']}
        first = by_id[own['candidate_ids'][0]]
        failures = first.get('recent_failures', 0)
        # Two repeated observations without a new private goal stage or a
        # recovered public binding must yield to a different legal method.
        # This is the user's repeat>=2 rule, not a D2-tuned score threshold.
        if first['skill'] != 'observe' or policy._ceiling_observation_repeats < 2:
            options.append((failures, 1, 0, first['id'], own, 'self_rule'))
    preferred = next((choice for choice in measured_path if current is not None
                      and choice['subtask']['id'] == current['id']), None)
    for candidate in candidates:
        if candidate['skill'] != 'call_vla':
            continue
        parameters = candidate['parameters']
        mode = parameters['mode']
        relevant = mode == 'task'
        if current and source is not None:
            relevant |= (mode == current['mode'] and parameters.get('anchor_id') == source.id
                         and (target is None or parameters.get('target_id') == target.id))
        if not relevant:
            continue
        preference = 2 if mode == 'task' else 1
        if preferred and preferred['method'] == 'call_vla' and all(
                parameters.get(k) == value for k, value in preferred.get('vla_parameters', {}).items()):
            preference = 0
        preparation = {'measured_anchor_permissive': 0, 'measured_anchor': 1, 'in_place': 2, 'initial_pose': 3}.get(parameters.get('preparation'), 1)
        options.append((candidate.get('recent_failures', 0), preference, preparation,
                        candidate['id'], decision(request, [candidate['id']]), 'call_vla'))
    if not options:
        return None, {'selector': 'no_public_option', 'unsupported': unsupported}
    selected = min(options, key=lambda row: row[:4])
    by_id = {candidate['id']: candidate for candidate in request['candidates']}
    first_selected = by_id[selected[4]['candidate_ids'][0]]
    policy._ceiling_observation_repeats = (policy._ceiling_observation_repeats+1
        if first_selected['skill'] == 'observe' else 0)
    return selected[4], {'selector': selected[5], 'subtask': current,
                         'rule_unsupported': unsupported, 'ranking': list(selected[:4]),
                         'uses_evaluation_sampled_method_preference': preferred is not None}
