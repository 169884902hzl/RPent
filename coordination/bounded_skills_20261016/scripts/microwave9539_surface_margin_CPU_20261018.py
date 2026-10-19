"""Compare equivalent measured surface contacts before committing a wrist pose."""
# ruff: noqa: E402 -- load the immutable source before restoring trusted classes
import hashlib
import inspect
import json
import os
import sys
import textwrap
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_directional_contact_20261018_4db4ea4'
sys.path.insert(0, str(source))
import numpy as np
from robots.libero import bounded_skills
from robots.libero.bounded_offline_labels import load_annotation_state

directory, = (root/'results/bounded_skills/feasibility_20261017/job9539_120').glob('*oracle_k4')
raw = (directory/'choices.jsonl').read_bytes()
row = json.loads(raw.splitlines()[0])
reference = row['private_prefix_annotation_state']
adapter = load_annotation_state(reference['path'], reference['sha256'])['adapter']
adapter.candidate_diagnostics = []
adapter._instance_cache = {'e114': np.asarray(
    adapter.plans['e114']['surface_measurement']['xyz_world'])}
code = textwrap.dedent(inspect.getsource(bounded_skills.MeasuredSkillAdapter._surface_contact_plan))
old = "return evidence['passed']\n    selected = next((option for option in choices if screened(option)), None)"
new = """margins = [solve['joint_margin_min_rad'] for check in evidence.get('ik_checks', [])
            for solve in check['solves'] if solve['solution_found']]
        option['screen']['route_joint_margin_rad'] = min(margins) if margins else None
        option['screen']['contact_joint_margin_rad'] = margins[-1] if margins else None
        return evidence['passed']
    feasible = [option for option in choices if screened(option)]
    selected = max(feasible, key=lambda option: (
        option['screen']['contact_joint_margin_rad'] or 0.,
        option['screen']['route_joint_margin_rad'] or 0.)) if feasible else None"""
assert code.count(old) == 1
code = code.replace(old, new)
namespace = dict(vars(bounded_skills))
exec(compile(code, '<cpu_surface_margin>', 'exec'), namespace)
started = time.monotonic()
plan = namespace['_surface_contact_plan'](adapter, adapter.scene.entities['e114'],
    np.asarray(adapter.scene.measurement_clouds['e114']))
diagnostic = adapter.candidate_diagnostics[-1]
report = {'source': str(source), 'context': reference,
    'cpu_s': time.monotonic()-started, 'candidate_method': code,
    'public_plan': {key: value for key, value in (plan or {}).items() if key != 'surface_measurement'},
    'diagnostic': diagnostic, 'scope': 'CPU hypothesis only; original geometry/IK thresholds unchanged',
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'private_goals_used': False,
    'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports/microwave9539_surface_margin_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'cpu_s': report['cpu_s'],
    'selected_yaw': diagnostic['selected_yaw_deg'],
    'candidates': [{key: option.get(key) for key in ('yaw_deg', 'path', 'screen', 'closure')}
        for option in diagnostic['candidates']]}))
