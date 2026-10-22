"""Test recent measured-surface tracking on an actual saved lift rejection."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'input', 'context', 'recorded', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--compare_surface_distance', action='store_true')
    p.add_argument('--use-prior-reference', action='store_true',
        help='Counterfactual: attach the complete last measured instance, with current surface support')
    a = p.parse_args()
    sys.path.insert(0, str(a.source))
    import robots.libero.env_server
    import numpy as np
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation
    from robots.libero.bounded_self_filter import ROBOT_FILTER_MARGIN_M
    from robots.libero.bounded_obstacles import build_obstacles, subtract_instances
    from robots.libero.bounded_screen import PublicRouteScreen
    from robots.libero.v5_geometric_grasp import _voxel

    with gzip.open(a.input, 'rb') as stream:
        old, args, kwargs = pickle.load(stream)
    with gzip.open(a.context, 'rb') as stream:
        context = pickle.load(stream)
    expected = json.loads(a.recorded.read_bytes())['result']
    before = old(*args, **kwargs)
    assert before['reason'] == expected['reason']
    np.testing.assert_allclose(before['at']['xyz_m'], expected['at']['xyz_m'], atol=1e-12, rtol=0.)
    key = context['active_anchor']
    entity = context['entities'][key]
    reference = np.asarray(context['measurement_clouds'][key])
    static = context['committed_grasps'][key]['instance_reference']['stationary_scene']
    points = old.capture_points
    inside = ((points >= np.asarray(entity.lower)-.001).all(axis=1)
        & (points <= np.asarray(entity.upper)+.001).all(axis=1))
    current = points[inside]
    body_distance = cKDTree(reference).query(current)[0]
    static_distance = cKDTree(static).query(current)[0]
    match = body_distance <= .001
    stationary = static_distance <= .004
    if a.compare_surface_distance:
        stationary &= static_distance <= body_distance+.001
    tracked = current[match & ~stationary]
    assert len(tracked) >= 40, 'not enough current public surface support'
    payload_source = reference if a.use_prior_reference else tracked
    robot = context['robot']
    scene = subtract_instances(build_obstacles(points), np.empty((0, 3)), payload_source,
        held_margin_m=ROBOT_FILTER_MARGIN_M)
    payload = (_voxel(payload_source, .002)-robot['eef_xyz_m']) @ Rotation.from_quat(
        robot['eef_quat_xyzw']).as_matrix()
    fresh = PublicRouteScreen(scene, old.geometry, copy.deepcopy(old.ik), opening=old.opening,
        payload_local=payload, initial_pose={'xyz_m': robot['eef_xyz_m'],
            'quat_xyzw': robot['eef_quat_xyzw']}, use_kernel=old.use_kernel,
        check_arm=old.check_arm, capture_points=old.capture_points, capture_key=old.capture_key)
    fresh.support_separation = old.support_separation
    after = fresh(*args, **kwargs)
    report = {'scope': 'saved public RGB-D counterfactual only; not a production fix',
        'physics_steps': 0, 'rpc_calls': 0, 'private_pose_used': False, 'training': False,
        'source': str(a.source), 'inputs': {name: {'path': str(path),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for name, path in [('route', a.input), ('context', a.context), ('recorded', a.recorded)]},
        'reference_capture_step': entity.source_step, 'current_capture_step': context['capture_step'],
        'reference_pixels': len(reference), 'tracked_current_pixels': len(tracked),
        'used_prior_reference': a.use_prior_reference,
        'payload_source_capture_step': entity.source_step if a.use_prior_reference else context['capture_step'],
        'prior_surface_scope': 'conditional attachment prediction; not a new current-frame measurement',
        'association': 'body_nearer_by_1mm' if a.compare_surface_distance else '4mm_static_veto',
        'stationary_veto_pixels': int((match & stationary).sum()),
        'old_payload_points': len(old.payload), 'new_payload_points': len(payload),
        'before': before, 'after': after}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as stream:
        json.dump(report, stream, indent=2, default=lambda v: v.tolist() if hasattr(v, 'tolist') else str(v))
    print(json.dumps({key: report[key] for key in ('reference_pixels', 'tracked_current_pixels',
        'old_payload_points', 'new_payload_points')} | {'before': before['reason'], 'after': after['reason']}))


if __name__ == '__main__':
    main()
