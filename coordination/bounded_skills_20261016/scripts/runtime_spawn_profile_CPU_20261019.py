"""Persist full prefix contexts and profile remaining oracle CPU overhead."""
import copy
import cProfile
import hashlib
import json
import os
import platform
import pstats
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_bounded_spawn_planning_20261019_7ffe2118'
sys.path.insert(0, str(SOURCE))

from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.bounded_oracle import BoundedOracle


def save_json(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    with path.open('xb') as stream:
        stream.write(raw)
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def main():
    base = ROOT / 'coordination/bounded_skills_20261016'
    output = base / 'reports/runtime_spawn_profile_CPU_20261019'
    output.mkdir()
    choices, = (ROOT / 'results/bounded_skills/feasibility_20261017/job9544_124').glob('*oracle_k4/choices.jsonl')
    row = json.loads(next(choices.open()))
    ref = row['private_prefix_annotation_state']
    saved = load_annotation_state(ref['path'], ref['sha256'])
    context_method = PublicPrefixPrediction.context
    arms = []
    for workers in (1, 4):
        state = copy.deepcopy(saved)
        adapter = state['adapter']
        adapter.prefix_consequence_workers = workers
        oracle = BoundedOracle(SimpleNamespace(call=lambda *_: copy.deepcopy(state['private_status'])), adapter)
        oracle.binding.__dict__.update(state['binding'])
        contexts = []

        def context(prediction):
            value = context_method(prediction)
            contexts.append(copy.deepcopy(value))
            return value

        PublicPrefixPrediction.context = context
        profiler = cProfile.Profile()
        started = time.perf_counter()
        try:
            decision = profiler.runcall(oracle.choose, copy.deepcopy(row['request']))
        finally:
            PublicPrefixPrediction.context = context_method
        elapsed = time.perf_counter()-started
        profile_path = output / f'workers{workers}.pstats'
        profiler.dump_stats(str(profile_path))
        functions = []
        for (file, line, name), (primitive_calls, calls, self_s, cumulative_s, _) in pstats.Stats(profiler).stats.items():
            functions.append({'file': file, 'line': line, 'function': name,
                              'primitive_calls': primitive_calls, 'calls': calls,
                              'self_s': self_s, 'cumulative_s': cumulative_s})
        functions.sort(key=lambda function: -function['cumulative_s'])
        context_files = [save_json(output / f'workers{workers}_prefix{i}.json', value)
                         for i, value in enumerate(contexts)]
        labels = save_json(output / f'workers{workers}_labels.json', oracle.last_labels)
        arms.append({'workers': workers, 'profiled_wall_s': elapsed, 'decision': decision,
                     'request': save_json(output / f'workers{workers}_request.json', row['request']),
                     'contexts': context_files, 'labels': labels, 'legality_audit': oracle.last_legality_audit,
                     'profile': {'path': str(profile_path), 'sha256': hashlib.sha256(profile_path.read_bytes()).hexdigest()},
                     'top15': functions[:15],
                     'project_top15': [function for function in functions if '/robots/libero/' in function['file']][:15]})
        print(json.dumps({'workers': workers, 'profiled_wall_s': elapsed,
                          'contexts': len(contexts)}), flush=True)
    equal = all(arms[0][key] == arms[1][key] for key in ('decision', 'legality_audit'))
    equal &= arms[0]['request']['sha256'] == arms[1]['request']['sha256']
    equal &= arms[0]['labels']['sha256'] == arms[1]['labels']['sha256']
    equal &= [value['sha256'] for value in arms[0]['contexts']] == [value['sha256'] for value in arms[1]['contexts']]
    report = {'source_snapshot': str(SOURCE), 'host': platform.node(), 'interpreter': sys.executable,
              'scope': 'profiled complete oracle CPU selection from a captured cup request',
              'saved_context': ref, 'arms': arms, 'all_saved_context_and_label_bytes_equal': equal,
              'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
              'limitations': ['Profiler and artifact collection add overhead; use the earlier unprofiled paired report for timings.',
                             'Spawn profile includes main-process waiting; worker function time is not broken down here.',
                             'Initial contact generation and live perception are outside this saved-request experiment.'],
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save_json(base / 'reports/runtime_spawn_profile_CPU_20261019.json', report)
    if not equal:
        raise SystemExit('profiled worker paths changed a saved public context, choice or label')


if __name__ == '__main__':
    main()
