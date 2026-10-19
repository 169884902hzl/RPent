"""Read only the registered handoff/stopping replays, retaining missing/errors."""
import argparse
import hashlib
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np


def read(path):
    return json.loads(Path(path).read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--job')
    parser.add_argument('--batch-output', action='append', default=[], metavar='INDEX=PATH',
        help='Explicit registered outputs from steps inside an owned GPU allocation')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    batches = read(args.preparation/'batch_plan.json')
    manifest = batches['batches'][0]['manifest']
    assert hashlib.sha256(Path(manifest['path']).read_bytes()).hexdigest() == manifest['sha256']
    plan = read(manifest['path'])
    outputs = {int(value.split('=', 1)[0]): Path(value.split('=', 1)[1]) for value in args.batch_output}
    if not args.job and not outputs:
        parser.error('provide --job or explicit --batch-output')
    sys.path.insert(0, batches['batches'][0]['source'])
    records, missing, errors = [], [], []
    for batch_index, batch in enumerate(batches['batches']):
        root = outputs.get(batch_index, args.preparation.parent/f'job{args.job}_{batch_index}')
        directory = root/f'N{batches["selected_n"]}'
        if root.exists():
            launch = read(root/'launch.json')
            assert launch['source_commit'] == plan['source_commit'] and launch['manifest'] == manifest
        for ordinal, index in enumerate(batch['indices']):
            case = plan['cases'][index]
            path = directory/f'{ordinal:03d}_{case["name"]}'/'worker_summary.json'
            partial = not path.exists()
            if partial:
                trial_path = path.parent/case['name']/'replay/summary.json'
                if not trial_path.exists():
                    missing.append(index)
                    continue
                assignment = read(path.parent/'assignment.json')
                assert assignment['case'] == case and assignment['case_index'] == index and not assignment['startup']
                result = {'source_commit': plan['source_commit'], 'case': case, 'training': False,
                    'trials': [read(trial_path)], 'continuation': {'status': 'pending'}}
            else:
                worker = read(path)
                if worker['exit_code']:
                    errors.append({'index': index, 'worker_summary': str(path), 'error': worker})
                    continue
                result = worker['result']
            assert result['source_commit'] == plan['source_commit']
            assert result['case'] == case and result['training'] is False
            trial = result['trials'][0]
            execution = next((d['execution'] for line in Path(trial['choices']['path']).open()
                for d in json.loads(line)['execution_details']
                if 'skill_stop_reason' in d.get('execution', {})), None)
            row = {'index': index, 'case': case['episode'], 'sampling_seed': trial['trial_seed'],
                'variant': case['diagnostic']['variant'], 'private_endpoint_success': trial['success'],
                'reason': trial['reason'], 'sim_steps': trial['sim_steps'],
                'paired_replay': trial.get('paired_replay'), 'continuation': result['continuation'],
                'wall_s': trial['wall_s'], 'private_metrology_s': trial['private_metrology_s'],
                'worker_summary': str(path) if not partial else None,
                'continuation_pending': partial, 'source_commit': plan['source_commit']}
            if execution is not None:
                trace, checks = execution['trace'], execution['checks']
                budget = execution['budget']
                row.update(controls=len(trace), inference_blocks=execution['blocks_used'], budget=budget,
                    skill_stop_reason=execution['skill_stop_reason'], handoff=execution['handoff'],
                    vla_timing_s=execution['timing_s'], prompt=execution.get('template'),
                    first_public_completed_control=next((i for i, c in enumerate(checks)
                        if c['completed']), None) if budget['controls_per_check'] == 1 else None,
                    private_success_timing='post-branch sustained window only; no invented earlier private success step')
                if trace:
                    saved = pickle.loads(Path(case['diagnostic']['branchpoint']['path']).read_bytes())
                    entities = saved['public_runtime']['scene']['entities']
                    end = np.asarray(trace[-1]['after']['eef_xyz_m'])
                    row['nearest_initial_public_entities_at_vla_end'] = sorted([
                        {'id': e.id, 'label': e.name, 'distance_m': float(np.linalg.norm(end-e.xyz)),
                            'capture_step': e.source_step}
                        for e in entities.values() if e.name != 'table' and not e.name.startswith('area ')],
                        key=lambda r: (r['distance_m'], r['id']))[:3]
                sam = trial['wall_time_breakdown']['main_thread_exclusive_s'].get('perception.segmentation', 0.)
                timing = execution['timing_s']
                parts = {'preparation_and_planning': timing['preparation'], 'pi05_inference': timing['inference'],
                    'sam_rpc': sam, 'private_metrology': trial['private_metrology_s'], 'handoff': timing['handoff']}
                parts['other_rgbd_geometry_control_io'] = trial['wall_s']-sum(parts.values())
                row['nonoverlapping_wall_partition_s'] = parts
                row['sam_scope'] = 'client SAM RPC including queue/transport; part of public observation, not added to it twice'
            records.append(row)
    result = {'manifest': manifest, 'source_commit': plan['source_commit'], 'registered_n': len(plan['cases']),
        'completed_n': len(records), 'missing_indices': missing, 'errors': errors, 'records': records,
        'complete_workers_n': sum(not r['continuation_pending'] for r in records),
        'variants': dict(Counter(r['variant'] for r in records)), 'training': False,
        'scope': 'registered same-state subtask repair only; not D2 whole-episode success',
        'all_six_handoffs_completed': len([r for r in records if r['variant'] == 'handoff']) == 6
            and all(r.get('handoff', {}).get('completed') is True or r.get('handoff', {}).get('native_stop')
                for r in records if r['variant'] == 'handoff')}
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ('registered_n','completed_n','missing_indices','errors','variants')}))


if __name__ == '__main__':
    main()
