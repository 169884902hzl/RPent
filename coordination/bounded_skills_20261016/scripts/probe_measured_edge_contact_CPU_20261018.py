"""Screen a thin-surface contour contact alternative on frozen public states."""
# ruff: noqa: E402 -- pin source and CPU before robot imports
import copy
import argparse
import hashlib
import inspect
import importlib.util
import json
import os
import sys
import textwrap
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_inclined_rim_20261018_2997335'
parser = argparse.ArgumentParser()
parser.add_argument('--inclined', action='store_true')
parser.add_argument('--working-adapter', type=Path)
args = parser.parse_args()
sys.path.insert(0, str(source))
import numpy as np

from robots.libero import bounded_skills
from robots.libero.bounded_offline_labels import load_annotation_state

original = bounded_skills.MeasuredSkillAdapter._surface_contact_plan
code = textwrap.dedent(inspect.getsource(original))
old = '        for patch_normal in normals:\n'
new = '''        if horizontal:
            boundary = np.r_[patch[:2]-centre[:2], 0.]
            if np.linalg.norm(boundary) >= .02:
                normals.insert(0, boundary/np.linalg.norm(boundary))
        for patch_normal in normals:
'''
if args.inclined:
    new = new.replace('                normals.insert(0, boundary/np.linalg.norm(boundary))',
        '''                boundary /= np.linalg.norm(boundary)
                for angle in (60., 45., 30.):
                    incline = boundary*math.cos(math.radians(angle))
                    incline[2] = math.sin(math.radians(angle))
                    normals.insert(0, incline)''')
assert code.count(old) == 1
code = code.replace(old, new)
old = '            tangent /= np.linalg.norm(tangent)\n'
new = '''            if np.linalg.norm(tangent) < .1:
                tangent = np.cross(patch_normal, [0., 0., 1.])
            tangent /= np.linalg.norm(tangent)
'''
assert code.count(old) == 1
code = code.replace(old, new)
old = "choices.sort(key=lambda item: (not item['local_normal'], item['patch_index'], item['wrist_change_rad'], item['yaw_deg']))"
new = "choices.sort(key=lambda item: (abs(item['normal_xyz'][2]), not item['local_normal'], item['patch_index'], item['wrist_change_rad'], item['yaw_deg']))"
assert code.count(old) == 1
code = code.replace(old, new)
namespace = dict(vars(bounded_skills))
exec(compile(code, '<cpu_measured_contour_contact>', 'exec'), namespace)
variant = namespace['_surface_contact_plan']
if args.working_adapter:
    spec = importlib.util.spec_from_file_location('candidate_measured_edge_runtime', args.working_adapter)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    variant = module.MeasuredSkillAdapter._surface_contact_plan
    code = inspect.getsource(variant)

records = []
for job in ('9502_160', '9502_161'):
    directory, = (root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle_k4')
    lines = (directory/'choices.jsonl').read_bytes().splitlines()
    for index in (0, 1):
        row = json.loads(lines[index])
        fits = [item for item in row['candidate_screen_diagnostics']
            if item.get('stage') == 'measured_surface_contact' and item.get('contact_xyz_m') is not None]
        if not fits:
            continue
        ref = row['private_prefix_annotation_state']
        frozen = load_annotation_state(ref['path'], ref['sha256'])
        for fit in fits:
            key = fit['anchor_id']
            attempts = []
            for name, method in (('original', original), ('measured_contour', variant)):
                adapter = copy.deepcopy(frozen['adapter'])
                adapter.candidate_diagnostics = []
                adapter._instance_pixels = lambda anchor: adapter._cloud_and_ik(anchor, contact=True).measured_target_points
                points = adapter._cloud_and_ik(key, contact=True).measured_target_points
                started = time.perf_counter()
                plan = method(adapter, adapter.scene.entities[key], points)
                elapsed = time.perf_counter()-started
                diagnostic = adapter.candidate_diagnostics[-1]
                attempts.append({'method': name, 'plan': plan, 'cpu_s': elapsed,
                    'selected_contact_xyz_m': diagnostic['contact_xyz_m'],
                    'selected_normal_xyz': diagnostic['surface_normal_xyz'],
                    'candidates': diagnostic['candidates']})
                print(json.dumps({'job': job, 'row': index, 'method': name,
                    'plan_available': plan is not None, 'normal': diagnostic['surface_normal_xyz'],
                    'cpu_s': elapsed}), flush=True)
            records.append({'job': job, 'row': index, 'anchor_id': key, 'context': ref, 'attempts': attempts})

report = {'scope': 'CPU screening of an alternative tip orientation at an observed contour point; no unseen side-face completion',
    'source': str(source), 'original_method_sha256': hashlib.sha256(inspect.getsource(original).encode()).hexdigest(),
    'candidate_method_sha256': hashlib.sha256(code.encode()).hexdigest(), 'candidate_method': code,
    'records': records, 'inclined': args.inclined, 'working_adapter': str(args.working_adapter),
    'gpu_used': False, 'physics_steps': 0, 'training': False, 'confirmation': False,
    'private_truth_used': False, 'runtime_modified': False,
    'limitation': 'A screened edge-contact pose does not establish physical contact or pushing success.',
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
suffix = '_inclined' if args.inclined else ''
suffix += '_runtime' if args.working_adapter else ''
output = root/f'coordination/bounded_skills_20261016/reports/measured_edge_contact_CPU_20261018{suffix}.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
