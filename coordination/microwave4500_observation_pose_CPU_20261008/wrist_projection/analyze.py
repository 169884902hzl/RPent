"""Project an explicitly saved public fixed patch into the same wrist RGB-D."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np


def run(download=False):
    root = Path(__file__).resolve().parent
    refs = json.loads((root / 'inputs.json').read_text())
    paths = {}
    for key, record in refs.items():
        path = root / (key + Path(record['path']).suffix)
        if download and not path.exists():
            subprocess.run(['scp', 'gpu5880-ts:' + record['path'], str(path)], check=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('registered public input changed: ' + key)
        paths[key] = path
    meta = json.loads(paths['wrist_calibration'].read_text())
    with np.load(paths['fixed_plane'], allow_pickle=False) as saved:
        cloud = saved[saved.files[0]]
    with np.load(paths['wrist_world'], allow_pickle=False) as saved:
        world = saved[saved.files[0]]
    transform, intrinsic = np.asarray(meta['extrinsic_cam2world']), np.asarray(meta['intrinsic_K'])
    camera = (cloud - transform[:3, 3]) @ transform[:3, :3]
    homogeneous = camera @ intrinsic.T
    uv = homogeneous[:, :2] / homogeneous[:, 2:]
    pixels = np.rint(uv).astype(int)
    valid = ((camera[:, 2] > 0) & (pixels[:, 0] >= 0) & (pixels[:, 0] < meta['width'])
             & (pixels[:, 1] >= 0) & (pixels[:, 1] < meta['height']))
    pixels, camera = pixels[valid], camera[valid]
    measured = (world[pixels[:, 1], pixels[:, 0]] - transform[:3, 3]) @ transform[:3, :3]
    depth_difference = measured[:, 2] - camera[:, 2]
    measured_valid = np.isfinite(measured).all(axis=1) & (measured[:, 2] > 0)
    depths = depth_difference[measured_valid]
    result = {'scope': 'One first post-observation public capture; point counts correlated, not independent trials.',
        'inputs': refs, 'convention': 'Same positive-z forward projection as v6_som and tools._world_from_depth.',
        'fixed_points': len(cloud), 'in_front_and_image': int(valid.sum()),
        'valid_sampled_depth': int(measured_valid.sum()),
        'sampled_depth_minus_fixed_projection_m_percentile': np.percentile(depths, [0, 5, 50, 95, 100]).tolist(),
        'surface_in_front_by_more_than_15mm': int((depths < -.015).sum()),
        'same_depth_within_15mm': int((abs(depths) <= .015).sum()),
        'interpretation': 'Most projected fixed-patch points have matching wrist depth. Empty SAM fixed-frame output cannot be explained by complete absence from this view. These are diagnostic depth tolerances, not changed verifier thresholds.'}
    (root / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'inputs'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--download', action='store_true')
    run(parser.parse_args().download)
