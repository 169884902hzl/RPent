"""Pin the original failed public-binding case to a repaired source snapshot."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--failed-worker', type=Path, required=True)
    parser.add_argument('--old-preparation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    source = args.source.resolve(strict=True)
    worker = json.loads(args.failed_worker.read_bytes())
    assert worker['error'] == 'SubtaskBindingError' and worker['exit_code'] == 1
    old = json.loads((args.old_preparation/'preparation.json').read_bytes())
    assert ref(old['manifest']['path']) == old['manifest']
    manifest = json.loads(Path(old['manifest']['path']).read_bytes())
    case = worker['case']
    assert case in manifest['cases'] and case['diagnostic']['domain'] == 'original'
    assert not manifest['training'] and not manifest['confirmation']
    manifest.update(source_commit=args.commit, cases=[case],
        parent_manifest=old['manifest'], program_error_worker=ref(args.failed_worker),
        scope='same original state and policy seeds after a public prompt-binding program error; no score replacement')
    args.output.mkdir(parents=True)

    def write(name, value):
        with (args.output/name).open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')

    write('manifest.json', manifest)
    batch = {'domain': 'original', 'source': str(source), 'source_commit': args.commit,
        'manifest': ref(args.output/'manifest.json'), 'indices': [0]}
    plan = {'selected_n': 8, 'batches': [batch], 'training': False, 'confirmation': False}
    write('startup_plan.json', plan)
    write('batch_plan.json', plan)
    checks = []
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', LIBERO_CONFIG_PATH=str(root/'runtime_config'),
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    for kind in ('startup', 'batch'):
        command = [str(root/'.venv/bin/python'), old['launcher']['path'], '--batch-plan',
            str(args.output/(kind+'_plan.json')), '--batch-index', '0', '--preflight']
        result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
        log = args.output/(kind+'_preflight.log')
        log.write_text(result.stdout+result.stderr)
        result.check_returncode()
        checks.append({'command': command, 'exit_code': 0, 'log': str(log)})
    report = {'source': str(source), 'source_commit': args.commit,
        'manifest': ref(args.output/'manifest.json'), 'launcher': old['launcher'],
        'preflights': checks, 'script': ref(__file__), 'training': False, 'confirmation': False}
    write('preparation.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
