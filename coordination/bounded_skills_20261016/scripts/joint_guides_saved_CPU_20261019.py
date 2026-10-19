"""Check the committed contact-guide adapter on the recorded door failure."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root / 'source_bounded_chunk_v3_joint_guides_20261019_6958aefe'
sys.path.insert(0, str(source))

from robots.libero.bounded_offline_labels import load_annotation_state

choices, = (root / 'results/bounded_skills/feasibility_20261017/job9611_120').glob('*oracle_k4/choices.jsonl')
row = [json.loads(line) for line in choices.read_text().splitlines()][1]
ref = row['private_prefix_annotation_state']
adapter = load_annotation_state(ref['path'], ref['sha256'])['adapter']
adapter._instance_cache = {}
adapter.instance_boundary_evidence = {}
adapter.candidate_diagnostics = []
entity = adapter.scene.entities['e114']
started = time.perf_counter()
plan = adapter._surface_contact_plan(entity, adapter.scene.measurement_clouds['e114'])
elapsed = time.perf_counter()-started
report = {'scope': 'saved public measurement plus committed adapter; no physics or task-success label',
    'source_commit': '6958aefe1ef60c8b9f92e029f308762fdadb81f7', 'context': ref,
    'original_recorded_plan': row.get('request', {}).get('candidates'),
    'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
    'plan': plan, 'cpu_s': elapsed, 'diagnostics': adapter.candidate_diagnostics,
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
# The raw original request is already hash-pinned; avoid duplicating it here.
report.pop('original_recorded_plan')
out = root / 'coordination/bounded_skills_20261016/reports/joint_guides_saved_CPU_20261019.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(out), 'plan_found': plan is not None, 'cpu_s': elapsed,
    'approach_waypoints': len(plan.get('approach_route', [])) if plan else 0,
    'contact_waypoints': len(plan.get('contact_route', [])) if plan else 0}))
