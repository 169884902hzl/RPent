# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Test measured support-plane contamination as a cause of pre-lift fit gaps."""
# ruff: noqa: E402 -- select public-only source before geometry imports
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--geometry', type=Path, required=True)
parser.add_argument('--identity', type=Path, required=True)
parser.add_argument('--job', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np
from scipy.spatial import cKDTree

from robots.libero.bounded_payload import _surface_registration
from robots.libero.v5_grasp_geometry import complete_cylindrical_contact_surface
from robots.libero.v5_perception_geometry import measured_work_surface

with np.load(args.geometry) as saved:
    geometry = {key: saved[key] for key in saved.files}
reference, current, scene = (geometry[key] for key in ('reference', 'current', 'scene'))
case = next(r for r in json.loads(args.identity.read_text())['results'] if r['job'] == args.job)
points = {tuple(p['xyz_m']): p for v in case['views'] for p in v['new_payload_pixels']}
queries = np.array(list(points), float).reshape(-1, 3)
anchor = SimpleNamespace(lower=reference.min(0), xyz=np.median(reference, axis=0))
surfaces = {camera: measured_work_surface(geometry[camera], [anchor])
    for camera in ('agentview', 'wrist')}
surface = next((s for s in surfaces.values() if s is not None), None)
assert surface is not None, 'No public measured support; do not invent a plane'
normal, centre = np.asarray(surface['normal_xyz']), np.asarray(surface['centroid_xyz'])


def plane_distance(points):
    return abs((points-centre)@normal)


clean_reference, clean_current = (cloud[plane_distance(cloud) > .001]
    for cloud in (reference, current))
fit, registration = _surface_registration(clean_reference, clean_current, reciprocal=True)
variants = []
for name, measured in (('original', reference), ('plane_removed', fit)):
    variances, axes = np.linalg.eigh(np.cov(measured.T))
    lower, upper = measured.min(0)-.001, measured.max(0)+.001
    for axis in (2, 1, 0):
        member, details = complete_cylindrical_contact_surface(scene.reshape(-1, 1, 3), measured, axes[:, axis])
        mask = (member[:, 0] & (scene >= lower).all(axis=1) & (scene <= upper).all(axis=1))
        cloud = scene[mask]
        variants.append({'name': name, 'principal_axis_index': axis,
            'axis_xyz': axes[:, axis].tolist(), 'variances': variances.tolist(),
            'points': len(cloud), 'query_distance_m': cKDTree(cloud).query(queries)[0].tolist(),
            'evidence': details})
report = {'job': args.job, 'measured_planes': surfaces,
    'query_private_diagnostic_names': list(points.values()),
    'query_plane_distance_m': plane_distance(queries).tolist(),
    'removed_reference_pixels': len(reference)-len(clean_reference),
    'removed_current_pixels': len(current)-len(clean_current),
    'plane_removal_residual_m': .001, 'registration': registration, 'variants': variants,
    'inputs': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in (args.geometry, args.identity)],
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'controls': 0, 'gpu_used': False, 'training': False,
    'runtime_change': False,
    'scope': 'public geometry variants only; private names identify diagnostic queries'}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(args.output), 'job': args.job}))
