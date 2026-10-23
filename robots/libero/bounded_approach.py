"""Approach waypoints from measured scene points and static hand dimensions."""
import numpy as np


def elevated_approach(robot, endpoint, screen, *, clearance_m=.004):
    """Raise above the measured corridor, translate, then descend to stand-off.

    This generates a proposal, never a collision exemption. The caller must
    screen the complete interpolated trajectory with the unchanged checker.
    """
    start = np.asarray(robot['eef_xyz_m'], float)
    goal = np.asarray(endpoint['xyz_m'], float)
    radius = float(screen.radius)  # static hand bounds plus measured payload
    points = np.concatenate((np.asarray(screen.points).reshape(-1, 3),
                             np.asarray(screen.target).reshape(-1, 3)))
    finite = points[np.isfinite(points).all(axis=1)]
    low = np.minimum(start[:2], goal[:2])-radius
    high = np.maximum(start[:2], goal[:2])+radius
    corridor = finite[np.all((finite[:, :2] >= low) & (finite[:, :2] <= high), axis=1)]
    top = float(corridor[:, 2].max()) if len(corridor) else max(start[2], goal[2])
    height = float(max(start[2], goal[2], top+radius+clearance_m))
    # A real raise is useful even if the current pose is already above the
    # obstacles. Its distance comes from the robot's static swept radius.
    height = max(height, float(max(start[2], goal[2])+radius+clearance_m))
    quat = endpoint.get('quat_xyzw', robot['eef_quat_xyzw'])
    route = [{'xyz_m': [*start[:2], height], 'quat_xyzw': robot['eef_quat_xyzw']},
             {'xyz_m': [*goal[:2], height], 'quat_xyzw': quat},
             {'xyz_m': goal.tolist(), 'quat_xyzw': quat}]
    return route, {'source': 'public_scene_corridor_and_static_hand_or_measured_payload',
        'corridor_points': len(corridor), 'measured_corridor_top_m': top,
        'swept_radius_m': radius, 'clearance_m': clearance_m, 'travel_height_m': height,
        'private_pose_used': False, 'requires_unchanged_full_route_screen': True}
