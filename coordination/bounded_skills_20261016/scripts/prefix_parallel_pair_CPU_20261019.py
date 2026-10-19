"""Test independent per-process consequences against their exact serial bytes."""
import copy
import hashlib
import json
import multiprocessing
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root / 'source_bounded_hybrid_d2_20261019_e9aeaf9b'
sys.path.insert(0, str(source))

from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_offline_labels import load_annotation_state
from rpent.skill_package.contract import committed_candidate_ids

prediction = None

def candidate(original):
    return prediction.candidate(original)

def raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

records = []
for job in ('9248_0', '9544_124', '9611_120'):
    choices, = (root / ('results/bounded_skills/feasibility_20261017/job'+job)).glob('*oracle_k4/choices.jsonl')
    row = next(json.loads(line) for line in choices.open())
    ref = row['private_prefix_annotation_state']
    saved = load_annotation_state(ref['path'], ref['sha256'])
    prediction = PublicPrefixPrediction(copy.deepcopy(saved['adapter']), row['request'])
    first = next(c for c in row['request']['candidates'] if c['id'] == row['decision']['candidate_ids'][0])
    prediction.advance(first)
    captured = copy.deepcopy(prediction)
    excluded = set(prediction.prefix) | set(committed_candidate_ids(row['request']))
    candidates = [c for c in row['request']['candidates'] if c['id'] not in excluded]
    arms, results = [], []
    for workers in (1, 4):
        prediction = copy.deepcopy(captured)
        started = time.perf_counter()
        if workers == 1:
            results.append([candidate(original) for original in candidates])
        else:
            # This probe has no CUDA, live clients, renderer or simulation.
            # Production GPU-process ownership requires a separate design.
            with multiprocessing.get_context('fork').Pool(workers) as pool:
                results.append(pool.map(candidate, candidates, chunksize=4))
        arms.append({'workers': workers, 'cpu_s': time.perf_counter()-started})
    differences = [original['id'] for original, a, b in zip(candidates, *results) if raw(a) != raw(b)]
    records.append({'job': job, 'context': ref, 'prefix': prediction.prefix,
        'candidates': len(candidates), 'different_candidate_ids': differences,
        'serial_sha256': hashlib.sha256(raw(results[0])).hexdigest(),
        'parallel_sha256': hashlib.sha256(raw(results[1])).hexdigest(), 'arms': arms})
    print(json.dumps(records[-1]), flush=True)
report = {'scope': 'CPU process-isolation experiment; no production parallel path enabled',
    'records': records, 'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
    'source_commit': 'e9aeaf9b', 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
out = root / 'coordination/bounded_skills_20261016/reports/prefix_parallel_pair_CPU_20261019.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
