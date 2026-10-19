"""Inspect measured push direction and private binding, without controls."""
# ruff: noqa: E402 -- pin CPU/source before loading saved state classes
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_oblique_contour_20261018_5249d5d'
sys.path.insert(0, str(source))
from robots.libero.bounded_offline_labels import load_annotation_state

directory, = (root/'results/bounded_skills/feasibility_20261017/job9534_160').glob('*oracle_k4')
path = directory/'choices.jsonl'
raw = path.read_bytes()
rows = [json.loads(line) for line in raw.splitlines()]
records = []
for index in (0, 3, 10, 15, 18):
    row = rows[index]
    reference = row['private_prefix_annotation_state']
    state = load_annotation_state(reference['path'], reference['sha256'])
    adapter = state['adapter']
    bindings = state['binding'].get('_bindings', {})
    records.append({'row': index, 'context': reference, 'instruction': row['request']['instruction'],
        'private_status_for_diagnosis_only': state['private_status'], 'binding': bindings,
        'public_anchors': row['request']['anchors'],
        'plans': {key: {k: value for k, value in plan.items() if k in
            ('xyz_m', 'approach_xyz_m', 'preferred_approach', 'surface_measurement', 'contact_kind')}
            for key, plan in adapter.plans.items()},
        'selected': [c for cid in row['decision']['candidate_ids']
                     for c in row['request']['candidates'] if c['id'] == cid],
        'receipts': [{k: r[k] for k in ('skill', 'outcome', 'stop_reason', 'steps_used')}
                     for r in row.get('receipts', [])]})
report = {'source': str(source), 'job': '9534_160', 'records': records,
    'choices': {'path': str(path), 'sha256_at_capture': hashlib.sha256(raw).hexdigest()},
    'scope': 'Saved public candidate geometry and private task-binding diagnosis only',
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'used_for_control': False,
    'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports/plate9534_public_goal_binding_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
for item in records:
    print(json.dumps({'row': item['row'], 'instruction': item['instruction'],
        'private_status': item['private_status_for_diagnosis_only'], 'binding': item['binding'],
        'anchors': [{k: a[k] for k in ('id', 'label', 'xyz_m')} for a in item['public_anchors']],
        'selected': [(c['skill'], c['parameters']) for c in item['selected']]}))
