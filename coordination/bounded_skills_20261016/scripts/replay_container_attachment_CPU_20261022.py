"""Compare the actual overwritten lift screen with its cached attachment."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--recorded', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    import numpy as np
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation
    from robots.libero.bounded_screen import PublicRouteScreen

    with gzip.open(args.input, 'rb') as stream:
        original, call_args, call_kwargs = pickle.load(stream)
    with gzip.open(args.context, 'rb') as stream:
        context = pickle.load(stream)
    recorded = json.loads(args.recorded.read_bytes())['result']
    geometry = context['cached_attachment_geometry']
    if geometry is None:
        raise ValueError('the diagnostic must contain the pre-existing attachment screen')
    robot = context['robot']
    reused = PublicRouteScreen(geometry['scene'], original.geometry, copy.deepcopy(original.ik),
        opening=original.opening, contact_points=geometry['target'],
        contact_allowed=original.contact_allowed, payload_local=geometry['payload_local'],
        initial_pose={'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': robot['eef_quat_xyzw']},
        use_kernel=original.use_kernel, check_arm=original.check_arm,
        capture_points=original.capture_points, capture_key=original.capture_key)
    reused.support_separation = original.support_separation
    results = {}
    for name, screen in [('overwritten_contact_reference', original), ('existing_attachment', reused)]:
        screen._pose_geometry_cache = {}
        screen._endpoint_ik_cache = {}
        begin = time.perf_counter()
        result = screen(*call_args, **call_kwargs)
        results[name] = {'wall_s': time.perf_counter()-begin,
            'scene_points': len(screen.points), 'payload_points': len(screen.payload), 'result': result}
    before = results['overwritten_contact_reference']['result']
    assert before['reason'] == recorded['reason']
    for field in ('obstacle_point', 'payload_point'):
        np.testing.assert_allclose(before[field], recorded[field], atol=1e-12, rtol=0.)
    np.testing.assert_allclose(before['at']['xyz_m'], recorded['at']['xyz_m'], atol=1e-12, rtol=0.)
    hit = np.asarray(before['obstacle_point'])
    attached_world = (geometry['payload_local']
        @ Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix().T+robot['eef_xyz_m'])
    pixels = {}
    for camera, world in context['worlds'].items():
        flat = world.reshape(-1, 3)
        ids = np.flatnonzero(np.isfinite(flat).all(axis=1))
        distance, index = cKDTree(flat[ids]).query(hit)
        pixels[camera] = {'distance_m': float(distance),
            'row_col': list(divmod(int(ids[index]), world.shape[1]))}
    result = {'scope': 'same saved public depth/proprioception; no physics, SAM or oracle',
        'training': False, 'physics_steps': 0, 'rpc_calls': 0,
        'source': str(args.source), 'inputs': {name: {'path': str(path),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for name, path in [('route', args.input), ('context', args.context), ('recorded', args.recorded)]},
        'recorded_rejection_reproduced_at_1e_minus_12': True,
        'rejected_pixel': {'xyz_m': hit.tolist(), 'camera_pixels': pixels,
            'distance_to_contact_reference_m': float(cKDTree(context['payload_reference']['target']).query(hit)[0]),
            'distance_to_existing_attached_surface_m': float(cKDTree(attached_world).query(hit)[0]),
            'distance_to_existing_stationary_scene_m': float(cKDTree(geometry['scene']).query(hit)[0])},
        'arms': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2,
        default=lambda value: value.tolist() if hasattr(value, 'tolist') else str(value))+'\n')
    print(json.dumps({'output': str(args.output), 'reproduced': True,
        'arms': {key: value['result']['reason'] for key, value in results.items()},
        'pixel': result['rejected_pixel']}))


if __name__ == '__main__':
    main()
