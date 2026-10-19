"""Compare production request workers including exact public capture overhead."""
import copy
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_bounded_request_planning_20261019_c82b5253'
sys.path.insert(0, str(SOURCE))

from robots.libero.bounded_cpu_planning import request_candidates
from robots.libero.bounded_offline_labels import load_annotation_state, request_digest


def save_json(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    with path.open('xb') as stream:
        stream.write(raw)
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def main():
    base = ROOT / 'coordination/bounded_skills_20261016'
    output = base / 'reports/request_candidates_pair_CPU_20261019'
    output.mkdir()
    records = []
    for job, position in (('9248_0', 0), ('9544_124', 0), ('9611_120', 0),
                          ('9248_47', -1), ('9248_113', -1)):
        choices, = (ROOT / f'results/bounded_skills/feasibility_20261017/job{job}').glob('*oracle_k4/choices.jsonl')
        rows = [json.loads(line) for line in choices.open()]
        row = rows[position]
        ref = row['private_prefix_annotation_state']
        saved = load_annotation_state(ref['path'], ref['sha256'])
        options = [(c['skill'], c['parameters']) for c in row['request']['candidates']]
        arms = []
        for workers in (1, 4):
            adapter = copy.deepcopy(saved['adapter'])
            adapter.candidate_diagnostics = []
            started = time.perf_counter()
            if workers == 1:
                candidates = [c for skill, parameters in options
                              if (c := adapter._candidate(skill, parameters)) is not None]
            else:
                candidates = request_candidates(adapter, options, workers)
            elapsed = time.perf_counter() - started
            value = {'candidates': candidates, 'diagnostics': adapter.candidate_diagnostics}
            arms.append({'workers': workers, 'wall_s': elapsed, 'candidates': len(candidates),
                         'diagnostics': len(adapter.candidate_diagnostics),
                         'value': save_json(output / f'{job}_workers{workers}.json', value)})
        equal = arms[0]['value']['sha256'] == arms[1]['value']['sha256']
        item = {'job': job, 'saved_row_index': row.get('index'), 'saved_state': ref,
                'held': saved['adapter'].held, 'request_sha256': request_digest(row['request']),
                'arms': arms, 'candidate_and_diagnostic_bytes_equal': equal}
        records.append(item)
        print(json.dumps(item), flush=True)
        if not equal:
            raise RuntimeError('production capture/spawn changed candidate consequences or diagnostics')
    report = {'source_snapshot': str(SOURCE), 'host': platform.node(), 'interpreter': sys.executable,
              'scope': 'post-contact-plan candidate enumeration including capture and spawn; before retry memory and compaction',
              'records': records, 'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
              'limitations': ['Does not regenerate initial contact plans or measure live perception.',
                              'These cross-source CPU diagnostics do not replace old physical results or training labels.'],
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save_json(base / 'reports/request_candidates_pair_CPU_20261019.json', report)


if __name__ == '__main__':
    main()
