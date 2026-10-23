"""Public RGB-D feedback for articulated handles and object pushing."""
import numpy as np

from robots.libero.bounded_motion import SmoothMotion, measured_robot
from robots.libero.bounded_screen import PublicRouteScreen

STEP_M = .02
MAX_ADVANCE_M = .40
MAX_STEPS = 400
STAGNANT_CHECKS = 2
PROGRESS_M = .003


def dominant_direction(displacement, prior):
    """Continue on the observed axis with the largest displacement."""
    displacement = np.asarray(displacement, float)
    if np.linalg.norm(displacement) < PROGRESS_M:
        return np.asarray(prior, float)
    axis = int(np.argmax(np.abs(displacement)))
    direction = np.zeros(3)
    direction[axis] = np.sign(displacement[axis])
    return direction


def in_target(entity, target):
    """The measured object centre must enter the measured target footprint."""
    return all(target.lower[i] <= entity.xyz[i] <= target.upper[i] for i in (0, 1))


def run(adapter, parameters, *, push=False):
    key = parameters['anchor_id']
    source = adapter.scene.entities.get(key)
    target = adapter.scene.entities.get(parameters.get('target_id'))
    if source is None or push and target is None:
        return {'steps_used': 0, 'advance_m': 0., 'stop_reason': 'public_anchor_unmeasured', 'checks': []}
    direction = np.asarray(parameters['direction'], float)
    direction /= max(np.linalg.norm(direction), 1e-12)
    started = adapter.p.env.execution_budget()['used_sim_steps']
    initial = np.asarray(source.xyz, float)
    advance, stagnant, checks, traces = 0., 0, [], []
    reason = 'distance_budget'
    for _ in range(int(MAX_ADVANCE_M / STEP_M)):
        if adapter.p.env.terminated or adapter.p.env.truncated:
            reason = 'native_stop'
            break
        if adapter.p.env.execution_budget()['used_sim_steps'] - started >= MAX_STEPS:
            reason = 'control_budget'
            break
        entity = adapter.scene.entities[key]
        if push and in_target(entity, target):
            reason = 'measured_target_region'
            break
        robot = measured_robot(adapter.p)
        axis = int(np.argmax(np.abs(direction)))
        sign = int(np.sign(direction[axis]))
        step = np.zeros(3); step[axis] = sign * STEP_M
        reference = np.array(adapter._contact_pixels(key, handle_only=not push), copy=True)
        capture = adapter.ex.toolkit._state.latest_step
        screen = adapter._cloud_and_ik(key, contact=True)
        if isinstance(screen, PublicRouteScreen):
            screen = screen.translating_contact(axis, robot['eef_xyz_m'])
        endpoint = {'xyz_m': (np.asarray(robot['eef_xyz_m']) + step).tolist(),
                    'quat_xyzw': robot['eef_quat_xyzw']}
        used = adapter.p.env.execution_budget()['used_sim_steps'] - started
        detail = SmoothMotion(adapter.p, screen, adapter.config).run([endpoint],
            gripper=adapter.gripper_command,
            contact_stop=lambda _: adapter.p.env.execution_budget()['used_sim_steps'] - started >= MAX_STEPS)
        traces.extend(detail.get('trace', []))
        if not detail.get('executed'):
            reason = detail['stop_reason']; break
        fit = adapter.refresh(names=[entity.name],
            contact_motion=(key, 'xyz'[axis], sign * STEP_M, reference, capture))
        accepted = fit is not None and fit.get('accepted', False)
        delta = np.asarray(fit['translation_m'], float) if accepted else np.zeros(3)
        progress = float(np.linalg.norm(delta)) if accepted else None
        if progress is None:
            reason = 'contact_motion_unmeasured'
        elif progress < PROGRESS_M:
            stagnant += 1
        else:
            advance += progress
            stagnant = 0
            direction = dominant_direction(delta, direction)
        checks.append({'capture_step': adapter.ex.toolkit._state.latest_step,
            'axis': 'xyz'[axis], 'direction': sign, 'registration': fit,
            'advance_m': advance, 'measured_displacement_m': delta.tolist() if accepted else None,
            'stagnant_checks': stagnant, 'control_steps': detail.get('steps_used', 0)})
        if not accepted or stagnant >= STAGNANT_CHECKS:
            reason = reason if not accepted else 'measured_motion_stalled'
            break
    final = adapter.scene.entities.get(key)
    displacement = (np.asarray(final.xyz) - initial).tolist() if final is not None else None
    return {'steps_used': adapter.p.env.execution_budget()['used_sim_steps'] - started,
        'advance_m': advance, 'object_displacement_m': displacement,
        'stop_reason': reason, 'checks': checks, 'trace': traces,
        'source': 'public_rgbd_surface_registration', 'private_joint_angles_used': False,
        'success': reason in {'native_stop', 'measured_target_region'}}
