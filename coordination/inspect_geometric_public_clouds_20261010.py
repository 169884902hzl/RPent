"""Reproduce geometry candidates from saved public RGB-D and robot pose only."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.v5_geometric_grasp import panda_geometry, remove_measured_hand, sample_grasps


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('packet', type=Path)
    parser.add_argument('--robot-xml', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inputs = json.loads((args.packet / 'records.json').read_text())
    geometry = panda_geometry(args.robot_xml)
    args.output.mkdir(exist_ok=False, parents=True)
    figure, axes = plt.subplots(len(inputs), 3, figsize=(12, 3.7 * len(inputs)))
    records = []
    for index, item in enumerate(inputs):
        parent = args.packet / item['category']
        def read(name):
            path = parent / name
            expected = next(f['copied']['sha256'] for f in item['files']
                            if Path(f['copied']['path']).name == name)
            if pin(path)['sha256'] != expected:
                raise ValueError('public cloud bytes changed')
            with np.load(path) as archive:
                return archive[archive.files[0]]
        target = read('target.npz')
        robot = item['public_robot']
        scene = np.concatenate([read(view + '_world.npz').reshape(-1, 3)
                                for view in ('agentview', 'wrist')])
        scene, removed = remove_measured_hand(scene, robot['robot0_eef_pos'], robot['robot0_eef_quat'],
            geometry, sum(abs(q) for q in robot['robot0_gripper_qpos']))
        rotation = Rotation.from_quat(robot['robot0_eef_quat']).as_matrix()
        yaw = float(np.arctan2(rotation[1, 0], rotation[0, 0]))
        started = time.monotonic()
        plan, candidates = sample_grasps(target, scene, item['public_name'], robot['robot0_eef_pos'],
            yaw, geometry, current_body_quat_xyzw=robot['robot0_eef_quat'])
        wall = time.monotonic() - started
        for column, (x, y) in enumerate(((0, 1), (0, 2), (1, 2))):
            ax = axes[index, column]
            ax.scatter(target[:, x], target[:, y], c=target[:, 2], s=.6, cmap='viridis')
            if plan:
                ax.scatter(plan['xyz'][x], plan['xyz'][y], marker='x', s=80, color='red', label='chosen contact')
            ax.set_aspect('equal', adjustable='datalim')
            ax.set_xlabel('XYZ'[x] + ' (world metres)');ax.set_ylabel('XYZ'[y] + ' (world metres)')
            ax.set_title(item['category'] + ': measured public surface')
        row = {'category': item['category'], 'case_name': item['case_name'],
            'plan': plan, 'ranked_candidates': candidates, 'removed_public_hand_points': removed,
            'accepted': sum(not r['rejected'] for r in candidates), 'n_candidates': len(candidates),
            'rejection_counts': dict(Counter(reason for r in candidates for reason in r['rejected'])),
            'candidate_generation_wall_s': wall, 'public_fields_only': True,
            'physical_execution': False, 'training_allowed': False, 'qualification_allowed': False}
        records.append(row)
        print(json.dumps({k:row[k] for k in ('category','accepted','n_candidates',
                                            'candidate_generation_wall_s','rejection_counts')}), flush=True)
    figure.tight_layout()
    figure.savefig(args.output / 'public_clouds.png', dpi=170)
    plt.close(figure)
    path = args.output / 'records.json'
    path.write_text(json.dumps(records, indent=2) + '\n')
    manifest = {'inputs': pin(args.packet / 'manifest.json'), 'records': pin(path),
        'figure': pin(args.output / 'public_clouds.png'), 'producer': pin(Path(__file__)),
        'geometry_source': pin(Path(sample_grasps.__code__.co_filename)),
        'robot_geometry': geometry['references'], 'physical_execution': False,
        'limits': ['These three startup cases are diagnostic, not a method success-rate sample.'],
        'training_allowed': False, 'qualification_allowed': False}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
