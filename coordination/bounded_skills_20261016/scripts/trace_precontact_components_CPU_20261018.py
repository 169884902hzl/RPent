# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Locate surface ownership changes in a saved public pre-lift fit, without IO."""
# ruff: noqa: E402 -- pin the measured-geometry implementation before imports
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

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

from robots.libero.bounded_payload import (
    _surface_registration,
    complete_spatial_payload_component,
)
from robots.libero.v5_grasp_geometry import (
    complete_contact_surface,
    complete_cylindrical_contact_surface,
    complete_planar_boundary,
)

with np.load(args.geometry) as saved:
    arrays = {key: saved[key] for key in saved.files}
reference, current = arrays['reference'], arrays['current']
stationary, scene = arrays['stationary'], arrays['scene']
audit = next(r for r in json.loads(args.identity.read_text())['results'] if r['job'] == args.job)
points = [p for v in audit['views'] for p in v['new_payload_pixels']]
unique = {tuple(p['xyz_m']): p for p in points}
points = list(unique.values())
queries = np.asarray([p['xyz_m'] for p in points]).reshape(-1, 3)
corrected, registration = _surface_registration(reference, current, reciprocal=True)
lower, upper = corrected.min(0)-.001, corrected.max(0)+.001
stages = []


def record(name, cloud):
    distance = cKDTree(cloud).query(queries)[0]
    stages.append({'name': name, 'points': len(cloud),
        'query_distance_m': distance.tolist()})


record('old_reference', reference)
record('current_instance', current)
record('stationary_scene', stationary)
record('registered_reference', corrected)
for camera in ('agentview', 'wrist'):
    world = arrays[camera]
    mask, _ = complete_contact_surface(world, corrected, current_boundary=True)
    extent = (world >= lower).all(axis=2) & (world <= upper).all(axis=2)
    record(camera+'_contact_before_extent', world[mask])
    record(camera+'_contact_inside_extent', world[mask & extent])
    mask, _ = complete_planar_boundary(world, mask & extent)
    record(camera+'_post_extent_plane', world[mask])
_, axes = np.linalg.eigh(np.cov(corrected.T))
mask, _ = complete_cylindrical_contact_surface(scene.reshape(-1, 1, 3), corrected, axes[:, -1])
record('circular_sections', scene[mask[:, 0]
    & (scene >= lower).all(axis=1) & (scene <= upper).all(axis=1)])
raw = np.concatenate([arrays[c].reshape(-1, 3) for c in ('agentview', 'wrist')])
mask, component = complete_spatial_payload_component(raw, current, stationary, lower, upper)
record('spatial_component', raw[mask])
report = {'job': args.job, 'queries': points, 'stages': stages,
    'registration': registration, 'component': component,
    'queries_inside_reference_extent': ((queries >= lower).all(axis=1)
        & (queries <= upper).all(axis=1)).tolist(),
    'source': str(args.source),
    'inputs': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in (args.geometry, args.identity)],
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'controls': 0, 'gpu_used': False, 'training': False,
    'scope': 'public geometry stages; private identity only names diagnostic queries'}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(args.output), 'job': args.job, 'queries': len(points)}))
