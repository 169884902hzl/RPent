"""Compare complete real saved-request oracle paths with optional spawn."""
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root / 'source_bounded_spawn_planning_20261019_7ffe2118'
sys.path.insert(0, str(source))

from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.bounded_oracle import BoundedOracle


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                   allow_nan=False).encode()).hexdigest()


def main():
    records = []
    context_method = PublicPrefixPrediction.context
    for job in ('9248_0', '9544_124', '9611_120'):
        choices, = (root / f'results/bounded_skills/feasibility_20261017/job{job}').glob('*oracle_k4/choices.jsonl')
        row = next(json.loads(line) for line in choices.open())
        ref = row['private_prefix_annotation_state']
        saved = load_annotation_state(ref['path'], ref['sha256'])
        arms = []
        for workers in (1, 4):
            state = copy.deepcopy(saved)
            adapter = state['adapter']
            adapter.prefix_consequence_workers = workers
            oracle = BoundedOracle(SimpleNamespace(call=lambda *_: copy.deepcopy(state['private_status'])), adapter)
            oracle.binding.__dict__.update(state['binding'])
            contexts = []

            def context(prediction):
                current = context_method(prediction)
                contexts.append({'prefix': current['prefix'], 'sha256': digest(current),
                                 'candidates': len(current['candidates'])})
                return current

            PublicPrefixPrediction.context = context
            started = time.perf_counter()
            decision = oracle.choose(copy.deepcopy(row['request']))
            elapsed = time.perf_counter()-started
            PublicPrefixPrediction.context = context_method
            arms.append({'workers': workers, 'wall_s': elapsed, 'contexts': contexts,
                         'decision': decision, 'labels_sha256': digest(oracle.last_labels),
                         'request_sha256': digest(row['request']),
                         'legality_audit': oracle.last_legality_audit})
        equal = all(arms[0][field] == arms[1][field] for field in
                    ('contexts', 'decision', 'labels_sha256', 'request_sha256', 'legality_audit'))
        record = {'job': job, 'state': ref, 'complete_context_labels_and_choice_equal': equal, 'arms': arms}
        records.append(record)
        print(json.dumps({'job': job, 'equal': equal,
                          'wall_s': [arm['wall_s'] for arm in arms],
                          'actions': [arm['decision']['candidate_ids'] for arm in arms]}), flush=True)
    report = {'source_snapshot': str(source), 'records': records,
              'scope': 'complete oracle CPU selection from identical captured requests; no live simulation',
              'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out = root / 'coordination/bounded_skills_20261016/reports/runtime_spawn_oracle_CPU_20261019.json'
    with out.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    if not all(row['complete_context_labels_and_choice_equal'] for row in records):
        raise SystemExit('spawn changed a complete oracle context, choice or label')


if __name__ == '__main__':
    main()
