"""Measured contact translation, monitored along one screened smooth route."""
from __future__ import annotations

import numpy as np

from robots.libero.bounded_motion import SmoothMotion, measured_robot, settle_osc_hold
from robots.libero.bounded_screen import PublicRouteScreen

# Fixed execution rules, independent of task goals and model parameters.
MAX_DISTANCE_M = .30
CHECK_DISTANCE_M = .02
MAX_SIM_STEPS = 400
NO_PROGRESS_CHECKS = 2


def run_guarded(adapter, parameters):
    key, axis, sign = parameters['anchor_id'], 'xyz'.index(parameters['axis']), parameters['direction']
    start = adapter.p.env.execution_budget()['used_sim_steps']
    settling = settle_osc_hold(adapter.p, adapter.gripper_command, adapter.config)
    if not settling['completed']:
        return {**settling, 'advance_m': 0., 'guarded_stop_reason': 'contact_not_settled'}
    if adapter.p.env.terminated or adapter.p.env.truncated:
        return {**settling, 'advance_m': 0., 'guarded_stop_reason': 'native_stop'}
    adapter.refresh(names=[adapter.scene.entities[key].name])
    initial = measured_robot(adapter.p)
    screen = adapter._cloud_and_ik(key, contact=True)
    if isinstance(screen, PublicRouteScreen):
        screen = screen.translating_contact(axis, initial['eef_xyz_m'])
    reference = np.array(adapter._contact_pixels(key, handle_only=bool(
        adapter.plans.get(key, {}).get('handle_measurement'))), copy=True)
    previous_step = adapter.ex.toolkit._state.latest_step
    motion = SmoothMotion(adapter.p, screen, adapter.config)
    waypoints = []
    for distance in np.arange(CHECK_DISTANCE_M, MAX_DISTANCE_M+.0001, CHECK_DISTANCE_M):
        point = np.array(initial['eef_xyz_m']); point[axis] += sign*distance
        waypoints.append({'xyz_m': point.tolist(), 'quat_xyzw': initial['eef_quat_xyzw']})
    # A complete cabinet may block the nominal far endpoint. Select the
    # longest screened prefix before control; no blocked suffix is issued.
    attempts = []
    while waypoints:
        _, _, _, evidence = motion.prepare(waypoints, blend=True)
        attempts.append({'waypoints': len(waypoints), 'screen': evidence})
        if evidence['passed']:
            break
        at = evidence.get('at', {})
        position = at.get('xyz_m') if isinstance(at, dict) else None
        if position is None:
            waypoints = waypoints[:len(waypoints)//2]
        else:
            distance = sign*(position[axis]-initial['eef_xyz_m'][axis])-.005
            waypoints = [p for p in waypoints
                if sign*(p['xyz_m'][axis]-initial['eef_xyz_m'][axis]) < distance]
    if not waypoints:
        return {'executed': settling['executed'], 'steps_used': settling['steps_used'],
            'trace': settling['trace'], 'advance_m': 0., 'settling': settling,
            'guarded_stop_reason': 'guarded_route_blocked', 'route_attempts': attempts}
    checks, stagnant, advance = [], 0, 0.
    stop = None

    def check(index, measured):
        nonlocal reference, previous_step, stagnant, advance, stop
        fit = adapter.refresh(names=[adapter.scene.entities[key].name],
            contact_motion=(key, parameters['axis'], sign*CHECK_DISTANCE_M, reference, previous_step))
        step = adapter.ex.toolkit._state.latest_step
        measured_progress = None
        if fit and fit['accepted']:
            low, high = sorted(np.asarray(fit['compatible_axis_interval_m'])*sign)
            if low >= .005:
                measured_progress = float(fit['translation_m'][axis]*sign)
                advance += measured_progress
                stagnant = 0
            elif -.005 < low <= high < .005:
                measured_progress = 0.
                stagnant += 1
            else:
                stop = 'contact_surface_motion_ambiguous'
        else:
            stop = 'contact_motion_unmeasured'
        checks.append({'waypoint': index, 'capture_step': step, 'registration': fit,
            'advance_m': advance, 'progress_m': measured_progress, 'stagnant_checks': stagnant})
        reference = np.array(adapter._contact_pixels(key), copy=True)
        previous_step = step
        if not stop and parameters.get('target_id'):
            entity = adapter.scene.entities[key]
            target = adapter.scene.entities[parameters['target_id']]
            if all(target.lower[i] <= entity.xyz[i] <= target.upper[i] for i in range(3)):
                stop = 'measured_target_region'
        if not stop and stagnant >= NO_PROGRESS_CHECKS:
            stop = 'no_measured_progress'
        return stop

    def budget(_):
        nonlocal stop
        if adapter.p.env.execution_budget()['used_sim_steps']-start >= MAX_SIM_STEPS:
            stop = 'guarded_step_budget'
            return True
        return False

    result = motion.run(waypoints, gripper=adapter.gripper_command, blend=True,
        waypoint_check=check, contact_stop=budget)
    stop = stop or ('guarded_distance_budget' if result['stop_reason'] == 'endpoint' else result['stop_reason'])
    result.update(guarded_stop_reason=stop, advance_m=advance, public_progress_checks=checks,
        route_attempts=attempts, settling=settling,
        conditional_contact_translation={'axis': parameters['axis'],
            'source': 'selected_measured_contact_surface', 'measured_success': False})
    result['steps_used'] += settling['steps_used']
    result['trace'] = [*settling['trace'], *result['trace']]
    return result
