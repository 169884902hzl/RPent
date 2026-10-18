# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Screen measured rim normals on saved public geometry without control."""
# ruff: noqa: E402 -- pin recorded imports and disable GPUs before loading
import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--inclined', action='store_true', help='Screen the observed upper rim slope instead of an outer wall')
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_anchor_recovery_20261018_eee8434'
sys.path.insert(0, str(source))
import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_motion import SmoothMotion
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.v5_geometric_grasp import collision_counts, side_site_rotation

results = []
for job, anchor in (('9248_8', 'e99'), ('9248_19', 'e35')):
    choices = next((root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*/choices.jsonl'))
    row = json.loads(choices.open().readline())
    ref = row['private_prefix_annotation_state']
    saved = load_annotation_state(ref['path'], ref['sha256'])
    adapter = PublicPrefixPrediction(copy.deepcopy(saved['adapter']), row['request']).adapter
    points = np.asarray(adapter.scene.measurement_clouds[anchor])
    centre = np.median(points, axis=0)
    robot = row['request']['robot']
    geometry = adapter.geometry
    pads = [b for b in geometry['boxes'] if b['name'].endswith('_pad')]
    tip = np.mean([(np.asarray(b['lower'])+b['upper'])/2 for b in pads], axis=0)
    tip[2] = max(b['upper'][2] for b in geometry['boxes'] if 'finger' in b['name'])
    screen = adapter._cloud_and_ik(anchor, contact=True)
    records = []
    for angle in range(0, 360, 30):
        outward = Rotation.from_euler('z', angle, degrees=True).apply([1., 0., 0.])
        projection = (points-centre)@outward
        edge = points[projection >= np.quantile(projection, .97)]
        point = np.median(edge, axis=0)
        local = points[np.linalg.norm(points-point, axis=1) <= .015]
        record = {'angle_deg': angle, 'measured_points': len(local), 'point_m': point.tolist()}
        records.append(record)
        if len(local) < 8:
            record['rejected'] = 'too_few_local_pixels'
            continue
        values, axes = np.linalg.eigh(np.cov(local.T))
        normal = axes[:, 0]
        if (normal[2] < 0 if args.inclined else np.dot(normal, outward) < 0):
            normal = -normal
        record.update(normal=normal.tolist(), eigenvalues=values.tolist(),
            outward_alignment=float(np.dot(normal, outward)))
        if not args.inclined and (np.dot(normal, outward) < .5 or normal[2] < -.25):
            record['rejected'] = 'measured_normal_does_not_support_lateral_entry'
            continue
        right = np.cross(normal, [0., 0., 1.])
        right /= np.linalg.norm(right)
        variants = record['variants'] = []
        for sign in (1, -1):
            site = side_site_rotation(sign*right, -normal)
            orientation = Rotation.from_matrix(site@Rotation.from_euler('z', np.pi/2).as_matrix())
            xyz = point-site@tip
            entry = xyz+normal*.12
            height = max(robot['eef_xyz_m'][2], entry[2])+.08
            route = [
                {'xyz_m': [*robot['eef_xyz_m'][:2], height], 'quat_xyzw': robot['eef_quat_xyzw']},
                {'xyz_m': [*entry[:2], height], 'quat_xyzw': orientation.as_quat().tolist()},
                {'xyz_m': entry.tolist(), 'quat_xyzw': orientation.as_quat().tolist()},
                {'xyz_m': xyz.tolist(), 'quat_xyzw': orientation.as_quat().tolist()}]
            variant = {'sign': sign, 'route': route}
            variants.append(variant)
            for opening in np.linspace(.08, 0., 9):
                external = collision_counts(screen.points, xyz, site, geometry, opening, clearance_m=.004)
                own = collision_counts(screen.target, xyz, site, geometry, opening, clearance_m=.004)
                if any(external.values()) or own.get('palm', 0):
                    variant['rejected'] = {'opening_m': float(opening), 'scene': external, 'target': own}
                    break
            if 'rejected' not in variant:
                _, _, _, evidence = SmoothMotion(adapter.p, copy.deepcopy(screen), adapter.config).prepare(route)
                variant['screen'] = {k: evidence[k] for k in ('passed', 'reason', 'collision', 'ik_reachable', 'path_min_clearance_m')}
    results.append({'job': job, 'public_anchor': anchor, 'annotation_state': ref,
        'source': 'captured_fused_rgbd_and_static_robot_geometry_only', 'records': records})
suffix = '_inclined' if args.inclined else ''
output = root/f'coordination/bounded_skills_20261016/reports/plate_rim_screen{suffix}_CPU_20261018.json'
output.write_text(json.dumps({'results': results, 'source': str(source),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'physics_steps': 0, 'gpu_used': False, 'training': False, 'inclined': args.inclined,
    'scope': 'geometric option-coverage diagnosis; not a new runtime plan or physical outcome'}, indent=2)+'\n')
print(json.dumps({'output': str(output), 'results': [
    {'job': item['job'], 'supported_normals': sum('variants' in r for r in item['records']),
     'passed': sum(v.get('screen', {}).get('passed', False) for r in item['records'] for v in r.get('variants', []))}
    for item in results]}))
