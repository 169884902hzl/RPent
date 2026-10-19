"""Measure a serializable public predictor with spawn, not GPU-process fork."""
import copy
import hashlib
import json
import multiprocessing
import os
import pickle
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root / 'source_bounded_cpu_prefix_parallel_20261019_16fdece3'
sys.path.insert(0, str(source))

from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_offline_labels import FrozenSensors, load_annotation_state
from rpent.skill_package.contract import committed_candidate_ids

prediction = None


def initialize(captured):
    global prediction
    prediction = captured


def candidate(original):
    return prediction.candidate(original)


def raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def main():
    global prediction
    records = []
    for job in ('9248_0', '9544_124', '9611_120'):
        choices, = (root / f'results/bounded_skills/feasibility_20261017/job{job}').glob('*oracle_k4/choices.jsonl')
        row = next(json.loads(line) for line in choices.open())
        ref = row['private_prefix_annotation_state']
        saved = load_annotation_state(ref['path'], ref['sha256'])
        prediction = PublicPrefixPrediction(copy.deepcopy(saved['adapter']), row['request'])
        first = next(c for c in row['request']['candidates'] if c['id'] == row['decision']['candidate_ids'][0])
        prediction.advance(first)
        prediction.adapter.p.env = FrozenSensors(prediction.sensor, prediction.budget)
        # Predictor contains only measured public state, never saved private
        # status/binding, clients, a renderer, controller or environment.
        captured = pickle.dumps(prediction, protocol=5)
        excluded = set(prediction.prefix) | set(committed_candidate_ids(row['request']))
        originals = [c for c in row['request']['candidates'] if c['id'] not in excluded]
        arms, values = [], []
        for workers in (1, 4):
            prediction = pickle.loads(captured)
            started = time.perf_counter()
            if workers == 1:
                values.append([candidate(c) for c in originals])
            else:
                with multiprocessing.get_context('spawn').Pool(workers, initializer=initialize,
                                                              initargs=(prediction,)) as pool:
                    values.append(pool.map(candidate, originals, chunksize=4))
            arms.append({'workers': workers, 'wall_s': time.perf_counter()-started})
        differences = [c['id'] for c, a, b in zip(originals, *values) if raw(a) != raw(b)]
        record = {'job': job, 'captured_public_bytes': len(captured), 'arms': arms,
                  'different_candidate_ids': differences,
                  'sha256': [hashlib.sha256(raw(value)).hexdigest() for value in values]}
        records.append(record)
        print(json.dumps(record), flush=True)
    report = {'scope': 'CPU spawn lifecycle/serialization probe; live runtime unchanged',
              'source_commit': '16fdece350735430e24398df61a321f694681d0e', 'records': records,
              'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out = root / 'coordination/bounded_skills_20261016/reports/prefix_spawn_pair_CPU_20261019.json'
    with out.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    if any(row['different_candidate_ids'] for row in records):
        raise SystemExit('spawn changed a public consequence')


if __name__ == '__main__':
    main()
