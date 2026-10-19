# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Attribute captured handoff blockers using public RGB-D and robot meshes."""

import argparse
import json
import pickle
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_bytes())
    sys.path.insert(0, report['source'])
    import numpy as np
    from PIL import Image
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation

    from robots.libero.bounded_self_filter import gripper_at_measured_fingers

    directory = Path(report['directory'])
    summary = json.loads((directory/'replay/summary.json').read_bytes())
    public = pickle.loads(Path(summary['endpoint']['path']).read_bytes())['public_runtime']
    request = json.loads((directory/'first_self_request.json').read_bytes())
    robot = request['robot']
    geometry = gripper_at_measured_fingers(public['adapter']['geometry'],
        public['primitive']['_bounded_motion_samples'][-1][1]['finger_positions_m'])
    reference = public['adapter']['payload_reference']
    site = Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix() @ Rotation.from_euler('z', -np.pi/2).as_matrix()
    moved = ((reference['target']-reference['robot']['eef_xyz_m']) @
        Rotation.from_quat(reference['robot']['eef_quat_xyzw']).as_matrix()) @ Rotation.from_quat(
        robot['eef_quat_xyzw']).as_matrix().T+robot['eef_xyz_m']
    points = np.unique(np.concatenate([np.asarray(p).reshape(-1, 3)
        for c in report['rows'][0]['checks']
        for p in c['geometry'].get('public_scene_collision_points', {}).values()
        if len(p)]), axis=0)
    views = public['scene']['measurement_clouds_by_view'].get(robot['held_anchor_id'], {})
    rows = []
    for point in points:
        local = (point-robot['eef_xyz_m']) @ site
        meshes = []
        for box in geometry.get('visual_boxes', geometry['boxes']):
            eq = box.get('convex_halfspaces')
            if eq is not None:
                eq = np.asarray(eq)
                distance = float(np.max(local @ eq[:, :3].T+eq[:, 3]))
                meshes.append({'name': box['name'], 'maximum_halfspace_residual_m': distance})
        pixels = []
        for camera in ('agentview', 'wrist'):
            step = report['capture_step']
            with np.load(directory/(camera+'_world_high.npz')/f'{step:02d}.npz') as data:
                world = data[data.files[0]]
            distance, index = cKDTree(world.reshape(-1, 3)).query(point)
            y, x = np.unravel_index(index, world.shape[:2])
            rgb = np.asarray(Image.open(directory/(camera+'_high.png')/f'{step:02d}.png'))
            view = views.get(camera, {})
            semantic = np.asarray(view.get('xyz_world', [])).reshape(-1, 3)
            pixels.append({'camera': camera, 'pixel_yx': [int(y), int(x)],
                'distance_m': float(distance), 'rgb': rgb[y, x].tolist(),
                'current_semantic_distance_m': float(cKDTree(semantic).query(point)[0]) if len(semantic) else None,
                'semantic_capture_step': view.get('source_step')})
        rows.append({'point_m': point.tolist(), 'gripper_site_local_m': local.tolist(),
            'visual_hulls': sorted(meshes, key=lambda v: v['maximum_halfspace_residual_m'])[:2],
            'precontact_scene_distance_m': float(cKDTree(reference['scene']).query(point)[0]),
            'predicted_moving_surface_distance_m': float(cKDTree(moved).query(point)[0]),
            'pixels': pixels})
    args.output.write_text(json.dumps({'source': report['source'], 'directory': str(directory),
        'rows': rows, 'physics_steps': 0, 'sam_calls': 0, 'private_coordinates_used': False,
        'scope': 'attribution only; no changed collision margins or runtime classification'}, indent=2))
    print(json.dumps({'points': len(rows), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
