"""Pin a cache-only service entry for the not-yet-submitted D2 shards."""

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
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--sam-entry', type=Path, required=True)
    parser.add_argument('--compatibility', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    verified = json.loads(args.compatibility.read_bytes())
    assert verified['all_three_full_branches_equal']
    old = json.loads((args.preparation/'preparation.json').read_bytes())
    assert ref(old['manifest']['path']) == old['manifest']
    entry = ref(args.sam_entry)
    validated_entry = json.loads(Path(verified['preparation']['path']).read_bytes())['prototype']
    assert entry == validated_entry
    args.output.mkdir(parents=True)
    checks = []
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', LIBERO_CONFIG_PATH=str(root/'runtime_config'),
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    for kind in ('startup', 'batch'):
        plan = json.loads((args.preparation/(kind+'_plan.json')).read_bytes())
        assert not plan['training'] and not plan['confirmation']
        assert all(batch['manifest'] == old['manifest'] for batch in plan['batches'])
        plan['sam3_entry'] = entry
        path = args.output/(kind+'_plan.json')
        with path.open('x') as stream:
            json.dump(plan, stream, indent=2)
            stream.write('\n')
        for index in range(len(plan['batches'])):
            command = [str(root/'.venv/bin/python'), old['launcher']['path'], '--batch-plan',
                str(path), '--batch-index', str(index), '--preflight']
            result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
            log = args.output/f'{kind}_{index}_preflight.log'
            log.write_text(result.stdout+result.stderr)
            result.check_returncode()
            checks.append({'command': command, 'exit_code': 0, 'log': str(log)})
    report = {**old, 'preflights': checks, 'sam3_entry': entry,
        'parent_preparation': ref(args.preparation/'preparation.json'),
        'compatibility': ref(args.compatibility), 'script': ref(__file__),
        'scope': 'same source/cases/seeds/budgets; cache-only startup entry for future shards; existing jobs retained'}
    with (args.output/'preparation.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'preflight': 'passed', 'source_commit': old['source_commit'],
        'manifest': old['manifest'], 'sam3_entry': entry, 'checks': len(checks)}), flush=True)


if __name__ == '__main__':
    main()
