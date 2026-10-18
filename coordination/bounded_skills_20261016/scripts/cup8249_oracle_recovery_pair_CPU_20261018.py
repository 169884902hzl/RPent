"""Pair selectors on an unchanged saved public request and private goal labels."""
# ruff: noqa: E402 -- choose immutable source before imports
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--oracle', type=Path, required=True)
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0, str(root/'source_bounded_e425264_20261018'))
import numpy as np
from robots.libero.bounded_oracle import BoundedOracle
from robots.libero.v5_state import Entity

d = next((root/'results/bounded_skills/feasibility_20261017/job8249_60').glob('*oracle*'))
prefix = (d/'choices.jsonl').read_bytes().splitlines()[:13]
row = json.loads(prefix[12])
request = row['request']
private = json.loads((d/'private_task_result.json').read_text())
trace = json.loads((d/'private_oracle_trace.json').read_text())
entities = {}
for anchor in request['anchors']:
    centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
    entities[anchor['id']] = Entity(anchor['id'], anchor['label'], tuple(centre),
        tuple(centre-size/2), tuple(centre+size/2), True, 13)
adapter = SimpleNamespace(held='e6', scene=SimpleNamespace(entities=entities,
    view_axes=((1, 0, 0), (0, -1, 0))), ex=SimpleNamespace(instruction=request['instruction']),
    plans={}, target_cache=entities, receipts=row['receipts'])
spec = importlib.util.spec_from_file_location('paired_oracle', args.oracle)
working = importlib.util.module_from_spec(spec)
spec.loader.exec_module(working)
original = copy.deepcopy(request)
results = []
for name, cls in [('original', BoundedOracle), ('lateral_recovery', working.BoundedOracle)]:
    oracle = cls(SimpleNamespace(call=lambda _: private), adapter)
    for record in trace[:12]:
        for symbol, field in ((record['goal'][1], 'source_public_id'), (record['goal'][2], 'target_public_id')):
            if record[field] is not None:
                oracle.binding._bindings[symbol] = record[field]
    response = oracle.choose(request)
    chosen = next(c for c in request['candidates'] if c['id'] == response['candidate_ids'][0])
    results.append({'method': name, 'chosen': chosen, 'private_trace': oracle.private_trace})
assert request == original
assert results[0]['chosen']['skill'] == 'observe'
assert results[1]['chosen']['skill'] == 'nudge'
assert results[1]['chosen']['parameters'] == {'axis': 'y', 'distance_m': .01, 'anchor_id': 'e6'}
report = {'scope': 'selector-only CPU pair; unchanged saved public request; no controls',
    'model_visible_changes': False, 'gpu_used': False, 'training': False, 'physical_result': None,
    'private_truth_used_only_for_oracle_selection': True,
    'choices_prefix_sha256': hashlib.sha256(b'\n'.join(prefix)).hexdigest(),
    'working_oracle_sha256': hashlib.sha256(args.oracle.read_bytes()).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'row': 12, 'results': results}
out = root/'coordination/bounded_skills_20261016/reports/cup8249_oracle_recovery_pair_CPU_20261018.json'
out.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k: [{'method': x['method'], 'skill': x['chosen']['skill'],
    'parameters': x['chosen']['parameters']} for x in results] for k in ['results']}))
