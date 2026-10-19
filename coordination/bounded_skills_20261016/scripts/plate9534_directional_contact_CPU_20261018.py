"""Check directional measured contact coverage with unchanged route screens."""
# ruff: noqa: E402 -- pin the captured source before imports
import copy
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
source = root/'source_bounded_chunk_v3_oblique_contour_20261018_5249d5d'
sys.path.insert(0, str(source))
import numpy as np
from robots.libero import bounded_skills
from robots.libero.bounded_offline_labels import load_annotation_state

directory, = (root/'results/bounded_skills/feasibility_20261017/job9534_160').glob('*oracle_k4')
row = json.loads((directory/'choices.jsonl').read_bytes().splitlines()[0])
reference = row['private_prefix_annotation_state']
state = load_annotation_state(reference['path'], reference['sha256'])
original = bounded_skills.MeasuredSkillAdapter._surface_contact_plan
code = textwrap.dedent(inspect.getsource(original))
old = "choices.sort(key=lambda item: (abs(item['normal_xyz'][2]) if horizontal else 0.,"
new = "choices.sort(key=lambda item: (-float((np.asarray(item['contact_xyz_m'])-centre) @ _DIAG_DIRECTION), abs(item['normal_xyz'][2]) if horizontal else 0.,"
assert code.count(old) == 1
code = code.replace(old, new)
right, front = map(np.asarray, state['adapter'].scene.view_axes)
records = []
for name, direction in [('baseline', None), ('front', front), ('left', -right), ('right', right)]:
    adapter = copy.deepcopy(state['adapter'])
    adapter.candidate_diagnostics = []
    points = np.asarray(adapter.scene.measurement_clouds['e99'])
    adapter._instance_pixels = lambda _: points
    namespace = {**vars(bounded_skills), '_DIAG_DIRECTION': direction}
    exec(compile(code, '<cpu_directional_measured_contact>', 'exec'), namespace)
    started = time.monotonic()
    plan = (original if direction is None else namespace['_surface_contact_plan'])(
        adapter, adapter.scene.entities['e99'], points)
    diagnostic = adapter.candidate_diagnostics[-1]
    selected = next((c for c in diagnostic['candidates'] if (c.get('screen') or {}).get('passed')), None)
    result = {'method': name, 'direction': direction.tolist() if direction is not None else None,
        'cpu_s': time.monotonic()-started, 'plan_available': plan is not None,
        'contact_point': diagnostic['contact_xyz_m'],
        'plan': {k: v for k, v in (plan or {}).items() if k != 'surface_measurement'},
        'selected': selected,
        'checked_candidates': sum(c.get('screen') is not None or c.get('closure') is not None
                                  for c in diagnostic['candidates'])}
    records.append(result)
    print(json.dumps({k: result[k] for k in ('method', 'direction', 'cpu_s', 'plan_available', 'contact_point', 'checked_candidates')}), flush=True)
output = root/'coordination/bounded_skills_20261016/reports/plate9534_directional_contact_CPU_20261018.json'
report = {'source': str(source), 'context': reference, 'row': 0, 'records': records,
    'scope': 'Directional public contact coverage only; no changed production behavior or physical outcome',
    'method': code, 'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False,
    'private_goal_used_for_geometry': False, 'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
