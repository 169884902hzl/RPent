"""Test recent public payload references without changing collision tolerances."""

import copy
import hashlib
import json
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
setup = root/'coordination/bounded_skills_20261016/scripts/cup8158_current_membership_stages_CPU_20261018.py'
# Reuse the saved-frame fixture, without running its diagnostic or rewriting
# any previously delivered report.
context = {}
exec(compile(setup.read_text().split('stages = []', 1)[0], str(setup), 'exec'), context)
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

a, rows, key = (context[name] for name in ('a', 'rows', 'key'))
directory, load, row = (context[name] for name in ('directory', 'load', 'row'))
point = context['point']
def load_frame(name):
    path = directory/name/(f'{context["step"]:02d}'+Path(name).suffix)
    return np.asarray(Image.open(path)) if path.suffix == '.png' else load(path)
a.ex.toolkit._state.load = load_frame
a._cloud_and_ik()
a.held = key
static = load(directory/'bounded_payload_reference_scene.npz'/'11.npz')
results = []
for index in (11, 13, 14, 15, 16):
    previous = rows[index-1]
    evidence = previous['public_geometry_evidence'].get('bounded_screen_e6_1_payload_local')
    if not evidence:
        continue
    robot = previous['request']['robot']
    local = load(evidence['path'])
    target = local@Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix().T+robot['eef_xyz_m']
    a.payload_reference = {'target': target, 'scene': static,
        'robot': robot, 'capture_step': evidence['capture_step']}
    a._instance_cache.clear()
    current = a._instance_pixels(key)
    results.append({'previous_row': index-1, 'reference_capture_step': evidence['capture_step'],
        'reference_target': evidence, 'point_count': len(current),
        'nearest_blocker_m': float(cKDTree(current).query(point)[0]),
        'temporal': [copy.deepcopy(r) for r in a.instance_boundary_evidence[key]
                     if r.get('version', '').startswith('public-rigid-payload')]})
report = {'scope': 'CPU public saved-frame hypothesis; no controls, not a deployed rolling-reference rule',
    'private_truth_used': False, 'gpu_used': False, 'training': False,
    'choices_sha256': hashlib.sha256(context['choices'].read_bytes()).hexdigest(),
    'query_row': 16, 'blocker': point.tolist(), 'results': results}
path = root/'coordination/bounded_skills_20261016/reports/cup8158_rolling_payload_CPU_20261018.json'
path.write_text(json.dumps(report, indent=2)+'\n')
for result in results:
    print(result['reference_capture_step'], result['nearest_blocker_m'], result['point_count'], flush=True)
