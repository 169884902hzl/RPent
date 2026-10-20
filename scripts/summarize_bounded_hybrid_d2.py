# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Summarize registered D2 branches without treating missing trials as failures."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from robots.libero.bounded_hybrid_diagnostic import validate_d2_episode


def rate(values):
    """Keep known truth, unknown truth and the full registered denominator apart."""
    known = [value for value in values if type(value) is bool]
    n, success = len(known), sum(known)
    if not n:
        interval = None
    else:
        z = 1.959963984540054
        centre = (success / n + z*z / (2*n)) / (1 + z*z / n)
        half = z * ((success/n)*(1-success/n)/n + z*z/(4*n*n))**.5 / (1+z*z/n)
        interval = [max(0., centre-half), min(1., centre+half)]
    return {'success': success, 'known_n': n, 'unknown_n': len(values)-n,
            'registered_n': len(values), 'rate': success/n if n else None,
            'wilson95': interval}


def replay_evidence(report):
    """Require an executed selected-method replay before scoring its native flag."""
    paired = report.get('subtasks', [])
    replay = report.get('full_replay')
    complete = bool(paired) and all(row['selection']['status'] == 'measured'
        and row['selection']['method'] is not None for row in paired)
    label = None
    if replay is None:
        status = 'missing_replay_evidence'
    elif not replay:
        status = 'no_replay_executed'
    elif not complete:
        status = 'incomplete_selected_methods'
    elif any(type(row.get('success')) is not bool for row in replay):
        status = 'unknown_replay_subtask_outcome'
    elif any(row['success'] is False for row in replay):
        label, status = False, 'executed_replay_failed'
    elif len(replay) != len(paired):
        status = 'incomplete_replay_records'
    else:
        label = report.get('actual_full_replay_success')
        status = 'executed_complete_replay' if type(label) is bool else 'unknown_native_outcome'
        if type(label) is not bool:
            label = None
    return {'label': label, 'status': status,
        'raw_native_success_flag': report.get('actual_full_replay_success'),
        'recorded_replay_subtasks': len(replay or []), 'selected_methods_complete': complete}


def summarize(plan, reports):
    """Report subtask outcomes, four exits and independent complete replays."""
    cases = {case['name']: case for case in plan['cases']}
    if len(cases) != 40 or plan['training'] or plan['confirmation']:
        raise ValueError('expected the registered forty-case evaluation plan')
    for case in cases.values():
        validate_d2_episode(case['episode'])
    by_case, stages, failures, uncovered, exits = {}, [], [], [], Counter()
    request_times = []
    for report in reports:
        name = report['case']['name']
        if name not in cases or cases[name] != report['case']:
            raise ValueError('result case differs from D2 manifest')
        if report.get('source_commit') not in {None, plan['source_commit']}:
            raise ValueError('cannot combine different source commits')
        if name in by_case:
            raise ValueError('duplicate case result; select a declared run, never a best result')
        by_case[name] = report
        if report['status'] == 'oracle_rule_uncovered':
            uncovered.append({'case': name, 'clauses': report['unsupported']})
        for paired in report.get('subtasks', []):
            trials = paired['trials']
            if (len(trials) != 4 or trials[0]['method'] != 'self'
                    or any(row['method'] != 'call_vla' for row in trials[1:])):
                raise ValueError('subtask needs one self and exactly three VLA trials')
            identities = {(row['initial_physics_sha256'], row['request_sha256']) for row in trials}
            if len(identities) != 1:
                raise ValueError('branch initial physics/request identities differ')
            vla = [row['success'] for row in trials[1:]]
            own = trials[0]['success']
            best = True if own is True or True in vla else (
                False if own is False and all(value is False for value in vla) else None)
            stage = {'case': name, 'suite': cases[name]['episode']['suite'],
                'subtask': paired['subtask'], 'self_success': own,
                'vla': rate(vla), 'sampled_best_success': best,
                'selection': paired['selection'], 'trials': trials}
            stages.append(stage)
            if best is False:
                failures.append(stage)
            for row in trials:
                if row['method'] != 'call_vla' or row['vla_inference_calls'] == 0:
                    continue
                exits[row['reason']] += 1
        breakdown = report.get('wall_time_breakdown', {})
        root = breakdown.get('main_thread_exclusive_by_root_s', {}).get('planning.request', {})
        calls = breakdown.get('calls', {}).get('planning.request:None', 0)
        if calls:
            request_times.append({'case': name, 'source_commit': plan['source_commit'],
                'requests': calls, 'total_client_wall_s': sum(root.values()),
                'mean_request_wall_s': sum(root.values())/calls})
    groups = defaultdict(list)
    for stage in stages:
        groups[(stage['suite'], stage['subtask']['mode'])].append(stage)
    summary = []
    for (suite, mode), rows in sorted(groups.items()):
        summary.append({'suite': suite, 'subtask_mode': mode, 'subtasks': len(rows),
            'self': rate([row['self_success'] for row in rows]),
            'pi05_trials': rate([trial['success'] for row in rows for trial in row['trials'][1:]]),
            'sampled_best': rate([row['sampled_best_success'] for row in rows]),
            'pi05_x_of_3': [row['vla'] for row in rows],
            'unavailable_trials': sum(trial.get('status') == 'unavailable'
                or trial['reason'] in {'matching_call_vla_candidate_unavailable',
                    'source_binding_missing', 'target_binding_missing'}
                for row in rows for trial in row['trials']),
            'costs': [{'case': row['case'], 'subtask_id': row['subtask']['id'],
                'branches': [{key: trial[key] for key in (
                    'method', 'trial_seed', 'sim_steps', 'decisions', 'wall_s', 'reason')}
                    for trial in row['trials']]} for row in rows]})
    physical = {name: report for name, report in by_case.items() if report['status'] == 'physical_result'}
    replay_details = {name: replay_evidence(report) for name, report in physical.items()}
    replay = [replay_details[name]['label'] if name in physical else None for name in cases]
    envelope = [physical[name].get('sampled_envelope_native_success') if name in physical else None
                for name in cases]
    task_suites = []
    for suite in sorted({case['episode']['suite'] for case in cases.values()}):
        names = [name for name, case in cases.items() if case['episode']['suite'] == suite]
        task_suites.append({'suite': suite, 'registered_cases': len(names),
            'sampled_envelope_native': rate([physical[name].get('sampled_envelope_native_success')
                if name in physical else None for name in names]),
            'independent_full_replay': rate([replay_details[name]['label']
                if name in physical else None for name in names])})
    return {'source_commit': plan['source_commit'], 'registered_cases': 40,
        'case_status': dict(Counter(report['status'] for report in by_case.values())),
        'missing_cases': [name for name in cases if name not in by_case],
        'independent_full_replay': rate(replay), 'sampled_envelope_native': rate(envelope),
        'independent_replay_evidence': [{'case': name, **detail}
            for name, detail in replay_details.items()],
        'task_suite_summary': task_suites,
        'conditional_rate_products': [{'case': name,
            'product': physical[name].get('conditional_rate_product') if name in physical else None,
            'status': by_case[name]['status'] if name in by_case else 'missing'} for name in cases],
        'subtask_summary': summary,
        'subtasks': stages, 'both_failed_subtasks': failures, 'uncovered_rules': uncovered,
        'vla_exit_counts_with_actual_inference': dict(exits),
        'planning_request_times': request_times, 'training': False,
        'limitations': [
            'Wilson intervals describe known labels; registered and unknown counts are separate.',
            'Repeated VLA trials within a subtask are correlated; pooled trial intervals are descriptive.',
            'Sampled best branches are an optimistic envelope, not independent whole-task success.',
            'Downstream subtasks not reached after a failed stage are not attempted observations.',
            'An empty replay or only a selected-method prefix is unobserved whole-replay evidence; its raw native flag is retained separately.',
            'Rule-acceptable options and measured method success are distinct; this is not model choice accuracy.',
        ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--case-result', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_bytes())
    report = summarize(plan, [json.loads(path.read_bytes()) for path in args.case_result])
    report['summarizer'] = {'path': str(Path(__file__).resolve()),
        'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    report['manifest'] = {'path': str(args.manifest.resolve()),
        'sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest()}
    report['result_sources'] = [{'path': str(path.resolve()),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in args.case_result]
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
