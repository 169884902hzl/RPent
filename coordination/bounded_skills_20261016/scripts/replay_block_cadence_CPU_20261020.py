"""Audit saved VLA stop observations at action-block boundaries, without physics.

This is a thinning audit, not a replay of unrecorded controls or a new outcome
label. Stateful visual evidence needs a fresh physical paired comparison.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_ref(ref):
    path = Path(ref['path'])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref['sha256']:
        raise ValueError(f'registered input changed: {path}')
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cohort = json.loads(args.cohort.read_bytes())
    if cohort['closed_vla_trials'] != 213 or cohort['training']:
        raise ValueError('expected the closed, evaluation-only 213-branch cohort')
    rows = []
    for state in cohort['records']:
        for branch in state['trials']:
            summary = json.loads(read_ref(branch['summary']))
            choices = read_ref(summary['choices'])
            executions = [detail['execution'] for line in choices.splitlines()
                for detail in json.loads(line)['execution_details']
                if 'stop_reason' in detail.get('execution', {})
                    and 'preparation' in detail['execution']]
            if len(executions) != 1:
                raise ValueError('expected one fallback execution per branch')
            execution = executions[0]
            trace, checks = execution['trace'], execution['checks']
            row = {'case': state['case'], 'category': state['category'], 'mode': state['mode'],
                'source_commit': state['source_commit'], 'trial_seed': branch['trial_seed'],
                'summary': branch['summary'], 'choices': summary['choices'],
                'recorded_truth_success': summary['success'],
                'recorded_stop': execution.get('skill_stop_reason', execution['stop_reason']),
                'recorded_final_reason': summary['reason'],
                'controls': len(trace), 'recorded_checks': len(checks),
                'timing_s': execution.get('timing_s'), 'new_truth_success': None,
                'new_physical_result_measured': False}
            if not trace:
                row.update(status='no_policy_controls', block_boundary_checks=len(checks),
                    terminal_stop_observation_retained=None)
            elif execution['budget']['controls_per_check'] != 1 or len(checks) != len(trace)+1:
                row.update(status='dense_check_alignment_unavailable', block_boundary_checks=None,
                    terminal_stop_observation_retained=None)
            else:
                # The installed LIBERO service returns five controls per block.
                # A last partial block is not silently treated as a complete one.
                if any(item['control'] not in range(5) for item in trace):
                    raise ValueError('trace differs from the registered five-control service')
                boundaries = [i for i, item in enumerate(trace) if item['control'] == 4]
                terminal_retained = trace[-1]['control'] == 4
                native_stop = (execution['skill_stop_reason'] == 'native_success'
                    or (execution['stop_reason'] == 'native_success'
                        and execution.get('handoff', {}).get('native_stop') is True))
                sampled = [(0, checks[0]), *[(i+1, checks[i+1]) for i in boundaries]]
                visual_stop = next((control for control, check in sampled[1:]
                    if check['completed'] or check['outside_region']), None)
                row.update(status=('native_stop_checked_each_control' if native_stop else
                    'visual_stop_at_block_boundary' if terminal_retained else
                    'visual_stop_inside_block_unrecorded_tail'),
                    block_boundary_checks=1+len(boundaries),
                    native_stop_at_recorded_endpoint=native_stop,
                    terminal_stop_observation_retained=terminal_retained,
                    last_recorded_block=trace[-1]['block'], last_recorded_control=trace[-1]['control'],
                    first_retained_visual_stop_control=visual_stop,
                    stateful_visual_evidence=(state['mode'] in {'pick', 'push'}),
                    skipped_checks=len(checks)-1-len(boundaries))
            rows.append(row)
    counts = dict(Counter(row['status'] for row in rows))
    timing = defaultdict(float)
    for row in rows:
        for key, value in (row['timing_s'] or {}).items():
            timing[key] += value
    report = {'cohort': {'path': str(args.cohort.resolve()),
            'sha256': hashlib.sha256(args.cohort.read_bytes()).hexdigest()},
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'branches': len(rows), 'statuses': counts, 'records': rows,
        'recorded_timing_s_sum': dict(timing),
        'recorded_checks': sum(row['recorded_checks'] for row in rows),
        'thinned_checks_on_recorded_prefix': sum(row['block_boundary_checks'] or 0 for row in rows),
        'new_ground_truth_outcomes': 0, 'physics_steps': 0, 'gpu_used': False, 'training': False,
        'limitations': ['No unrecorded remainder of an early-stopped block is fabricated.',
            'Saved dense visual checks carry state; thinning them does not recompute the verifier.',
            'An unchanged sampled stop is not proof of unchanged closed-loop outcome.',
            'Summed branch timings include N8 contention and are not N1 latency.']}
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in ('branches', 'statuses', 'recorded_checks',
        'thinned_checks_on_recorded_prefix', 'recorded_timing_s_sum', 'new_ground_truth_outcomes')}))


if __name__ == '__main__':
    main()
