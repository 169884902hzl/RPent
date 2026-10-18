"""Pair saved-public carry screening with a measured-pixel SAM refinement."""

import copy
import hashlib
import json
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
setup = root/'coordination/bounded_skills_20261016/scripts/cup8158_current_membership_stages_CPU_20261018.py'
context = {}
exec(compile(setup.read_text().split('stages = []', 1)[0], str(setup), 'exec'), context)
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from robots.libero.bounded_motion import MotionConfig, SmoothMotion
from robots.libero.v5_state import Entity

a, row, directory, load = (context[name] for name in ('a', 'row', 'directory', 'load'))
key, step = context['key'], context['step']
def load_frame(name):
    path = directory/name/(f'{step:02d}'+Path(name).suffix)
    return np.asarray(Image.open(path)) if path.suffix == '.png' else load(path)
a.ex.toolkit._state.load = load_frame
a._cloud_and_ik()
a.held = key
a.config = MotionConfig()
a.scene.entities = {}
for anchor in row['request']['anchors']:
    centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
    a.scene.entities[anchor['id']] = Entity(anchor['id'], anchor['label'], tuple(centre),
        tuple(centre-size/2), tuple(centre+size/2), True, step)
a.target_cache = a.scene.entities.copy()
reference = directory/'bounded_payload_reference_robot.json'/'11.json'
a.payload_reference = {'target': load(directory/'bounded_payload_reference_target.npz'/'11.npz'),
    'scene': load(directory/'bounded_payload_reference_scene.npz'/'11.npz'),
    'robot': json.loads(reference.read_text()), 'capture_step': 11}
original_views = copy.deepcopy(a.scene.measurement_clouds_by_view[key])
diagnostic_path = root/'coordination/bounded_skills_20261016/reports/cup8158_sam_identity_GPU_job8172/report.json'
diagnostic = json.loads(diagnostic_path.read_text())
guided = next(r for r in diagnostic['results'] if r['camera'] == 'wrist' and 'point' in r['query'])
with np.load(guided['mask']) as archive:
    guided_mask = archive['mask']
world = load_frame('wrist_world_high.npz')
original_mask = load(row['perception_evidence'][key]['sam_mask_files']['wrist']['path']).astype(bool)
results = []
for method in ('original', 'public_point_union'):
    a.scene.measurement_clouds_by_view[key] = copy.deepcopy(original_views)
    if method == 'public_point_union':
        union = (original_mask | guided_mask) & np.isfinite(world).all(axis=2)
        a.scene.measurement_clouds_by_view[key]['wrist']['xyz_world'] = world[union]
    a._instance_cache.clear()
    a._screen_cache.clear()
    screen = a._cloud_and_ik('e99')
    route = a._route('carry_to', {'target_id': 'e99'})
    trajectory, _, _, check = SmoothMotion(a.p, screen, a.config).prepare(route)
    instance = a._instance_pixels(key)
    result = {'method': method, 'route': route, 'duration_s': trajectory.duration,
        'check': check, 'current_instance_points': len(instance),
        'nearest_public_blockers_m': cKDTree(instance).query(diagnostic['public_blockers'])[0].tolist(),
        'boundary': copy.deepcopy(a.instance_boundary_evidence[key])}
    results.append(result)
    print(method, check['passed'], check['reason'], result['nearest_public_blockers_m'], flush=True)
report = {'scope': 'exact saved RGB-D, same full carry route, zero controls; not deployed',
    'source': context['source'], 'choices_sha256': hashlib.sha256(context['choices'].read_bytes()).hexdigest(),
    'sam_diagnosis': {'path': str(diagnostic_path), 'sha256': hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()},
    'guidance': guided, 'private_truth_used': False, 'gpu_used': False, 'training': False,
    'results': results}
output = root/'coordination/bounded_skills_20261016/reports/cup8158_guided_membership_pair_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
