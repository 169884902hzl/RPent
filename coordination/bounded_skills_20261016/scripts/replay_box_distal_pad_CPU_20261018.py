# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare pad-centre and distal-pad contact on two saved public box states."""
# ruff: noqa: E402 -- select the immutable source before robot imports
import argparse
import copy
import hashlib
import json
import os
import sys
import time
from collections import Counter
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


def distal(*positional, **keywords):
    plan, rows = original(*positional, **keywords)
    geometry = positional[5]
    pads = [box for box in geometry['boxes'] if box['name'].endswith('_pad')]
    midpoint = np.mean([(np.asarray(box['lower'])+box['upper'])/2 for box in pads], axis=0)
    # The final 2 mm remain inside both measured pad faces. This shifts
    # placement on the same measured flank, without moving that flank.
    edge = min(box['upper'][2] for box in pads)-.002
    added = []
    for row in rows:
        if row['rejected']:
            continue
        item = copy.deepcopy(row)
        item['id'] += '_distal_pad'
        site = Rotation.from_quat(item['body_quat_xyzw']).as_matrix()@Rotation.from_euler('z', -np.pi/2).as_matrix()
        shift = -site[:, 2]*(edge-midpoint[2])
        contact = np.asarray(item['xyz'])+shift
        entry = np.asarray(item['approach_xyz'])+shift
        item['xyz'], item['approach_xyz'] = contact.tolist(), entry.tolist()
        item['route'] = route.approach_route(positional[3], positional[4], contact,
            item['body_quat_xyzw'], item['approach'], entry,
            max(waypoint['xyz'][2] for waypoint in row['route']),
            orient_at_pregrasp=row['id'].endswith('_orient_at_pregrasp'))
        item['pad_contact_local_z_m'] = edge
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
    before = next(d for d in row['candidate_screen_diagnostics'] if d.get('anchor_id') == anchor and d.get('stage') == 'grasp_route_search')
    route.sample_unified_grasps = distal
    started = time.perf_counter()
    result = adapter.grasp_geometry(adapter.scene.entities[anchor])
    diagnostics = copy.deepcopy(adapter.candidate_diagnostics)
    record = {'job': job, 'context': ref, 'anchor': anchor,
        'before_selected': before['selected'], 'after_plan': result,
        'cpu_seconds': time.perf_counter()-started, 'diagnostics': diagnostics}
    records.append(record)
    print(json.dumps({'job': job, 'before_selected': before['selected'],
        'after_selected': result.get('grasp_candidate_id') if result else None,
        'cpu_seconds': record['cpu_seconds'],
        'reasons': dict(Counter(r.get('route_screen', {}).get('reason', r.get('reason'))
            for d in diagnostics for r in d.get('candidates', [])))}), flush=True)
    route.sample_unified_grasps = original
report = {'source': str(args.source), 'source_sha256': hashlib.sha256((args.source/'robots/libero/bounded_skills.py').read_bytes()).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'records': records, 'physics_steps': 0, 'gpu_used': False, 'training': False,
    'limitation': 'Saved public geometry and numerical route screen only; not physical grasp success.'}
args.output.write_text(json.dumps(report, indent=2)+'\n')
