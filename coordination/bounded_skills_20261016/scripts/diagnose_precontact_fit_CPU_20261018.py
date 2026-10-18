# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Trace rejected rigid fits using saved public captures, without controls."""
import argparse
import hashlib
import json
import os
import runpy
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--working-adapter', type=Path, required=True)
parser.add_argument('--job', required=True)
parser.add_argument('--row', type=int, default=1)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
replay = Path(__file__).with_name('replay_precontact_surface_CPU_20261018.py')
sys.argv = [str(replay), '--source', str(args.source), '--working-adapter',
    str(args.working_adapter), '--job', args.job, '--row', str(args.row),
    '--output', str(args.output.with_name(args.output.stem+'_replay.json'))]
data = runpy.run_path(str(replay), run_name='__main__')

import numpy as np  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
from scipy.spatial.transform import Rotation  # noqa: E402


def voxel(points):
    points = np.asarray(points, float).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1)]
    _, ids = np.unique(np.floor(points/.001).astype(int), axis=0, return_index=True)
    return points[np.sort(ids)]


def trace_fit(predicted, measured, *, translation_only=False, reciprocal=False):
    source, target = voxel(predicted), voxel(measured)
    source = source[::max(1, len(source)//8000)]
    tree = cKDTree(target)
    centre = source.mean(0)
    rotation, shift = np.eye(3), np.zeros(3)
    trace = []
    for _ in range(30):
        transformed = (source-centre)@rotation.T+centre+shift
        distance, ids = tree.query(transformed)
        supported = distance <= .008
        if supported.sum() < 40 or supported.mean() < .5:
            break
        geometric_support = float(supported.mean())
        if reciprocal:
            reverse = cKDTree(transformed).query(target[ids])[1]
            supported &= reverse == np.arange(len(source))
            if supported.sum() < 40:
                break
        a, b = transformed[supported], target[ids[supported]]
        ac, bc = a.mean(0), b.mean(0)
        u, singular, vt = np.linalg.svd((a-ac).T@(b-bc))
        delta_rotation = vt.T@u.T
        if np.linalg.det(delta_rotation) < 0:
            vt[-1] *= -1
            delta_rotation = vt.T@u.T
        if translation_only:
            delta_rotation = np.eye(3)
        delta = bc-ac@delta_rotation.T
        shift = (centre+shift)@delta_rotation.T+delta-centre
        rotation = delta_rotation@rotation
        corrected = (predicted-centre)@rotation.T+centre+shift
        change = (a-ac)@delta_rotation.T+bc-a
        trace.append({'iteration': len(trace), 'supported': int(supported.sum()),
            'supported_fraction': float(supported.mean()), 'geometric_support_fraction': geometric_support,
            'median_residual_m': float(np.median(tree.query((source-centre)@rotation.T+centre+shift)[0])),
            'rotation_rad': float(Rotation.from_matrix(rotation).magnitude()),
            'translation_m': shift.tolist(), 'singular_values': singular.tolist(),
            'maximum_surface_displacement_m': float(np.linalg.norm(corrected-predicted, axis=1).max()),
            'max_iterate_change_m': float(np.linalg.norm(change, axis=1).max())})
        if np.linalg.norm(change, axis=1).max() < .00001:
            break
    return {'translation_only_diagnostic': translation_only, 'reciprocal_diagnostic': reciprocal,
        'iterations': trace,
        'source_samples': len(source), 'target_samples': len(target),
        'source_bounds_m': [source.min(0).tolist(), source.max(0).tolist()],
        'target_bounds_m': [target.min(0).tolist(), target.max(0).tolist()],
        'initial_residual_quantiles_m': np.quantile(tree.query(source)[0], [0, .1, .5, .9, 1]).tolist()}


report = {'scope': 'CPU saved-public ICP diagnosis; alternative fit is not runtime behavior',
    'job': args.job, 'source': str(args.source), 'row': args.row,
    'rigid': trace_fit(data['reference'], data['instance']),
    'translation_only': trace_fit(data['reference'], data['instance'], translation_only=True),
    'reciprocal': trace_fit(data['reference'], data['instance'], reciprocal=True),
    'blockers': data['blockers'].tolist(), 'controls': 0, 'gpu_used': False,
    'private_truth_used': False, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
reference = data['adapter'].committed_grasps[data['key']]['instance_reference']
report['blocker_distances_m'] = {name: cKDTree(points).query(data['blockers'])[0].tolist()
    for name, points in [('old_instance', data['reference']), ('current_instance', data['instance']),
        ('old_non_target', reference['stationary_scene'])]}
geometry_path = args.output.with_suffix('.npz')
np.savez_compressed(geometry_path, reference=data['reference'], current=data['instance'],
    stationary=reference['stationary_scene'], blockers=data['blockers'],
    scene=data['adapter']._base_geometry[0],
    **{camera: data['adapter']._self_filtered_world(np.asarray(data['frame'](camera+'_world_high.npz')))
       for camera in ('agentview', 'wrist')})
report['public_geometry'] = {'path': str(geometry_path),
    'sha256': hashlib.sha256(geometry_path.read_bytes()).hexdigest()}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(args.output), 'job': args.job,
    'rigid_final': report['rigid']['iterations'][-1],
    'translation_final': report['translation_only']['iterations'][-1],
    'reciprocal_final': report['reciprocal']['iterations'][-1]}))
