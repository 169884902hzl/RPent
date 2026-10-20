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
        'actual_full_replay_success': False, 'full_replay': [], 'subtasks': [{'trials': trials,
            'subtask': {'id': 'g0:pick', 'mode': 'pick'},
            'selection': {'method': None, 'status': 'incomplete_measurement'}}]}


def test_registered_task_denominator_does_not_erase_missing_cases():
    plan = fixture_plan()
    result = summarize(plan, [fixture_report(plan)])
    assert result['independent_full_replay']['success'] == 0
    assert result['independent_full_replay']['known_n'] == 0
    assert result['independent_full_replay']['unknown_n'] == 40
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


def test_optimistic_envelope_product_and_independent_replay_remain_separate():
    plan = fixture_plan()
    report = fixture_report(plan)
    report['subtasks'][0]['trials'][-1]['success'] = False
    report['subtasks'][0]['selection'] = {'method': 'call_vla', 'status': 'measured'}
    report['full_replay'] = [{'method': 'call_vla', 'success': False}]
    report.update(sampled_envelope_native_success=True, conditional_rate_product=1/3)
    result = summarize(plan, [report])
    assert result['sampled_envelope_native']['success'] == 1
    assert result['sampled_envelope_native']['unknown_n'] == 39
    assert result['independent_full_replay']['success'] == 0
    assert result['independent_full_replay']['known_n'] == 1
    assert result['conditional_rate_products'][0]['product'] == 1/3
    assert result['conditional_rate_products'][1]['product'] is None
    assert sum(row['registered_cases'] for row in result['task_suite_summary']) == 40
    suite = next(row for row in result['task_suite_summary']
                 if row['suite'] == report['case']['episode']['suite'])
    assert suite['registered_cases'] == 5
    assert suite['sampled_envelope_native']['success'] == 1
    assert suite['independent_full_replay']['success'] == 0


def test_no_replay_does_not_turn_the_initial_native_false_into_a_physical_failure():
    plan = fixture_plan()
    report = fixture_report(plan)
    before = copy.deepcopy(report)
    result = summarize(plan, [report])
    evidence, = result['independent_replay_evidence']
    assert evidence['status'] == 'no_replay_executed'
    assert evidence['label'] is None and evidence['raw_native_success_flag'] is False
    assert result['independent_full_replay']['known_n'] == 0
    assert report == before


def test_successful_prefix_before_unselected_subtask_is_not_a_full_replay_failure():
    plan = fixture_plan()
    report = fixture_report(plan)
    first = copy.deepcopy(report['subtasks'][0])
    first['selection'] = {'method': 'self', 'status': 'measured'}
    first['subtask']['id'] = 'g0:before'
    report['subtasks'].insert(0, first)
    report['full_replay'] = [{'method': 'self', 'success': True}]
    result = summarize(plan, [report])
    evidence, = result['independent_replay_evidence']
    assert evidence['status'] == 'incomplete_selected_methods'
    assert evidence['label'] is None


def test_complete_replay_with_unsatisfied_native_goal_retains_failure():
    plan = fixture_plan()
    report = fixture_report(plan)
    report['subtasks'][0]['selection'] = {'method': 'self', 'status': 'measured'}
    report['full_replay'] = [{'method': 'self', 'success': True}]
    result = summarize(plan, [report])
    evidence, = result['independent_replay_evidence']
    assert evidence['status'] == 'executed_complete_replay'
    assert evidence['label'] is False
    assert result['independent_full_replay']['known_n'] == 1


def test_failed_first_replay_subtask_retains_an_actual_failure():
    plan = fixture_plan()
    report = fixture_report(plan)
    report['subtasks'][0]['selection'] = {'method': 'self', 'status': 'measured'}
    second = copy.deepcopy(report['subtasks'][0])
    second['subtask']['id'] = 'g0:after'
    report['subtasks'].append(second)
    report['full_replay'] = [{'method': 'self', 'success': False}]
    result = summarize(plan, [report])
    evidence, = result['independent_replay_evidence']
    assert evidence['status'] == 'executed_replay_failed' and evidence['label'] is False
    assert result['independent_full_replay']['known_n'] == 1
