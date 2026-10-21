"""Later recovery decisions must not acquire labels for an earlier request."""
import importlib.util
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
