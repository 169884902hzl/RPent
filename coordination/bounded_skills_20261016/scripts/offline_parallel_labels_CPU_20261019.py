"""Compare complete saved-state prefix contexts and labels, without physics."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root / 'source_bounded_cpu_prefix_parallel_20261019_16fdece3'
sys.path.insert(0, str(source))

from robots.libero.bounded_offline_labels import OfflinePrefixPrediction, annotate_prefix, load_annotation_state


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


records = []
original_context = OfflinePrefixPrediction.context
for job in ('9248_0', '9544_124', '9611_120'):
    choices, = (root / f'results/bounded_skills/feasibility_20261017/job{job}').glob('*oracle_k4/choices.jsonl')
    row = next(json.loads(line) for line in choices.open())
    reference = row['private_prefix_annotation_state']
    state = load_annotation_state(reference['path'], reference['sha256'])
    prefix = row['decision']['candidate_ids'][:1]
    arms = []
    for workers in (1, 4):
        contexts = []

        def context(prediction):
            result = original_context(prediction)
            contexts.append({'prefix': result['prefix'], 'sha256': digest(result),
                             'candidates': len(result['candidates'])})
            return result

        OfflinePrefixPrediction.context = context
        started = time.perf_counter()
        label = annotate_prefix(state, row['request'], prefix, workers=workers)
        arms.append({'workers': workers, 'wall_s': time.perf_counter()-started,
                     'contexts': contexts, 'label_sha256': digest(label), 'label': label})
    OfflinePrefixPrediction.context = original_context
    equal = arms[0]['contexts'] == arms[1]['contexts'] and arms[0]['label_sha256'] == arms[1]['label_sha256']
    records.append({'job': job, 'saved_state': reference, 'prefix': prefix,
                    'complete_context_and_label_bytes_equal': equal, 'arms': arms})
    print(json.dumps({'job': job, 'equal': equal,
        'wall_s': [arm['wall_s'] for arm in arms],
        'selected': [arm['label']['selected'] for arm in arms]}), flush=True)
report = {'source_commit': '16fdece350735430e24398df61a321f694681d0e', 'records': records,
          'scope': 'isolated offline CPU annotation; live planning remains serial',
          'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
out = root / 'coordination/bounded_skills_20261016/reports/offline_parallel_labels_CPU_20261019.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
if not all(row['complete_context_and_label_bytes_equal'] for row in records):
    raise SystemExit('parallel annotation changed a captured public context or private label')
