"""Attribute a real rejected hand point to retained public measurements."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variant', choices=('before', 'after'), default='before')
    args = parser.parse_args()
    previous = json.loads(args.report.read_bytes())
    sys.path.insert(0, previous['source'])
    import robots.libero.env_server
    import numpy as np
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation

    saved = {}
    for name, reference in previous['inputs'].items():
        raw = Path(reference['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == reference['sha256']
        if name in ('route', 'context'):
            saved[name] = pickle.loads(gzip.decompress(raw))
    screen, positional, keyword = saved['route']
    context = saved['context']
    result = screen(*positional, **keyword)
    key = context['active_anchor']
    entity = context['entities'][key]
    robot = context['robot']
    rotation = Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()
    if args.variant == 'after':
        if not previous.get('used_prior_reference'):
            raise ValueError('this replay mode expects the complete-prior-surface counterfactual')
        from robots.libero.bounded_obstacles import build_obstacles, subtract_instances
        from robots.libero.bounded_self_filter import ROBOT_FILTER_MARGIN_M
        from robots.libero.bounded_screen import PublicRouteScreen
        from robots.libero.v5_geometric_grasp import _voxel
        reference = np.asarray(context['measurement_clouds'][key])
        scene = subtract_instances(build_obstacles(screen.capture_points),
            np.empty((0, 3)), reference, held_margin_m=ROBOT_FILTER_MARGIN_M)
        payload = (_voxel(reference, .002)-robot['eef_xyz_m'])@rotation
        fresh = PublicRouteScreen(scene, screen.geometry, copy.deepcopy(screen.ik),
            opening=screen.opening, payload_local=payload,
            initial_pose={'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': robot['eef_quat_xyzw']},
            use_kernel=screen.use_kernel, check_arm=screen.check_arm,
            capture_points=screen.capture_points, capture_key=screen.capture_key)
        fresh.support_separation = screen.support_separation
        screen = fresh
        result = screen(*positional, **keyword)
    assert result['reason'] == previous[args.variant]['reason']
    np.testing.assert_allclose(result['at']['xyz_m'], previous[args.variant]['at']['xyz_m'],
        atol=1e-12, rtol=0.)
    payload_world = screen.payload @ rotation.T+robot['eef_xyz_m']
    clouds = {'scene': screen.points, 'capture': screen.capture_points,
        'active_reference': context['measurement_clouds'][key],
        'attached_payload': payload_world,
        'stationary_reference': context['committed_grasps'][key]['instance_reference']['stationary_scene']}
    trees = {name: cKDTree(points) for name, points in clouds.items() if len(points)}
    failures = result['public_scene_collision_points']
    rows = []
    for box in screen.geometry['boxes']:
        for point in failures.get(box['name'], []):
            point = np.asarray(point)
            distances = {name: float(tree.query(point)[0]) for name, tree in trees.items()}
            scene_index = int(trees['scene'].query(point)[1])
            peers = []
            for name, points in context['measurement_clouds'].items():
                if len(points):
                    peers.append({'id': name, 'name': context['entities'][name].name,
                        'distance_m': float(cKDTree(points).query(point)[0])})
            signed = {}
            for name, pose in [('start', robot), ('failure', result['at'])]:
                site = Rotation.from_quat(pose['eef_quat_xyzw'] if name == 'start'
                    else pose['quat_xyzw']).as_matrix() @ Rotation.from_euler('z', -np.pi/2).as_matrix()
                xyz = pose['eef_xyz_m'] if name == 'start' else pose['xyz_m']
                signed[name] = float(screen._halfspace_distance((point-xyz)[None]@site, box)[0])
            rows.append({'box': box['name'], 'world_point_m': point.tolist(),
                'nearest_cloud_distance_m': distances,
                'nearest_public_instances': sorted(peers, key=lambda p:p['distance_m'])[:5],
                'inside_active_measured_bounds': bool(((point >= entity.lower) & (point <= entity.upper)).all()),
                'signed_box_distance_m': signed,
                'start_allowance_for_point': screen.initial_margin.get(box['name'], {}).get(scene_index)})
    report = {'scope': 'public retained depth and proprioception only; no physics or RPC',
        'source': previous['source'], 'inputs': previous['inputs'],
        'frame': 'same world coordinates used by the recorded public route screen', 'units': 'm',
        'capture_steps': [previous['reference_capture_step'], previous['current_capture_step']],
        'active_id': key, 'active_name': entity.name,
        'clouds': {name: {'points': len(points), 'finite': bool(np.isfinite(points).all()),
            'dtype': str(np.asarray(points).dtype)} for name, points in clouds.items()},
        'failure_reason': result['reason'], 'variant': args.variant, 'rows': rows,
        'physics_steps': 0, 'private_coordinates_used': False, 'training': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'active': entity.name, 'rows': rows}))


if __name__ == '__main__':
    main()
