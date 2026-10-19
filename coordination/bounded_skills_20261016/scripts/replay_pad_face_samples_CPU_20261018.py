# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Test an extra measured-pad sample; retain all sweep and closure checks."""
import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))
import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero import v5_grasp_route as route

root = Path('/public/home/sunyihan/rpent_libero_eval')
original = route.sample_unified_grasps


def sample_pad_edge(*positional, **keywords):
    plan, rows = original(*positional, **keywords)
    pads = [b for b in positional[5]['boxes'] if b['name'].endswith('_pad')]
    # A 2mm cell centred 1mm from the common measured pad boundary remains
    # wholly on both pads. This is a proposal, not a collision exception.
    edge_z = min(b['upper'][2] for b in pads)-.001
    added = []
    for row in rows:
        if row['rejected'] or '_distal_pad' not in row['id']:
            continue
        item = copy.deepcopy(row)
        item['id'] += '_edge_cell'
        site = Rotation.from_quat(item['body_quat_xyzw']).as_matrix()@Rotation.from_euler('z', -np.pi/2).as_matrix()
        shift = -site[:, 2]*(edge_z-item['pad_contact_local_xyz_m'][2])
        contact, entry = (np.asarray(item[key])+shift for key in ('xyz', 'approach_xyz'))
        item.update(xyz=contact.tolist(), approach_xyz=entry.tolist())
        item['pad_contact_local_xyz_m'][2] = edge_z
        item['route'] = route.approach_route(positional[3], positional[4], contact,
            item['body_quat_xyzw'], item['approach'], entry,
            max(w['xyz'][2] for w in row['route']),
            orient_at_pregrasp=row['id'].endswith('_orient_at_pregrasp'))
        added.append(item)
    return plan, [*rows, *added]


records = []
for job in ('9472_0', '9472_1'):
    choices = next((root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*/choices.jsonl'))
    row = json.loads(choices.open().readline())
    ref = row['private_prefix_annotation_state']
    saved = load_annotation_state(ref['path'], ref['sha256'])
    anchor = next(a['id'] for a in row['request']['anchors'] if a['label'] == 'cream cheese')
    adapter = saved['adapter']
    route.sample_unified_grasps = sample_pad_edge
    started = time.perf_counter()
    result = adapter.grasp_geometry(adapter.scene.entities[anchor])
    record = {'job': job, 'context': ref, 'plan': result,
        'cpu_seconds': time.perf_counter()-started,
        'diagnostics': copy.deepcopy(adapter.candidate_diagnostics)}
    records.append(record)
    print(json.dumps({'job': job, 'candidate': result.get('grasp_candidate_id') if result else None,
        'cpu_seconds': record['cpu_seconds']}), flush=True)
    route.sample_unified_grasps = original
report = {'source': str(args.source), 'route_sha256': hashlib.sha256((args.source/'robots/libero/v5_grasp_route.py').read_bytes()).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'records': records,
    'physics_steps': 0, 'gpu_used': False, 'training': False, 'runtime_changed': False,
    'scope': 'Extra static-pad-face proposal on saved public geometry; not physical success'}
with args.output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
