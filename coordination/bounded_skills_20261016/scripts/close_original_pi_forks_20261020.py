"""Combine the fixed original diagnostic cohort with its declared error repair."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_bytes())


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def rate(values):
    n, successes = len(values), sum(values)
    if not n:
        return {'n': 0, 'success': 0, 'rate': None, 'wilson95': None}
    z = 1.959963984540054
    centre = (successes/n+z*z/(2*n))/(1+z*z/n)
    half = z*((successes/n)*(1-successes/n)/n+z*z/(4*n*n))**.5/(1+z*z/n)
    return {'n': n, 'success': successes, 'rate': successes/n,
            'wilson95': [max(0., centre-half), min(1., centre+half)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first32', type=Path, required=True)
    parser.add_argument('--remaining39', type=Path, required=True)
    parser.add_argument('--repair-worker', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    first, rest, repair = map(read, (args.first32, args.remaining39, args.repair_worker))
    assert len(first['rows']) == 32 and len(rest['records']) == 39
    assert len(rest['errors']) == 1 and not rest['pending_reads']
    error = rest['errors'][0]['worker']
    assert error['error'] == 'SubtaskBindingError' and error['exit_code'] == 1
    assert repair['exit_code'] == 0 and repair['case'] == error['case']
    assert repair['result']['status'] == 'physical_result'
    assert not repair['result']['training'] and not repair['result']['confirmation']
    rows = []
    for row in first['rows']:
        rows.append({**row, 'source_commit': first['source_commit'],
            'repair': False, 'self_success': row['self_success'] if row['self_closed'] else None})
    for row in rest['records']:
        if row['case'] == repair['case']['name']:
            trials = [{**trial, 'summary': {'path': str(Path(trial['choices']['path']).parent/'summary.json')}}
                      for trial in repair['result']['trials']]
            source = repair['source_commit']
        else:
            trials = [trial for trial in row['trials'] if trial['method'] == 'call_vla']
            source = rest['source_commit']
        rows.append({**row, 'trials': trials, 'source_commit': source,
            'repair': row['case'] == repair['case']['name']})
    assert len(rows) == 71 and len({row['case'] for row in rows}) == 71
    for row in rows:
        assert len(row['trials']) == 3
        physics, requests, seeds = set(), set(), set()
        for trial in row['trials']:
            reference = trial['summary']
            path = Path(reference['path'] if isinstance(reference, dict) else reference)
            actual_ref = ref(path)
            if isinstance(reference, dict) and 'sha256' in reference:
                assert actual_ref == reference
            actual = read(path)
            assert actual['method'] == 'call_vla' and actual['training'] is False
            assert type(actual['success']) is bool
            assert actual['trial_seed'] == trial['trial_seed'] and actual['success'] == trial['success']
            trial.update({k: actual.get(k) for k in ('reason', 'sim_steps', 'wall_s',
                'vla_inference_calls', 'initial_physics_sha256', 'request_sha256')})
            trial['summary'] = actual_ref
            trial['actually_executed'] = trial['vla_inference_calls'] > 0
            physics.add(trial['initial_physics_sha256'])
            requests.add(trial['request_sha256'])
            seeds.add(trial['trial_seed'])
        assert len(physics) == len(requests) == 1 and None not in physics | requests and len(seeds) == 3
        row['vla_x_of_3'] = sum(t['success'] for t in row['trials'])
        row['vla_executed_n'] = sum(t['actually_executed'] for t in row['trials'])
    repair_row = next(row for row in rows if row['repair'])
    expected_base = repair['case']['diagnostic']['trial_seed_base']
    assert [t['trial_seed'] for t in repair_row['trials']] == [expected_base+1000*i for i in (1,2,3)]
    groups = []
    for category, mode in sorted({(row['category'], row['mode']) for row in rows}):
        cohort = [r for r in rows if (r['category'], r['mode']) == (category, mode)]
        trials = [t for row in cohort for t in row['trials']]
        groups.append({'category': category, 'mode': mode, 'states': len(cohort),
            'vla_interface': rate([t['success'] for t in trials]),
            'vla_executed': rate([t['success'] for t in trials if t['actually_executed']]),
            'without_inference': [t['summary'] for t in trials if not t['actually_executed']],
            'stop_counts': dict(Counter(t['reason'] for t in trials)),
            'self_closed': rate([r['self_success'] for r in cohort if type(r['self_success']) is bool]),
            'sources': dict(Counter(r['source_commit'] for r in cohort))})
    report = {'scope': 'fixed 71 original subtask diagnostic states, three VLA seeds each; not whole-task success',
        'sources': [ref(path) for path in (args.first32, args.remaining39, args.repair_worker)],
        'script': ref(__file__), 'registered_states': 71, 'closed_vla_trials': 213,
        'categories': groups, 'records': rows, 'old_program_error_retained': rest['errors'],
        'program_error_repair': ref(args.repair_worker), 'training': False, 'confirmation': False,
        'interval_scope': 'Wilson descriptive intervals on a fixed diagnostic cohort; seeds share states; mixed source revisions are explicit; no held-out performance claim',
        'self_denominator': 'only completed self branches in the first32; stopped partial and unrun self branches remain unknown'}
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    with args.output.with_suffix('.csv').open('x') as stream:
        fields = ['case', 'category', 'mode', 'source_commit', 'repair', 'self_success',
                  'vla_x_of_3', 'vla_executed_n']
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'registered_states': 71, 'closed_vla_trials': 213, 'categories': groups}))


if __name__ == '__main__':
    main()
