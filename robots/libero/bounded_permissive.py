"""User-authorized simulation preparation with bounded OSC increments."""
import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_motion import measured_robot, public_control

MAX_PREPARATION_STEPS = 200
MAX_TRANSLATION_STEP_M = .02
MAX_ROTATION_STEP_RAD = .10


def move(primitives, endpoint, *, gripper, config, max_steps=MAX_PREPARATION_STEPS):
    """Go as far as bounded feedback control allows; no sweep/tracking veto."""
    trace = []
    goal = np.asarray(endpoint['xyz_m'], float)
    orientation = Rotation.from_quat(endpoint.get('quat_xyzw', measured_robot(primitives)['eef_quat_xyzw']))
    reason = 'preparation_step_budget'
    for _ in range(max_steps):
        if primitives.env.terminated or primitives.env.truncated:
            reason = 'native_stop'
            break
        robot = measured_robot(primitives)
        delta = goal - robot['eef_xyz_m']
        rotation = (orientation * Rotation.from_quat(robot['eef_quat_xyzw']).inv()).as_rotvec()
        if np.linalg.norm(delta) <= config.endpoint_tolerance_m and np.linalg.norm(rotation) <= .08:
            reason = 'endpoint'
            break
        delta *= min(1., MAX_TRANSLATION_STEP_M / max(np.linalg.norm(delta), 1e-12))
        rotation *= min(1., MAX_ROTATION_STEP_RAD / max(np.linalg.norm(rotation), 1e-12))
        action = np.r_[delta / config.translation_action_scale_m,
                       rotation / config.rotation_action_scale_rad, gripper]
        before, after = public_control(primitives, np.clip(action, -1., 1.))
        trace.append({'before': before, 'after': after, 'action': action.tolist()})
    error = float(np.linalg.norm(goal - measured_robot(primitives)['eef_xyz_m']))
    return {'success': True, 'mode': 'measured_anchor', 'steps_used': len(trace), 'trace': trace,
            'stop_reason': reason, 'endpoint_error_m': error,
            'arrived': reason == 'endpoint', 'sweep_veto': False, 'tracking_error_veto': False,
            'max_steps': max_steps, 'max_translation_step_m': MAX_TRANSLATION_STEP_M,
            'private_geometry_used': False, 'handoff_even_if_endpoint_not_reached': True}


def prepare(adapter, parameters):
    """Use the measured plan endpoint, falling back to measured anchor bounds."""
    key = parameters['anchor_id']
    transfer = parameters['mode'] in {'on', 'in'} and adapter.held == key
    route = adapter._route('carry_to' if transfer else 'move_to',
        {'target_id': parameters['target_id']} if transfer else {'anchor_id': key})
    if route:
        endpoint = route[-1]
    else:
        entity = adapter.scene.entities.get(parameters.get('target_id') if transfer else key)
        if entity is None:
            return {'success': False, 'steps_used': 0, 'reason': 'public_anchor_unmeasured'}
        point = np.asarray(entity.xyz, float).copy()
        point[2] = float(entity.upper[2]) + .10
        endpoint = {'xyz_m': point.tolist()}
    result = move(adapter.p, endpoint, gripper=adapter.gripper_command, config=adapter.config)
    result['endpoint'] = endpoint
    adapter._incremental_touched.update(k for k in (key, parameters.get('target_id')) if k)
    return result
