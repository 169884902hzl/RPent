# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Keep D2 result identities, unobserved cases and fork denominators distinct."""

import copy

import pytest

from robots.libero.bounded_hybrid_diagnostic import D2_SUITES
from scripts.summarize_bounded_hybrid_d2 import summarize


def fixture_plan():
    return {'training': False, 'confirmation': False, 'source_commit': 'fixed',
        'cases': [{'name': f'{suite}_{task}', 'episode': {'suite': suite, 'task': task, 'seed': 40}}
                  for suite in D2_SUITES for task in range(5)]}


def fixture_report(plan):
    trials = [{'method': method, 'success': success, 'trial_seed': index,
        'initial_physics_sha256': 'physics', 'request_sha256': 'request',
        'vla_inference_calls': int(index > 0), 'reason': 'block_budget',
        'sim_steps': 10, 'decisions': 1, 'wall_s': 2.}
        for index, (method, success) in enumerate([
            ('self', False), ('call_vla', False), ('call_vla', True), ('call_vla', None)])]
    return {'case': plan['cases'][0], 'source_commit': 'fixed', 'status': 'physical_result',
        'actual_full_replay_success': False, 'subtasks': [{'trials': trials,
            'subtask': {'id': 'g0:pick', 'mode': 'pick'},
            'selection': {'method': None, 'status': 'incomplete_measurement'}}]}


def test_registered_task_denominator_does_not_erase_missing_cases():
    plan = fixture_plan()
    result = summarize(plan, [fixture_report(plan)])
    assert result['independent_full_replay']['success'] == 0
    assert result['independent_full_replay']['known_n'] == 1
    assert result['independent_full_replay']['unknown_n'] == 39
    assert result['independent_full_replay']['registered_n'] == 40
    group, = result['subtask_summary']
    assert group['pi05_trials']['success'] == 1
    assert group['pi05_trials']['known_n'] == 2
    assert group['pi05_trials']['unknown_n'] == 1
    assert group['sampled_best']['success'] == 1
    assert not result['both_failed_subtasks']


@pytest.mark.parametrize('mismatch', ['physics', 'source', 'duplicate'])
def test_different_source_or_initial_state_cannot_be_pooled(mismatch):
    plan = fixture_plan()
    report = fixture_report(plan)
    reports = [report]
    if mismatch == 'physics':
        report['subtasks'][0]['trials'][2]['initial_physics_sha256'] = 'another'
    elif mismatch == 'source':
        report['source_commit'] = 'another'
    else:
        reports.append(copy.deepcopy(report))
    with pytest.raises(ValueError):
        summarize(plan, reports)


def test_both_zero_success_is_retained_with_each_branch_reason():
    plan = fixture_plan()
    report = fixture_report(plan)
    for trial in report['subtasks'][0]['trials']:
        trial['success'] = False
    result = summarize(plan, [report])
    failure, = result['both_failed_subtasks']
    assert len(failure['trials']) == 4
    assert failure['vla']['registered_n'] == 3
    assert failure['vla']['success'] == 0
