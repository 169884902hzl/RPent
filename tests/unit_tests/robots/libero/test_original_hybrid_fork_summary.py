"""Original fork reports retain unattempted and unknown branch denominators."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


def report_fixture(tmp_path, monkeypatch, *, mismatched=None):
    script = (Path(__file__).resolve().parents[4]
        / 'coordination/bounded_skills_20261016/scripts/summarize_original_hybrid_forks_20261020.py')
    spec = importlib.util.spec_from_file_location('original_fork_summary', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    preparation = tmp_path/'preparation'
    preparation.mkdir()
    cases = [{'name': f'case_{index}', 'category': 'cup_transfer',
        'episode': {'suite': 'libero_10', 'task': 4, 'seed': index},
        'diagnostic': {'goal_index': 1, 'subtask_mode': 'pick'}} for index in range(2)]
    manifest = preparation/'manifest.json'
    manifest.write_text(json.dumps({'source_commit': 'fixed', 'cases': cases}))
    reference = {'path': str(manifest), 'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()}
    (preparation/'batch_plan.json').write_text(json.dumps({'selected_n': 4,
        'batches': [{'manifest': reference, 'indices': [0, 1]}]}))
    (preparation/'full_submission.json').write_text(json.dumps({'job': '123'}))
    for index, case in enumerate(cases):
        directory = tmp_path/'job123_0/N4'/f'{index:03d}_{case["name"]}'
        directory.mkdir(parents=True)
        result = {'status': 'prefix_not_reached' if index == 0 else 'physical_result'}
        (directory/'worker_summary.json').write_text(json.dumps({'source_commit': 'fixed',
            'case': case, 'exit_code': 0, 'result': result}))
        if index == 0:
            continue
        for name, method, success, calls in [('self_0', 'self', False, 0),
                ('call_vla_1', 'call_vla', False, 0),
                ('call_vla_2', 'call_vla', False, 2),
                ('call_vla_3', 'call_vla', None, 3)]:
            path = directory/case['name']/name/'summary.json'
            path.parent.mkdir(parents=True)
            trial = {'method': method, 'success': success, 'training': False,
                'vla_inference_calls': calls, 'initial_physics_sha256': 'physics',
                'request_sha256': 'request'}
            if name == 'call_vla_2' and mismatched:
                trial[mismatched] = 'different'
            path.write_text(json.dumps(trial))
    output = tmp_path/'report.json'
    monkeypatch.setattr(sys, 'argv', [str(script), '--preparation', str(preparation),
        '--output', str(output)])
    return module, output


def test_unknown_and_unattempted_are_not_pi05_failures(tmp_path, monkeypatch):
    module, output = report_fixture(tmp_path, monkeypatch)
    module.main()
    report = json.loads(output.read_bytes())
    overall = report['overall']
    assert overall['registered_states'] == 2
    assert overall['status_counts']['prefix_not_reached'] == 1
    assert overall['vla_branch']['n'] == 2
    assert overall['vla_actually_executed']['n'] == 1
    assert overall['vla_unknown_outcomes'] == 1
    assert overall['vla_trials_registered'] == 6
    assert overall['vla_trials_unobserved'] == 3
    assert overall['vla_without_inference'] == 1
    assert overall['vla_inference_trials'] == 2
    assert report['both_failed'] == []


@pytest.mark.parametrize('key', ['initial_physics_sha256', 'request_sha256'])
def test_branches_from_different_inputs_cannot_be_pooled(tmp_path, monkeypatch, key):
    module, _ = report_fixture(tmp_path, monkeypatch, mismatched=key)
    with pytest.raises(ValueError, match=key):
        module.main()


def test_owned_allocation_output_keeps_all_registered_denominators(tmp_path, monkeypatch):
    module, output = report_fixture(tmp_path, monkeypatch)
    actual = tmp_path/'owned_allocation_step'
    (tmp_path/'job123_0').rename(actual)
    monkeypatch.setattr(sys, 'argv', [*sys.argv, '--batch-output', '0='+str(actual)])
    module.main()
    report = json.loads(output.read_bytes())
    assert report['closed_workers'] == 2
    assert report['overall']['registered_states'] == 2
    assert report['overall']['vla_trials_registered'] == 6
    assert report['overall']['vla_trials_unobserved'] == 3
    assert report['explicit_batch_outputs'] == {'0': str(actual)}
