"""Screen contact geometry after a hypothetical public close-before-approach."""
# ruff: noqa: E402 -- pin captured CPU classes before imports
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
from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_offline_labels import load_annotation_state

directory, = (root/'results/bounded_skills/feasibility_20261017/job9575_160').glob('*oracle_k4')
raw = (directory/'choices.jsonl').read_bytes()
row = json.loads(raw.splitlines()[0])
reference = row['private_prefix_annotation_state']
adapter = load_annotation_state(reference['path'], reference['sha256'])['adapter']
prediction = PublicPrefixPrediction(adapter, row['request'])
close, = [c for c in row['request']['candidates'] if c['skill'] == 'set_gripper'
          and c['parameters']['mode'] == 'close']
prediction.advance(close)
clone = prediction.adapter
points = np.asarray(clone.scene.measurement_clouds['e99'])
clone._instance_cache = {'e99': np.asarray(adapter.plans['e99']['surface_measurement']['xyz_world'])}
clone.candidate_diagnostics = []
code = textwrap.dedent(inspect.getsource(bounded_skills.MeasuredSkillAdapter._surface_contact_plan))
old = 'for opening in np.linspace(.08, 0., 9):'
new = "for opening in np.linspace(min(.08, robot['gripper_opening_m']), 0., 9):"
assert code.count(old) == 1
code = code.replace(old, new)
old = "-float((np.asarray(option['contact_xyz_m'])-centre)@direction))"
new = "(-float(np.asarray(option['normal_xyz'])@direction), -float((np.asarray(option['contact_xyz_m'])-centre)@direction)))"
assert code.count(old) == 1
code = code.replace(old, new)
old = 'and screened(option)), None)'
new = "and float(np.asarray(option['normal_xyz'])@direction) > 0. and screened(option)), None)"
assert code.count(old) == 1
code = code.replace(old, new)
namespace = dict(vars(bounded_skills))
exec(compile(code, '<cpu_closed_surface>', 'exec'), namespace)
started = time.monotonic()
plan = namespace['_surface_contact_plan'](clone, clone.scene.entities['e99'], points)
report = {'source': str(source), 'context': reference,
    'prefix': [close['id']], 'conditional_robot': prediction.sensor,
    'cpu_s': time.monotonic()-started, 'candidate_method': code,
    'public_plan': {key: value for key, value in (plan or {}).items() if key != 'surface_measurement'},
    'diagnostic': clone.candidate_diagnostics[-1],
    'scope': 'Conditional on hypothetical close; no new measurement or physical result',
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'private_goals_used': False,
    'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports/plate9575_closed_aperture_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'cpu_s': report['cpu_s'],
    'options': {key: {k: v for k, v in value.items() if k != 'surface_measurement'}
        for key, value in (plan or {}).get('surface_contact_options', {}).items()}}))
