"""Distinguish a visible-centre change from surface motion in saved RGB-D."""
# ruff: noqa: E402 -- select the immutable source before robot imports
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--directory', type=Path, required=True)
parser.add_argument('--row', type=int, default=0)
parser.add_argument('--anchor', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np
from scipy.spatial import cKDTree

from robots.libero.bounded_payload import contact_axis_registration
from robots.libero.bounded_self_filter import public_robot_mask


def load(path):
    with np.load(path) as data:
        return np.asarray(data[data.files[0]])


ledger = args.directory/'choices.jsonl'
row = json.loads(ledger.read_bytes().splitlines()[args.row])
anchor = next(a for a in row['request']['anchors'] if a['id'] == args.anchor)
receipt = next(r for r in row['receipts'] if any(
    c['anchor_id'] == args.anchor and c['displacement_m'] is not None for c in r['changes']))
delta = next(c['displacement_m'] for c in receipt['changes'] if c['anchor_id'] == args.anchor)
reference_file = next((args.directory/f'bounded_precontact_{args.anchor}_target.npz').glob('*.npz'))
reference = load(reference_file)
step = next(e['capture_step'] for e in receipt['evidence'] if e['measurement_id'].endswith(':'+args.anchor))
robot = next(d['execution']['trace'][-1]['after'] for d in row['execution_details']
             if d.get('execution', {}).get('trace'))
xml = Path('/public/home/sunyihan/rpent_libero_eval/.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml')
views, samples, instance_masks = {}, [], []
reported_centre = np.asarray(anchor['xyz_m'])+delta
for camera in ('agentview', 'wrist'):
    path = args.directory/(camera+'_world_high.npz')/f'{step:02d}.npz'
    world = load(path)
    robot_mask = public_robot_mask(world, robot, xml)
    valid = np.isfinite(world).all(axis=2) & (np.abs(world).sum(axis=2) > 1e-6) & ~robot_mask
    cloud = world[valid]
    lower, upper = reference.min(0)-.04, reference.max(0)+.04
    cloud = cloud[((cloud >= lower) & (cloud <= upper)).all(axis=1)]
    residual = cKDTree(cloud).query(reference)[0] if len(cloud) else np.full(len(reference), np.inf)
    views[camera] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'local_public_points': len(cloud), 'reference_support_fraction': {
            str(t): float(np.mean(residual <= t)) for t in (.001, .002, .004, .008)},
        'median_reference_residual_m': float(np.median(residual))}
    samples.append(cloud)
    for mask_path in args.directory.glob(f'v6_sam_{camera}_*.npz/{step:02d}.npz'):
        mask = load(mask_path).astype(bool)
        if mask.shape != world.shape[:2]:
            continue
        points = world[mask & valid]
        if len(points) >= 40:
            instance_masks.append({'path': str(mask_path), 'points': points,
                'centre_distance_m': float(np.linalg.norm(np.median(points, axis=0)-reported_centre))})
current = np.concatenate(samples)
residual = cKDTree(current).query(reference)[0]
report = {'source': str(args.source), 'directory': str(args.directory),
    'ledger_sha256': hashlib.sha256(ledger.read_bytes()).hexdigest(), 'row': args.row,
    'anchor': anchor, 'reported_centre_displacement_m': delta,
    'reported_centre_distance_m': float(np.linalg.norm(delta)), 'capture_step': step,
    'reference_path': str(reference_file), 'reference_sha256': hashlib.sha256(reference_file.read_bytes()).hexdigest(),
    'reference_points': len(reference), 'views': views,
    'combined_reference_support_fraction': {str(t): float(np.mean(residual <= t)) for t in (.001, .002, .004, .008)},
    'axis_fits': {axis: contact_axis_registration(reference, current, i, .02)
                 for i, axis in enumerate('xyz')},
    'scope': 'saved public RGB-D and proprioception only; no controls, no private poses',
    'limitations': ['An axis fit is conditional on no motion in the other axes.',
        'Surface overlap is evidence; it alone does not prove an unchanged object pose.']}
matching = [item for item in instance_masks if item['centre_distance_m'] < .001]
report['current_mask_matches'] = [{k: v for k, v in item.items() if k != 'points'} for item in matching]
if len(matching) == 1:
    from robots.libero.bounded_payload import stationary_surface_registration

    item = matching[0]
    report['guard_replay'] = stationary_surface_registration(reference, current, item['points'])
    report['current_mask_identity_source'] = 'unique saved SAM mask matching reported public anchor centre within 1mm'
args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
print(json.dumps(report))
