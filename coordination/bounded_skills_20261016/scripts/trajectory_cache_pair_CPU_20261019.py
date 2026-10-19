"""Measure exact-input spline reuse on captured public prefix contexts."""
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root / 'source_bounded_hybrid_d2_20261019_e9aeaf9b'
sys.path.insert(0, str(source))

import numpy as np

from robots.libero import bounded_motion
from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_offline_labels import annotate_prefix, load_annotation_state

original = bounded_motion.plan
original_context = PublicPrefixPrediction.context

def key_for(points, kwargs):
    array = np.asarray(points, dtype=float)
    derivatives = kwargs.get('initial_derivatives')
    return (array.shape, array.tobytes(), kwargs.get('blend', True),
        tuple((indices.start, indices.stop, indices.step, limits.velocity,
            limits.acceleration, limits.jerk) for indices, limits in kwargs['groups']),
        None if derivatives is None else np.asarray(derivatives, dtype=float).tobytes())

records = []
for job in ('9248_0', '9544_124', '9611_120'):
    choices, = (root / ('results/bounded_skills/feasibility_20261017/job'+job)).glob('*oracle_k4/choices.jsonl')
    row = next(json.loads(line) for line in choices.open())
    ref = row['private_prefix_annotation_state']
    saved = load_annotation_state(ref['path'], ref['sha256'])
    prefix = row['decision']['candidate_ids'][:1]
    arms = []
    results = []
    for enabled in (False, True):
        cache, stats = {}, {'calls': 0, 'hits': 0, 'planning_s': 0., 'copy_s': 0.}
        context_hashes = []
        def context(owner):
            result = original_context(owner)
            raw = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
            context_hashes.append(hashlib.sha256(raw).hexdigest())
            return result
        def planning(points, **kwargs):
            key = key_for(points, kwargs)
            stats['calls'] += 1
            if enabled and key in cache:
                stats['hits'] += 1
                started = time.perf_counter()
                result = copy.deepcopy(cache[key])
                stats['copy_s'] += time.perf_counter()-started
                return result
            started = time.perf_counter()
            result = original(points, **kwargs)
            stats['planning_s'] += time.perf_counter()-started
            cache[key] = copy.deepcopy(result)
            return result
        bounded_motion.plan = planning
        PublicPrefixPrediction.context = context
        started = time.perf_counter()
        try:
            result = annotate_prefix(saved, row['request'], prefix)
        finally:
            bounded_motion.plan = original
            PublicPrefixPrediction.context = original_context
        arms.append({'cache_enabled': enabled, 'cpu_s': time.perf_counter()-started,
                     'context_sha256': context_hashes, **stats})
        results.append(result)
    raw = [json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
           for result in results]
    if raw[0] != raw[1]:
        raise ValueError('cached trajectory changed prefix labels')
    if arms[0]['context_sha256'] != arms[1]['context_sha256']:
        raise ValueError('cached trajectory changed public prefix candidate/consequence bytes')
    records.append({'job': job, 'context': ref, 'prefix': prefix,
        'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
        'label_sha256': hashlib.sha256(raw[0]).hexdigest(), 'labels_identical': True, 'arms': arms})
    print(json.dumps(records[-1]), flush=True)
report = {'scope': 'CPU exact-input pure trajectory cache probe; unchanged geometry/IK order; not production',
    'records': records, 'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
    'source_commit': 'e9aeaf9b', 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
out = root / 'coordination/bounded_skills_20261016/reports/trajectory_cache_pair_CPU_20261019.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
