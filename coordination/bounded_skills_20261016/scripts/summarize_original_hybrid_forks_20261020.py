"""Summarize registered original subtask forks without calling them whole tasks."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def rate(values):
    n, successes = len(values), sum(values)
    if not n:
        return {'n': 0, 'success': 0, 'rate': None, 'wilson95': None}
    z = 1.959963984540054
    denominator = 1+z*z/n
    centre = (successes/n+z*z/(2*n))/denominator
    half = z*((successes/n)*(1-successes/n)/n+z*z/(4*n*n))**.5/denominator
    return {'n': n, 'success': successes, 'rate': successes/n,
        'wilson95': [centre-half, centre+half]}


def summarize(rows):
    trials = [trial for row in rows for trial in row['trials'] if trial['method'] == 'call_vla']
    known = [trial for trial in trials if type(trial['success']) is bool]
    executed = [trial for trial in known if trial['vla_actually_executed']]
    return {'registered_states': len(rows), 'closed_workers': sum(row['worker_closed'] for row in rows),
        'fork_reached': sum(row['fork_reached'] for row in rows),
        'status_counts': dict(Counter(row['status'] for row in rows)),
        'self_branch': rate([row['self_success'] for row in rows if type(row['self_success']) is bool]),
        'vla_branch': rate([trial['success'] for trial in known]),
        'vla_actually_executed': rate([trial['success'] for trial in executed]),
        'vla_trials_registered': 3*len(rows), 'vla_trials_closed': len(trials),
        'vla_trials_unobserved': 3*len(rows)-len(trials),
        'vla_unknown_outcomes': len(trials)-len(known),
        'vla_inference_trials': sum(trial['vla_actually_executed'] for trial in trials),
        'vla_without_inference': sum(not trial['vla_actually_executed'] for trial in trials),
        'both_failed_states': sum(row['both_failed'] for row in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan = read(args.preparation/'batch_plan.json')
    submission = read(args.preparation/'full_submission.json')
    reference = plan['batches'][0]['manifest']
    manifest_bytes = Path(reference['path']).read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != reference['sha256']:
        raise ValueError('registered original manifest changed')
    manifest = json.loads(manifest_bytes)
    records, errors, pending_reads = [], [], []
    for batch_index, batch in enumerate(plan['batches']):
        root = args.preparation.parent/f'job{submission["job"]}_{batch_index}'
        if (root/'launch.json').exists():
            launch = read(root/'launch.json')
            assert launch['source_commit'] == manifest['source_commit']
            assert launch['manifest'] == reference
        for ordinal, index in enumerate(batch['indices']):
            case = manifest['cases'][index]
            directory = root/f'N{plan["selected_n"]}'/f'{ordinal:03d}_{case["name"]}'
            worker_path = directory/'worker_summary.json'
            worker = read(worker_path) if worker_path.exists() else None
            if worker:
                assert worker['source_commit'] == manifest['source_commit'] and worker['case'] == case
            result = (worker.get('result') or {}) if worker else {}
            status = result.get('status', 'pending')
            if worker and worker['exit_code']:
                status = 'worker_error'
                errors.append({'index': index, 'worker_summary': str(worker_path), 'worker': worker})
            trials = []
            for name, method in [('self_0', 'self'), ('call_vla_1', 'call_vla'),
                                 ('call_vla_2', 'call_vla'), ('call_vla_3', 'call_vla')]:
                path = directory/case['name']/name/'summary.json'
                if not path.exists():
                    continue
                try:
                    trial = read(path)
                except json.JSONDecodeError as exc:
                    detail = {'index': index, 'path': str(path), 'error': str(exc)}
                    (errors if worker else pending_reads).append(detail)
                    continue
                assert trial['method'] == method and trial['training'] is False
                trials.append({key: trial.get(key) for key in ('method', 'trial_seed', 'success',
                    'reason', 'sim_steps', 'decisions', 'wall_s', 'vla_inference_calls',
                    'truth_source', 'source_public_id', 'target_public_id', 'endpoint', 'choices',
                    'initial_physics_sha256', 'request_sha256', 'observation_restore')}
                    | {'summary': str(path),
                       'vla_actually_executed': method == 'call_vla' and trial['vla_inference_calls'] > 0})
            for key in ('initial_physics_sha256', 'request_sha256'):
                values = {trial[key] for trial in trials}
                if None in values or len(values) > 1:
                    raise ValueError(f'forks differ or lack {key}: {directory}')
            own = next((row for row in trials if row['method'] == 'self'), None)
            fallback = [row for row in trials if row['method'] == 'call_vla']
            both_failed = (bool(own and own['success'] is False and len(fallback) == 3)
                and all(row['success'] is False for row in fallback))
            records.append({'index': index, 'case': case['name'], 'category': case['category'],
                'episode': case['episode'], 'goal_index': case['diagnostic']['goal_index'],
                'mode': case['diagnostic']['subtask_mode'], 'status': status,
                'worker_closed': worker is not None,
                'fork_reached': (directory/case['name']/'private_branchpoint.pkl').exists(),
                'prefix': result.get('prefix'), 'trials': trials,
                'self_success': own['success'] if own else None,
                'vla_success': sum(row['success'] is True for row in fallback),
                'vla_trials_closed': len(fallback),
                'vla_trials_executed': sum(row['vla_actually_executed'] for row in fallback),
                'both_failed': both_failed})
    groups = []
    for category, mode in sorted({(row['category'], row['mode']) for row in records}):
        rows = [row for row in records if row['category'] == category and row['mode'] == mode]
        groups.append({'category': category, 'mode': mode, **summarize(rows)})
    report = {'source_commit': manifest['source_commit'], 'manifest': reference,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'registered_states': len(records), 'closed_workers': sum(row['worker_closed'] for row in records),
        'overall': summarize(records), 'categories': groups, 'records': records,
        'errors': errors, 'pending_reads': pending_reads,
        'both_failed': [row for row in records if row['both_failed']], 'training': False,
        'scope': 'original40/90 selected subtask development forks; not whole-episode or D2 success',
        'denominators': 'prefix_not_reached and uncovered are retained as registered states, not VLA attempts; no-inference branches are separate; partial/unknown outcomes stay unknown',
        'interval_scope': 'Wilson intervals describe this fixed diagnostic cohort; each state has three VLA sampling seeds. They are not a claim about independent task generalization.'}
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in ('registered_states', 'closed_workers', 'categories', 'errors')}))


if __name__ == '__main__':
    main()
