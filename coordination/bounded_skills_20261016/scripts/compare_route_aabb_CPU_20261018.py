# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Compare complete route evidence on saved public geometry, without controls."""
# ruff: noqa: E402 -- select the pinned source and BLAS settings before imports
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--baseline', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.baseline))

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_self_filter import gripper_at_measured_fingers


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


implementations = {}
for label, source in [('baseline', args.baseline), ('candidate', args.candidate)]:
    geometry = load_module(label+'_grasp', source/'robots/libero/v5_geometric_grasp.py')
    screen = load_module(label+'_screen', source/'robots/libero/bounded_screen.py')
    screen.collision_counts = geometry.collision_counts
    implementations[label] = geometry, screen

root = Path('/public/home/sunyihan/rpent_libero_eval')
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
results = []
for job, index in [('9000_24', 0), ('9001_2', 2), ('8862_60', 0)]:
    directory, = [d for d in (root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*')
        if not d.name.endswith('_legacy')]
    raw = (directory/'choices.jsonl').read_bytes()
    rows = [json.loads(s) for s in raw.splitlines()]
    row = rows[index]
    controls = (c['before'] for d in row['execution_details'] for c in d.get('execution', {}).get('trace', []))
    robot = next(controls, None)
    if robot is None:
        robot = next(c['after'] for old in reversed(rows[:index]) for d in reversed(old['execution_details'])
            for c in reversed(d.get('execution', {}).get('trace', [])))
    assert robot['eef_xyz_m'] == row['request']['robot']['eef_xyz_m']
    geometry = gripper_at_measured_fingers(implementations['baseline'][0].panda_geometry(xml),
                                         robot['finger_positions_m'])
    pose = {k: robot[k] for k in ('eef_xyz_m', 'eef_quat_xyzw')}
    initial = {'xyz_m': pose['eef_xyz_m'], 'quat_xyzw': pose['eef_quat_xyzw']}
    artifacts = row['public_geometry_evidence']

    def load(name):
        info = artifacts[name]
        path = Path(info['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == info['sha256']
        with np.load(path) as stored:
            return stored[stored.files[0]]

    keys = [key[:-6] for key in artifacts if key.startswith('bounded_screen_') and key.endswith('_scene')][:3]
    for key in keys:
        cloud, target, payload = (load(key+suffix) for suffix in ('_scene', '_target', '_payload_local'))
        routes = []
        for delta in ([0., 0., 0.], [.02, 0., 0.], [0., -.02, .02], [0., 0., .05]):
            end = {'xyz_m': (np.asarray(initial['xyz_m'])+delta).tolist(),
                       'quat_xyzw': initial['quat_xyzw']}
            routes.append([initial, end])
        outputs, elapsed = {}, {'baseline': [], 'candidate': []}
        for repeat in range(4):
            labels = ['baseline', 'candidate'] if repeat % 2 == 0 else ['candidate', 'baseline']
            for label in labels:
                # This isolates collision geometry: the deterministic fake IK
                # is identical in both arms; no kinematic speedup is claimed.
                ik = SimpleNamespace(check=lambda *a: {'solution_found': True})
                screen = implementations[label][1].PublicRouteScreen(cloud, geometry, ik,
                    opening=robot['gripper_opening_m'], contact_points=target,
                    contact_allowed=key.endswith('_1'), payload_local=payload, initial_pose=initial)
                start = time.perf_counter()
                outputs[label] = [screen(route) for route in routes]
                elapsed[label].append(time.perf_counter()-start)
            assert outputs['baseline'] == outputs['candidate'], (job, index, key)
        rotation = Rotation.from_quat(initial['quat_xyzw']).as_matrix()@Rotation.from_euler('z', -np.pi/2).as_matrix()
        for opening in [0., .04, .08]:
            before = implementations['baseline'][0].collision_counts(cloud, initial['xyz_m'], rotation,
                geometry, opening, clearance_m=.004, return_points=True)
            after = implementations['candidate'][0].collision_counts(cloud, initial['xyz_m'], rotation,
                geometry, opening, clearance_m=.004, return_points=True)
            assert before == after
        results.append({'job': job, 'row': index, 'screen': key, 'points': len(cloud),
            'choices_sha256': hashlib.sha256(raw).hexdigest(), 'source_artifacts': {
                suffix: artifacts[key+suffix] for suffix in ('_scene', '_target', '_payload_local')},
            'complete_route_evidence_exact': True, 'routes': len(routes),
            'tested_jaw_openings_m': [0., .04, .08], 'raw_seconds': elapsed,
            'median_seconds': {label: float(np.median(times[1:])) for label, times in elapsed.items()}})
report = {'baseline': str(args.baseline), 'candidate': str(args.candidate), 'results': results,
    'source_sha256': {label: {name: hashlib.sha256((source/'robots/libero'/name).read_bytes()).hexdigest()
        for name in ('bounded_screen.py', 'v5_geometric_grasp.py')}
        for label, source in [('baseline', args.baseline), ('candidate', args.candidate)]},
    'controls': 0, 'private_truth_used': False, 'training': False, 'confirmation': False,
    'scope': 'exact saved public route geometry; deterministic fake IK; not request or physical throughput'}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps([{'job': r['job'], 'screen': r['screen'], 'exact': True,
    'median_seconds': r['median_seconds']} for r in results]))
