"""Check measured panel contact after the handle's approach becomes unreachable."""
# ruff: noqa: E402 -- restore the trusted pinned CPU context before imports
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_directional_contact_20261018_4db4ea4'
sys.path.insert(0, str(source))
import numpy as np
from robots.libero.bounded_offline_labels import load_annotation_state

directory, = (root/'results/bounded_skills/feasibility_20261017/job9539_120').glob('*oracle_k4')
choices = directory/'choices.jsonl'
raw = choices.read_bytes()
rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
records = []
for index in (6, 8, 12):
    row = rows[index]
    reference = row['private_prefix_annotation_state']
    adapter = load_annotation_state(reference['path'], reference['sha256'])['adapter']
    anchor_id = 'e114'
    entity = adapter.scene.entities[anchor_id]
    points = np.asarray(adapter.scene.measurement_clouds[anchor_id])
    adapter.candidate_diagnostics = []
    started = time.monotonic()
    plan = adapter._surface_contact_plan(entity, points)
    candidates = []
    if plan is not None:
        adapter.plans[anchor_id] = plan
        contact_screen = adapter._cloud_and_ik(anchor_id, contact=True)
        original_screens = adapter._cloud_and_ik
        free_screen = copy.deepcopy(contact_screen)
        free_screen.contact_allowed = False
        adapter._cloud_and_ik = lambda key=None, *, contact=False: (
            contact_screen if key == anchor_id and contact else free_screen
            if key == anchor_id else original_screens(key, contact=contact))
        for skill, parameters in (
                ('move_to', {'anchor_id': anchor_id, 'approach': plan['preferred_approach'],
                             'path': plan['preferred_path']}),
                ('descend', {'anchor_id': anchor_id})):
            candidates.append(adapter._candidate(skill, parameters))
    records.append({'index': index, 'context': reference, 'cpu_s': time.monotonic()-started,
        'public_plan': {key: value for key, value in (plan or {}).items()
                        if key != 'surface_measurement'},
        'candidates': candidates, 'diagnostics': adapter.candidate_diagnostics})
report = {'source': str(source), 'choices': {'path': str(choices),
    'sha256': hashlib.sha256(raw).hexdigest()}, 'records': records,
    'scope': 'CPU geometry only; unchanged full-route collision and IK checks',
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'private_goals_used': False,
    'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports/microwave9539_surface_fallback_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'rows': [{'index': row['index'],
    'cpu_s': row['cpu_s'], 'plan_available': bool(row['public_plan']),
    'candidates': row['candidates']} for row in records]}))
