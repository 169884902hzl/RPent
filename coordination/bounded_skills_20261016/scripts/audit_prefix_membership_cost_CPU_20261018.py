"""Measure exact duplicate point-set work during a saved-state oracle replay."""
import argparse
import hashlib
import json
import os
import runpy
import sys
import time
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--episode', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
sys.path.insert(0, str(args.source))

import numpy as np

from robots.libero import bounded_chunk
from robots.libero.bounded_oracle import BoundedOracle


def digest(array):
    value = np.asarray(array, dtype=float)
    return [list(value.shape), hashlib.sha256(value.tobytes()).hexdigest()]


original = bounded_chunk.separate_target_points
original_choose = BoundedOracle.choose
calls, first = [], {}
group = -1


def choose(oracle, request):
    global group
    group += 1
    first.clear()
    return original_choose(oracle, request)


def measured(target, scene):
    key = json.dumps([digest(target), digest(scene)])
    started = time.perf_counter()
    result = original(target, scene)
    elapsed = time.perf_counter()-started
    output = [digest(points) for points in result]
    previous = first.get(key)
    if previous is not None:
        assert output == calls[previous]['output'], 'identical input changed its output'
    else:
        first[key] = len(calls)
    calls.append(dict(replay_group=group, input=json.loads(key), output=output, elapsed_s=elapsed,
                      duplicate_of=previous))
    return result


bounded_chunk.separate_target_points = measured
BoundedOracle.choose = choose
replay = Path(__file__).with_name('recompute_original8288_oracle_CPU_20261018.py')
replay_output = args.output.with_name(args.output.stem+'_oracle.json')
sys.argv = [str(replay), '--source', str(args.source), '--episode', str(args.episode),
            '--output', str(replay_output)]
try:
    runpy.run_path(str(replay), run_name='__main__')
finally:
    bounded_chunk.separate_target_points = original
    BoundedOracle.choose = original_choose

duplicates = [call for call in calls if call['duplicate_of'] is not None]
report = dict(scope='CPU exact saved-state oracle replay; public prefix point-set inputs',
    source=str(args.source), calls=len(calls), unique_inputs=len(calls)-len(duplicates),
    duplicate_calls=len(duplicates), split_total_s=sum(call['elapsed_s'] for call in calls),
    exact_duplicate_split_s=sum(call['elapsed_s'] for call in duplicates),
    records=calls, oracle_replay=str(replay_output),
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    training=False, controls=0, fresh_sam_queries=0, GPU_used=False,
    limitations=['Hashing overhead is outside each split timer.',
                 'Duplicate lookup resets for each independent oracle invocation.',
                 'This measures point-set subtraction, not entire-episode speed.'])
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({key: report[key] for key in ('calls', 'unique_inputs', 'duplicate_calls',
    'split_total_s', 'exact_duplicate_split_s', 'oracle_replay')}))
