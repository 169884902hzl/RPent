"""Later recovery decisions must not acquire labels for an earlier request."""
import importlib.util
import hashlib
import json
from pathlib import Path



def module():
    path = Path(__file__).resolve().parents[4] / (
        'coordination/bounded_skills_20261016/scripts/'
        'export_original_schema6_measured_CPU_20261021.py')
    spec = importlib.util.spec_from_file_location('measured_export', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_measured_label_context_accepts_exact_first_decision():
    m = module()
    request = {'revision': 1, 'candidates': [{'id': 'vla'}]}
    trial = {'initial_physics_sha256': 'physics', 'request_sha256': m.digest(request),
             'selected_candidate_id': 'vla'}
    choices = [{'index': 0, 'request': request, 'decision': {'candidate_ids': ['vla']}}]
    assert m.verify_trial_context(trial, choices, request, 'physics') == (True, None)
    assert m.verify_trial_context(trial, choices, request, 'other')[0] is False


def test_measured_label_context_rejects_selection_after_binding_recovery():
    m = module()
    request = {'revision': 1, 'candidates': [{'id': 'vla'}]}
    trial = {'initial_physics_sha256': 'physics', 'request_sha256': m.digest(request),
             'selected_candidate_id': 'vla'}
    later = {'index': 1, 'request': request, 'decision': {'candidate_ids': ['vla']}}
    assert m.verify_trial_context(trial, [later], request, 'physics') == (
        False, 'selection_after_context_changed')
    later['index'] = 0
    later['request'] = {**request, 'revision': 2}
    assert m.verify_trial_context(trial, [later], request, 'physics')[0] is False


def test_prompt_change_in_later_recovery_is_unknown_for_the_initial_option():
    m = module()
    def wire(prompt):
        return {'fields': {'task_descriptions': hashlib.sha256(
            json.dumps([prompt], sort_keys=True).encode()).hexdigest()}}
    execution = [{'template': {'prompt': 'pick up the soup'}}]
    assert m.invocation_prompt([wire('pick up the soup')], execution) == (['pick up the soup'], None)
    prompts, issue = m.invocation_prompt([
        wire('pick up the soup'), wire('pick up the soup and place it in the basket'),
        wire('pick up the soup')], execution)
    assert prompts == ['pick up the soup']
    assert issue == 'effective_prompt_changed_during_continuation'


def test_requested_variants_cannot_duplicate_the_same_actual_candidate_and_seed():
    m = module()
    seen = set()
    trial = {'selected_candidate_id': 'actual_full_task', 'trial_seed': 34331000,
        'vla_variant': {'name': 'in_place'}}
    assert m.claim_invocation(seen, trial)
    assert not m.claim_invocation(seen, {**trial, 'vla_variant': {'name': 'full_task'}})
    assert m.claim_invocation(seen, {**trial, 'trial_seed': 34332000})
    assert m.claim_invocation(seen, {**trial, 'selected_candidate_id': 'actual_subtask'})
