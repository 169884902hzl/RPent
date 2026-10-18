# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Explain disconnected current RGB-D samples without changing ownership."""
# ruff: noqa: E402 -- select the public geometry implementation before imports
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
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np
from scipy.spatial import cKDTree

from robots.libero.bounded_payload import _surface_registration
from robots.libero.v5_perception_geometry import measured_work_surface

with np.load(args.geometry) as saved:
    data = {k: saved[k] for k in saved.files}
reference, current, queries = (data[k] for k in ('reference', 'current', 'blockers'))
anchor = SimpleNamespace(lower=reference.min(0), xyz=np.median(reference, axis=0))
surface = next(s for c in ('agentview', 'wrist')
               if (s := measured_work_surface(data[c], [anchor])) is not None)
normal, origin = np.asarray(surface['normal_xyz']), np.asarray(surface['centroid_xyz'])
reference, current = (cloud[abs((cloud-origin)@normal) > .001]
                      for cloud in (reference, current))
registered, fit = _surface_registration(reference, current, reciprocal=True)
lower, upper = registered.min(0)-.001, registered.max(0)+.001
target_tree, previous_tree = cKDTree(current), cKDTree(registered)
static_tree = cKDTree(data['stationary'])
views = []
for camera in ('agentview', 'wrist'):
    world = data[camera]
    valid = np.isfinite(world).all(axis=2)
    ids = np.flatnonzero(valid)
    tree = cKDTree(world.reshape(-1, 3)[ids])
    distances, closest = tree.query(queries)
    for q, distance, flat_id in zip(queries, distances, ids[closest]):
        y, x = np.unravel_index(flat_id, valid.shape)
        patch = []
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                yy, xx = y+dy, x+dx
                if not (0 <= yy < len(world) and 0 <= xx < world.shape[1]):
                    continue
                p = world[yy, xx]
                if not valid[yy, xx]:
                    patch.append({'offset_yx': [dy, dx], 'self_filtered': True})
                    continue
                patch.append({'offset_yx': [dy, dx], 'xyz_m': p.tolist(),
                    'query_gap_m': float(np.linalg.norm(p-q)),
                    'current_instance_distance_m': float(target_tree.query(p)[0]),
                    'registered_reference_distance_m': float(previous_tree.query(p)[0]),
                    'stationary_scene_distance_m': float(static_tree.query(p)[0]),
                    'inside_registered_bounds': bool(((p >= lower) & (p <= upper)).all())})
        views.append({'camera': camera, 'query': q.tolist(), 'nearest_distance_m': float(distance),
            'pixel_yx': [int(y), int(x)], 'patch': patch})
report = {'scope': 'CPU public-depth neighbourhood diagnostic; no membership change',
    'geometry': {'path': str(args.geometry), 'sha256': hashlib.sha256(args.geometry.read_bytes()).hexdigest()},
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'registered_bounds': [lower.tolist(), upper.tolist()], 'support_plane': surface,
    'registration': fit, 'views': views, 'controls': 0, 'gpu_used': False, 'private_truth_used': False}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(args.output), 'views': [{k: v for k, v in item.items() if k != 'patch'}
                                                     for item in views]}))
