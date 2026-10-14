"""Check saved collision pixels against the other view's public instance/depth."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('diagnostic', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.diagnostic.read_text())
    ledger = Path(report['ledger']['path'])
    row = json.loads(ledger.read_text().splitlines()[0])
    directory = Path(row['output_dir'])
    with np.load(report['target_cloud']['path']) as loaded:
        target = loaded[loaded.files[0]]
    tree = cKDTree(target)
    records = []
    for view in report['views']:
        other = 'wrist' if view['camera'] == 'agentview' else 'agentview'
        cloud_path = directory / (other + '_world_high.npz') / '01.npz'
        with np.load(cloud_path) as loaded:
            world = loaded[loaded.files[0]]
        meta_path = directory / (other + '_metadata.json') / '01.json'
        meta = json.loads(meta_path.read_text())
        intrinsic = np.array(meta['intrinsic_K'], dtype=float)
        intrinsic[0] *= world.shape[1] / meta['width']
        intrinsic[1] *= world.shape[0] / meta['height']
        extrinsic = np.array(meta['extrinsic_cam2world'])
        inverse = np.linalg.inv(extrinsic)
        for point, pixel in zip(view['collision_points'], view['pixels_yx']):
            camera = (inverse @ np.r_[point, 1.])[:3]
            projected = intrinsic @ camera
            uv = projected[:2] / projected[2]
            cx, cy = np.rint(uv).astype(int)
            samples = []
            if camera[2] > 0:
                for y in range(max(0, cy-1), min(world.shape[0], cy+2)):
                    for x in range(max(0, cx-1), min(world.shape[1], cx+2)):
                        observed = world[y, x]
                        depth = (inverse @ np.r_[observed, 1.])[2]
                        samples.append({'pixel_yx': [y, x],
                            'target_member': bool(tree.query(observed)[0] <= 1e-6),
                            'world_distance_m': float(np.linalg.norm(observed-point)),
                            'camera_depth_residual_m': float(depth-camera[2])})
            records.append({'source_camera': view['camera'], 'source_pixel_yx': pixel,
                'point_world': point, 'other_camera': other, 'projection_uv': uv.tolist(),
                'camera_depth_m': float(camera[2]), 'samples': samples})
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'report.json').write_text(json.dumps({'input': pin(args.diagnostic),
        'producer': pin(Path(__file__)), 'records': records,
        'private_target_pose_used': False, 'CPU_only': True}, indent=2)+'\n')
    print(json.dumps({'records': len(records), 'examples': records[:3]}))


if __name__ == '__main__':
    main()
