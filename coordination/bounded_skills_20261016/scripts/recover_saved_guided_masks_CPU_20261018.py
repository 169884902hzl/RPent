# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Recover saved public guided membership for a CPU diagnostic, without SAM calls."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

parser = argparse.ArgumentParser()
parser.add_argument('--job', required=True)
parser.add_argument('--row', type=int, required=True)
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
directory, = (root/'results/bounded_skills/feasibility_20261017'/('job'+args.job)).glob('*oracle*')
row = json.loads((directory/'choices.jsonl').read_bytes().splitlines()[args.row])
key = row['request']['robot']['held_anchor_id']
records = [r for r in row['instance_boundary_evidence'][key]
    if r.get('source') == 'current_measured_instance_interior_point_sam']
results = []
for record in records:
    camera = record['camera']
    result = {'camera': camera, 'query': {'point': record.get('point_row_col')},
        'found': bool(record.get('member_pixels'))}
    if not result['found']:
        result['reason'] = record.get('reason')
    else:
        artifact = row['public_geometry_evidence'][f'bounded_payload_guided_{key}_{camera}']
        raw = Path(artifact['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == artifact['sha256']
        with np.load(artifact['path']) as data:
            points = data[data.files[0]]
        with np.load(directory/(camera+'_world_high.npz')/f"{record['capture_step']:02d}.npz") as data:
            world = data[data.files[0]]
        finite = np.isfinite(world).all(axis=2)
        mask = np.zeros(finite.shape, bool)
        mask[finite] = cKDTree(points).query(world[finite])[0] <= 1e-6
        path = base/'preparation'/f'{args.job}_{camera}_guided_saved_mask_row{args.row}.npz'
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, mask=mask)
        result.update(mask=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            score=record['score'], source_artifact=artifact)
    results.append(result)
output = base/'reports'/f'{args.job}_saved_guided_masks_row{args.row}_CPU_20261018.json'
output.write_text(json.dumps({'private_truth_used': False, 'controls': 0, 'gpu_used': False,
    'limitation': 'Saved accepted membership, not the full raw SAM reply; CPU membership diagnostic only.',
    'results': results}, indent=2)+'\n')
print(output)
