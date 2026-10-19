"""Check directional contact with full-screened direct and overhead routes."""
# ruff: noqa: E402 -- restore only the pinned trusted CPU context
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

directory, = (root/'results/bounded_skills/feasibility_20261017/job9534_160').glob('*oracle_k4')
row = json.loads((directory/'choices.jsonl').read_bytes().splitlines()[0])
reference = row['private_prefix_annotation_state']
adapter = load_annotation_state(reference['path'], reference['sha256'])['adapter']
points = np.asarray(adapter.scene.measurement_clouds['e99'])
adapter._instance_cache = {'e99': points}
adapter.candidate_diagnostics = []
code = textwrap.dedent(inspect.getsource(bounded_skills.MeasuredSkillAdapter._surface_contact_plan))
old = "-float((np.asarray(option['contact_xyz_m'])-centre)@direction))"
new = "(-float(np.asarray(option['normal_xyz'])@direction), -float((np.asarray(option['contact_xyz_m'])-centre)@direction)))"
assert code.count(old) == 1
code = code.replace(old, new)
old = "and screened(option)), None)"
new = "and float(np.asarray(option['normal_xyz'])@direction) > 0. and screened(option)), None)"
assert code.count(old) == 1
code = code.replace(old, new)
old = "routes = [('over', over)] if horizontal else [('direct', over[-2:]), ('over', over)]"
new = "routes = [('over', over), ('direct', over[-2:])] if horizontal else [('direct', over[-2:]), ('over', over)]"
assert code.count(old) == 1
code = code.replace(old, new)
namespace = dict(vars(bounded_skills))
exec(compile(code, '<cpu_directional_approach>', 'exec'), namespace)
started = time.monotonic()
plan = namespace['_surface_contact_plan'](adapter, adapter.scene.entities['e99'], points)
diagnostic = adapter.candidate_diagnostics[-1]
report = {'source': str(source), 'context': reference,
    'cpu_s': time.monotonic()-started,
    'options': {name: {k: value for k, value in item.items() if k != 'surface_measurement'}
        for name, item in (plan or {}).get('surface_contact_options', {}).items()},
    'candidate_diagnostics': diagnostic, 'candidate_method': code,
    'scope': 'Public measured direction/route screening only; no production or physical change',
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'private_goals_used': False,
    'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports/plate9575_directional_direct_CPU_20261018.json'
raw = json.dumps(report, indent=2)+'\n'
with output.open('x') as stream:
    stream.write(raw)
print(json.dumps({'cpu_s': report['cpu_s'], 'options': report['options'],
    'checked': sum(c.get('screen') is not None or c.get('closure') is not None
        for c in diagnostic['candidates'])}))
