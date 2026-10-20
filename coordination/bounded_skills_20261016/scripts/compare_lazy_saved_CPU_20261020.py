"""Compare endpoint/full consequences on identical frozen public CPU inputs."""
import argparse
import copy
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    from robots.libero.bounded_offline_labels import load_annotation_state

    records = []
    args.output.mkdir()
    for job in ('9248_0', '9544_124', '9611_120'):
        choices, = (args.root/f'results/bounded_skills/feasibility_20261017/job{job}').glob('*oracle_k4/choices.jsonl')
        row = json.loads(next(choices.open()))
        reference = row['private_prefix_annotation_state']
        saved = load_annotation_state(reference['path'], reference['sha256'])
        arms, values = [], []
        for lazy in (False, True):
            adapter = copy.deepcopy(saved['adapter'])
            adapter.lazy_planning_v1 = lazy
            # Old trusted pickle graphs predate the new endpoint cache field.
            for screen in adapter._cloud_and_ik.screens.values():
                screen._endpoint_ik_cache = {}
            started = time.perf_counter()
            candidates = [adapter._candidate(c['skill'], c['parameters']) for c in row['request']['candidates']]
            elapsed = time.perf_counter()-started
            path = args.output/f'{job}_{"endpoint" if lazy else "full"}.json'
            raw = json.dumps(candidates, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
            path.write_bytes(raw)
            values.append(candidates)
            arms.append({'lazy': lazy, 'wall_s': elapsed, 'path': str(path),
                'sha256': hashlib.sha256(raw).hexdigest(), 'candidates': len(candidates)})
        by_skill = defaultdict(Counter)
        paired = []
        for original, full, cheap in zip(row['request']['candidates'], *values):
            skill = original['skill']
            counts = by_skill[skill]
            counts['n'] += 1
            if full is None or cheap is None:
                counts['missing'] += 1
                continue
            a, b = full['consequences'], cheap['consequences']
            full_blocked = a['collision'] is True or a['ik_reachable'] is False
            cheap_blocked = b['collision'] is True or b['ik_reachable'] is False
            counts['cheap_pass_full_block'] += not cheap_blocked and full_blocked
            counts['cheap_block_full_pass'] += cheap_blocked and not full_blocked
            counts['both_blocked'] += cheap_blocked and full_blocked
            counts['both_pass_or_unknown'] += not cheap_blocked and not full_blocked
            paired.append({'id': original['id'], 'skill': skill,
                'full': a, 'endpoint': b})
        record = {'job': job, 'saved_state': row['private_prefix_annotation_state'], 'arms': arms,
            'by_skill': {skill: dict(counts) for skill, counts in by_skill.items()}, 'paired': paired}
        records.append(record)
        print(json.dumps({key: record[key] for key in ('job', 'arms', 'by_skill')}), flush=True)
    report = {'source': str(args.source), 'records': records, 'physics_steps': 0,
        'rpc_calls': 0, 'gpu_used': False, 'training': False,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': 'identical captured plans/options, comparing numerical endpoint screen to full smooth route',
        'limitations': ['Captured geometry/plans are reused; no contact resampling or live perception.',
            'Full-route rejection is a numerical/geometric screen, not physical ground truth.',
            'Task result and online oracle choice changes require the registered N1 physical runs.']}
    (args.output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
