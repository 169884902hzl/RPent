"""Re-register an unchanged diagnostic cohort against a repaired source."""

import argparse
import copy
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
    parser.add_argument('--old-preparation', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    old = json.loads((args.old_preparation/'preparation.json').read_bytes())
    assert ref(old['manifest']['path']) == old['manifest']
    assert ref(old['launcher']['path']) == old['launcher']
    source = args.source.resolve(strict=True)
    manifest = json.loads(Path(old['manifest']['path']).read_bytes())
    assert not manifest['training'] and not manifest['confirmation']
    original_cases = copy.deepcopy(manifest['cases'])
    manifest.update(source_commit=args.commit, parent_manifest=old['manifest'])
    args.output.mkdir(parents=True)

    def write(name, value):
        with (args.output/name).open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')

    write('manifest.json', manifest)
    checks = []
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', LIBERO_CONFIG_PATH=str(root/'runtime_config'),
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    for name in ('startup', 'batch'):
        plan = json.loads((args.old_preparation/(name+'_plan.json')).read_bytes())
        assert not plan['training'] and not plan['confirmation']
        for batch in plan['batches']:
            assert batch['manifest'] == old['manifest']
            batch.update(source=str(source), source_commit=args.commit,
                manifest=ref(args.output/'manifest.json'))
        write(name+'_plan.json', plan)
        for index in range(len(plan['batches'])):
            command = [str(root/'.venv/bin/python'), old['launcher']['path'], '--batch-plan',
                str(args.output/(name+'_plan.json')), '--batch-index', str(index), '--preflight']
            result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
            log = args.output/f'{name}_{index}_preflight.log'
            log.write_text(result.stdout+result.stderr)
            result.check_returncode()
            checks.append({'command': command, 'exit_code': 0, 'log': str(log)})
    assert manifest['cases'] == original_cases
    report = {'source': str(source), 'source_commit': args.commit,
        'manifest': ref(args.output/'manifest.json'), 'launcher': old['launcher'],
        'preflights': checks, 'script': ref(__file__), 'training': False, 'confirmation': False,
        'parent_preparation': ref(args.old_preparation/'preparation.json'),
        'cases_identical': True, 'case_count': len(original_cases)}
    write('preparation.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
