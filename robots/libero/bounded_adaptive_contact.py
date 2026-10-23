"""Public RGB-D feedback for articulated handles and object pushing."""
import numpy as np

from robots.libero.bounded_motion import SmoothMotion, measured_robot
from robots.libero.bounded_screen import PublicRouteScreen

STEP_M = .02
MIN_STEP_M = .01
MAX_ADVANCE_M = .40
MAX_STEPS = 400
STAGNANT_CHECKS = 2
PROGRESS_M = .003


def unique_handle_parent(entities, mode):
    """Resolve a duplicated fixture detection only with a unique observed part."""
    from robots.libero.v5_state import fixture_actions
    parents = {entity.part_of for entity in entities.values()
               if entity.visible and entity.part_of is not None}
    candidates = [entity for entity in entities.values()
                  if entity.visible and entity.id in parents and mode in fixture_actions(entity.name)]
    return candidates[0] if len(candidates) == 1 else None


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
    if push:
        direction = np.asarray(target.xyz, float)-source.xyz
        direction[2] = 0.
    elif 'axis' in parameters:
        direction = np.zeros(3)
        direction['xyz'.index(parameters['axis'])] = parameters['direction']
    else:
        direction = np.asarray(parameters['direction'], float)
    direction /= max(np.linalg.norm(direction), 1e-12)
    started = adapter.p.env.execution_budget()['used_sim_steps']
    initial = np.asarray(source.xyz, float)
    advance, stagnant, checks, traces, motions = 0., 0, [], [], []
    contact_displacement = np.zeros(3)
    reason, requested = 'distance_budget', 0.
    for _ in range(round(MAX_ADVANCE_M / MIN_STEP_M)):
        if requested >= MAX_ADVANCE_M - 1e-9:
            break
        if adapter.p.env.terminated or adapter.p.env.truncated:
            reason = 'native_stop' if adapter.p.env.terminated else 'environment_budget'
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
        reference = np.array(adapter._contact_pixels(key, handle_only=not push), copy=True)
        capture = adapter.ex.toolkit._state.latest_step
        screen = adapter._cloud_and_ik(key, contact=True)
        if isinstance(screen, PublicRouteScreen):
            screen = screen.translating_contact(axis, robot['eef_xyz_m'])
        # A collision at the end of a 2 cm increment does not forbid its
        # clear 1 cm prefix. Both routes retain the same geometry and 4 mm
        # clearance; never retry after any physical movement has occurred.
        distances = [min(STEP_M, MAX_ADVANCE_M-requested)]
        if distances[0] > MIN_STEP_M + 1e-9:
            distances.append(MIN_STEP_M)
        for distance in distances:
            step = np.zeros(3); step[axis] = sign * distance
            endpoint = {'xyz_m': (np.asarray(robot['eef_xyz_m']) + step).tolist(),
                        'quat_xyzw': robot['eef_quat_xyzw']}
            detail = SmoothMotion(adapter.p, screen, adapter.config).run([endpoint],
                gripper=adapter.gripper_command,
                contact_stop=lambda _: adapter.p.env.execution_budget()['used_sim_steps'] - started >= MAX_STEPS)
            motions.append({'endpoint': endpoint, 'robot_before': robot,
                'executed': detail.get('executed', False), 'steps_used': detail.get('steps_used', 0),
                'stop_reason': detail['stop_reason'], 'screen': detail.get('screen')})
            if detail.get('executed') or not detail.get('screen', {}).get('collision'):
                break
        traces.extend(detail.get('trace', []))
        if not detail.get('executed'):
            reason = detail['stop_reason']; break
        requested += distance
        if adapter.p.env.terminated or adapter.p.env.truncated:
            reason = 'native_stop' if adapter.p.env.terminated else 'environment_budget'
            break
        fit = adapter.refresh(names=[entity.name],
            contact_motion=(key, 'xyz'[axis], sign * distance, reference, capture))
        accepted = fit is not None and fit.get('accepted', False)
        delta = np.asarray(fit['translation_m'], float) if accepted else np.zeros(3)
        observed = np.asarray(adapter._contact_pixels(key, handle_only=not push)).reshape(-1, 3)
        # The axial fit measures progress, but cannot reveal an orthogonal
        # hinge displacement. Choose the next direction from the two actual
        # public depth surfaces, rather than from that constrained fit.
        observed_delta = (np.median(observed, axis=0)-np.median(reference, axis=0)
            if len(observed) >= 40 and len(reference) >= 40 else None)
        progress = float(np.linalg.norm(delta)) if accepted else None
        if progress is None:
            reason = 'contact_motion_unmeasured'
        elif progress < PROGRESS_M:
            stagnant += 1
        else:
            advance += progress
            stagnant = 0
            if observed_delta is not None:
                direction = dominant_direction(observed_delta, direction)
                contact_displacement += observed_delta
        checks.append({'capture_step': adapter.ex.toolkit._state.latest_step,
            'axis': 'xyz'[axis], 'direction': sign, 'registration': fit,
            'advance_m': advance, 'measured_displacement_m': delta.tolist() if accepted else None,
            'direction_displacement_m': observed_delta.tolist() if observed_delta is not None else None,
            'direction_measurement': 'successive_current_rgbd_contact_surface_medians',
            'stagnant_checks': stagnant, 'control_steps': detail.get('steps_used', 0)})
        if not accepted or stagnant >= STAGNANT_CHECKS:
            reason = reason if not accepted else 'measured_motion_stalled'
            break
    final = adapter.scene.entities.get(key)
    displacement = (np.asarray(final.xyz) - initial).tolist() if final is not None else None
    return {'steps_used': adapter.p.env.execution_budget()['used_sim_steps'] - started,
        'advance_m': advance, 'object_displacement_m': displacement,
        'contact_surface_displacement_m': contact_displacement.tolist(),
        'stop_reason': reason, 'checks': checks, 'trace': traces, 'motion_attempts': motions,
        'source': 'public_rgbd_surface_registration', 'private_joint_angles_used': False,
        'success': reason in {'native_stop', 'measured_target_region'}}
