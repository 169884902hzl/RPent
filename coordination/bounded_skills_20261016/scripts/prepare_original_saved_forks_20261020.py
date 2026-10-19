"""Pin already logged original subtask starts, avoiding a newly failing prefix."""

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_bytes())


def reference(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def select_start(rows, diagnostic, load):
    """Select the first recorded decision in the registered goal and mode."""
    for row in rows:
        if 'private_pre_execution_snapshot' not in row:
            continue
        state = load(row['private_prefix_annotation_state'])
        index = next((i for i, done in enumerate(state['private_status']['satisfied']) if not done), None)
        mode = 'on' if state['adapter'].held is not None else 'pick'
        if index == diagnostic['goal_index'] and mode == diagnostic['subtask_mode']:
            return {'physics': row['private_pre_execution_snapshot'],
                'annotation': row['private_prefix_annotation_state'], 'decision_index': row['index']}
    raise ValueError('no logged original subtask start matches the registered phase')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--original-manifest', type=Path, required=True)
    parser.add_argument('--original-manifest-sha256', required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    sys.path.insert(0, str(source))
    from robots.libero.bounded_offline_labels import load_annotation_state

    def load(ref):
        return load_annotation_state(ref['path'], ref['sha256'])

    if reference(args.original_manifest)['sha256'] != args.original_manifest_sha256:
        raise ValueError('registered original manifest changed')
    old = read(args.original_manifest)
    cases = []
    for original in old['cases']:
        if original['category'] != 'cup_transfer':
            continue
        case = copy.deepcopy(original)
        diagnostic = case['diagnostic']
        choices = diagnostic['old_failed_choices']
        if reference(choices['path']) != choices:
            raise ValueError('original choices changed')
        rows = [json.loads(line) for line in Path(choices['path']).read_bytes().splitlines()]
        diagnostic['original_subtask_start'] = select_start(rows, diagnostic, load)
        cases.append(case)
    if len(cases) != 11:
        raise ValueError('expected exactly the eleven registered original failed cup states')
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    directory = root/'results/bounded_skills/original_saved_forks_20261020'/args.commit[:8]/'preparation'
    directory.mkdir(parents=True)
    manifest = directory/'manifest.json'
    manifest.write_text(json.dumps({**old, 'source_commit': args.commit, 'cases': cases,
        'parent_manifest': reference(args.original_manifest),
        'scope': 'eleven original failed-cup subtask starts; fresh public observation/recovery epoch shared by self and pi branches; separate from the from-init cohort'}, indent=2))
    batch = {'domain': 'original', 'source': str(source), 'source_commit': args.commit,
        'manifest': reference(manifest)}
    plan = {'selected_n': 8, 'batches': [{**batch, 'indices': list(range(i, min(i+8, 11)))}
        for i in range(0, 11, 8)], 'training': False, 'confirmation': False}
    startup = {**plan, 'batches': [{**batch, 'indices': [0]}]}
    launcher = root/'launcher_shared_20261019_3fa8bb8f1740/shared_gpu_episodes_20261019.py'
    checks = []
    for name, value in (('startup', startup), ('batch', plan)):
        path = directory/(name+'_plan.json')
        path.write_text(json.dumps(value, indent=2))
        for index in range(len(value['batches'])):
            command = [str(root/'.venv/bin/python'), str(launcher), '--batch-plan',
                str(path), '--batch-index', str(index), '--preflight']
            result = subprocess.run(command, cwd=root, text=True, capture_output=True,
                env=dict(os.environ, CUDA_VISIBLE_DEVICES='', LIBERO_CONFIG_PATH=str(root/'runtime_config'),
                    OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'))
            log = directory/f'{name}_{index}_preflight.log'
            log.write_text(result.stdout+result.stderr)
            result.check_returncode()
            checks.append({'command': command, 'exit_code': 0, 'log': str(log)})
    prep = {'source_commit': args.commit, 'source': str(source), 'manifest': reference(manifest),
        'launcher': reference(launcher), 'preflights': checks, 'training': False,
        'scope': 'new saved-start diagnostic; no confirmation or D2 data'}
    (directory/'preparation.json').write_text(json.dumps(prep, indent=2))
    print(json.dumps(prep))


if __name__ == '__main__':
    main()
