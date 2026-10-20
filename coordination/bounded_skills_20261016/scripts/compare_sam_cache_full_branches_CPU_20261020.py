"""Compare complete cached-SAM forks with the pinned same-source baseline."""

import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_bytes())


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--full-output', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    baseline = read(args.baseline)
    old_workers = {row['seed']: row['worker'] for row in baseline['rows']}
    prep = read(args.preparation/'preparation.json')
    assert ref(prep['manifest']['path']) == prep['manifest']
    plan = read(prep['manifest']['path'])
    batches = read(args.preparation/'batch_plan.json')
    assert plan['source_commit'] == baseline['source_commit']
    assert read(args.full_output/'launch.json')['source_commit'] == plan['source_commit']
    rows, pending = [], []
    for ordinal, index in enumerate(batches['batches'][0]['indices']):
        case = plan['cases'][index]
        worker_path = args.full_output/f'N{batches["selected_n"]}'/f'{ordinal:03d}_{case["name"]}'/'worker_summary.json'
        if not worker_path.exists():
            pending.append(str(worker_path))
            continue
        worker = read(worker_path)
        assert worker['exit_code'] == 0 and worker['source_commit'] == plan['source_commit']
        new = worker['result']['trials'][0]
        old_ref = old_workers[new['trial_seed']]
        assert ref(old_ref['path']) == old_ref
        old_worker = read(old_ref['path'])
        old = old_worker['result']['trials'][0]
        folders = [Path(trial['choices']['path']).parent for trial in (old, new)]
        checks = {'same_case': worker['case'] == old_worker['case'],
            'same_seed': old['trial_seed'] == new['trial_seed'],
            'same_initial_physics': old['initial_physics_sha256'] == new['initial_physics_sha256'],
            'same_initial_request': old['request_sha256'] == new['request_sha256'],
            'same_inference_calls': old['vla_inference_calls'] == new['vla_inference_calls'],
            'input_bytes_equal': (folders[0]/'vla_inputs.jsonl').read_bytes() == (folders[1]/'vla_inputs.jsonl').read_bytes(),
            'prediction_bytes_equal': (folders[0]/'vla_predictions.jsonl').read_bytes() == (folders[1]/'vla_predictions.jsonl').read_bytes(),
            'same_endpoint_physics': old['endpoint']['physics_sha256'] == new['endpoint']['physics_sha256'],
            'same_private_success': old['success'] is new['success'],
            'same_public_stop': old['reason'] == new['reason']}
        requests = [folder.parent/'first_self_request.json' for folder in folders]
        checks['next_request_bytes_equal'] = requests[0].read_bytes() == requests[1].read_bytes()
        continuations = [value['result']['continuation'] for value in (old_worker, worker)]
        checks['same_bounded_continuation'] = all(continuations[0].get(key) == continuations[1].get(key)
            for key in ('request_generated', 'status', 'decision', 'receipts', 'sim_steps'))
        rows.append({'seed': new['trial_seed'], 'baseline_worker': old_ref,
            'new_worker': ref(worker_path), 'checks': checks, 'all_equal': all(checks.values()),
            'private_success': new['success'], 'inference_calls': new['vla_inference_calls'],
            'wall_s_overlapping_loads': [old['wall_s'], new['wall_s']]})
    result = {'source_commit': plan['source_commit'], 'baseline': ref(args.baseline),
        'preparation': ref(args.preparation/'preparation.json'), 'script': ref(__file__),
        'rows': rows, 'pending': pending,
        'all_three_full_branches_equal': len(rows) == 3 and not pending and all(row['all_equal'] for row in rows),
        'physics_steps': 0, 'gpu_used': False, 'training': False,
        'scope': 'full observed branch compatibility; wall times have different overlapping loads, not controlled episode throughput'}
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
