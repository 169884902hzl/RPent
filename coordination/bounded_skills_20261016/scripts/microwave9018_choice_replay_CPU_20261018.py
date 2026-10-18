"""Replay only the selector at the recorded committed-door source identity."""
# ruff: noqa: E402 -- pin the immutable source before importing robot modules
import copy
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_panel_normal2_20261018_9f11e41'
sys.path.insert(0, str(source))

from robots.libero.bounded_oracle import BoundedOracle
from robots.libero.v5_state import Entity
from rpent.skill_package.contract import legal_after

candidate = Path('/tmp/bounded_oracle_panel_recovery_20261018.py')
spec = importlib.util.spec_from_file_location('panel_selector_candidate', candidate)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
directory = root/'results/bounded_skills/feasibility_20261017/job9018_120'
arm = next(directory.glob('*oracle_k4'))
rows = [json.loads(line) for line in (arm/'choices.jsonl').read_text().splitlines()]
row = rows[4]
request = row['request']
def surface(record):
    measured = next(item['plan']['surface_measurement'] for item in record['candidate_screen_diagnostics']
        if item.get('stage') == 'fixture_contact_plan' and item.get('anchor_id') == 'e114')
    return {key: measured[key] for key in ('normal_xyz', 'normal_source_step') if key in measured}
normals = {'reverted_initial': surface(row), 'last_measured': surface(rows[3])}
anchor = next(anchor for anchor in request['anchors'] if anchor['id'] == 'e114')
xyz, size = anchor['xyz_m'], anchor['size_m']
entity = Entity('e114', anchor['label'], tuple(xyz),
    tuple(x-s/2 for x, s in zip(xyz, size)), tuple(x+s/2 for x, s in zip(xyz, size)), False, 6)
scene = SimpleNamespace(entities={'e114': entity}, view_axes=([1., 0., 0.], [0., 1., 0.]))
adapter = SimpleNamespace(scene=scene, ex=SimpleNamespace(instruction=request['instruction']),
    held=None, active='e114', target_cache={}, receipts=rows[3]['receipts'])
status = {'done': False, 'goals': [['close', 'microwave_1']], 'satisfied': [False]}
records = []
for name, cls in [('baseline', BoundedOracle), ('candidate', module.BoundedOracle)]:
    for direction, measured in normals.items():
        adapter.plans = {'e114': {'surface_measurement': copy.deepcopy(measured)}}
        oracle = cls(None, adapter)
        # Preserve the already-committed source ID from the recorded run;
        # this check isolates direction/recovery, not fresh object binding.
        oracle.binding.bind = lambda *args, **kwargs: entity
        selected = oracle._choose_one(request, status)
        assert selected['id'] in legal_after(request, [])
        records.append({'selector': name, 'direction': direction, 'normal': measured,
            'selected': {key: selected[key] for key in ('id', 'skill', 'parameters')},
            'selected_is_public_legal': True})
assert records[0]['selected']['parameters'] == {'mode': 'open'}
assert records[-1]['selected']['parameters'] == {'axis': 'y', 'distance_m': .01, 'anchor_id': 'e114'}
output = root/'coordination/bounded_skills_20261016/reports/microwave9018_choice_replay_r2_CPU_20261018.json'
output.write_text(json.dumps({'scope': 'saved public request selector-only counterfactual; committed source fixed',
    'request_sha256': hashlib.sha256(json.dumps(request, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
    'choices_sha256': hashlib.sha256((arm/'choices.jsonl').read_bytes()).hexdigest(),
    'candidate_oracle_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'planner_calls': 0, 'controls': 0, 'gpu_used': False, 'training': False, 'records': records}, indent=2)+'\n')
print(json.dumps({'output': str(output), 'records': records}))
