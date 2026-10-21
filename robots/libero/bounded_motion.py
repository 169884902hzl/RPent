"""20 Hz smooth references translated into the existing Panda OSC interface."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
from scipy.spatial.transform import Rotation

from rpent.skill_package.trajectory import (
    Limits,
    Segment,
    Trajectory,
    brake,
    motion_metrics,
    plan,
)


@dataclass(frozen=True)
class MotionConfig:
    hz: float = 20.
    translation_speed_m_s: float = .15
    translation_acceleration_m_s2: float = .5
    translation_jerk_m_s3: float = 2.
    rotation_speed_rad_s: float = .4
    rotation_acceleration_rad_s2: float = 1.
    rotation_jerk_rad_s3: float = 4.
    translation_action_scale_m: float = .05
    rotation_action_scale_rad: float = .50
    tracking_error_stop_m: float = .03
    endpoint_tolerance_m: float = .012
    endpoint_settle_steps: int = 30
    reference_lead_s: float = .05
    handoff_max_steps: int = 30
    handoff_stable_steps: int = 4
    handoff_speed_m_s: float = .005
    handoff_rotation_speed_rad_s: float = .02

    def groups(self):
        return ((slice(0, 3), Limits(self.translation_speed_m_s, self.translation_acceleration_m_s2,
                                    self.translation_jerk_m_s3)),
                (slice(3, 6), Limits(self.rotation_speed_rad_s, self.rotation_acceleration_rad_s2,
                                    self.rotation_jerk_rad_s3)))


def measured_robot(primitives) -> dict:
    """Read only proprioceptive keys; object simulator poses are excluded."""
    obs = primitives.env.raw_obs()
    return {"eef_xyz_m": np.asarray(obs["robot0_eef_pos"], float).tolist(),
            "eef_quat_xyzw": np.asarray(obs["robot0_eef_quat"], float).tolist(),
            "gripper_opening_m": float(np.abs(obs["robot0_gripper_qpos"]).sum()),
            "finger_positions_m": np.asarray(obs["robot0_gripper_qpos"], float).tolist(),
            "joint_positions_rad": np.asarray(obs["robot0_joint_pos"], float).tolist()}


def public_control(primitives, action):
    """Save the public sensor stream across motion, gripper and VLA calls."""
    samples = getattr(primitives, '_bounded_motion_samples', [])
    before = measured_robot(primitives)
    index = getattr(primitives, '_bounded_control_index', 0)
    if not samples or samples[-1][0] != index:
        samples.append((index, before))
    primitives._step_env(action)
    after = measured_robot(primitives)
    primitives._bounded_control_index = index+1
    samples.append((index+1, after))
    primitives._bounded_motion_samples = samples[-4:]
    sweep = getattr(primitives, '_bounded_perception_sweep', None)
    if sweep is not None:
        sweep.append({'before': before, 'after': after})
    return before, after


def measured_derivatives(primitives, hz):
    """Estimate current Cartesian v/a/j from four consecutive public samples."""
    samples = getattr(primitives, '_bounded_motion_samples', [])
    if len(samples) < 4 or any(b[0]-a[0] != 1 for a, b in zip(samples, samples[1:])):
        return None
    current = measured_robot(primitives)
    if current != samples[-1][1]:
        return None  # An external caller advanced state outside this stream.
    origin = Rotation.from_quat(current['eef_quat_xyzw'])
    values = np.array([np.r_[state['eef_xyz_m'],
        (Rotation.from_quat(state['eef_quat_xyzw'])*origin.inv()).as_rotvec()] for _, state in samples])
    return tuple(np.diff(values, n=order, axis=0)[-1]*hz**order for order in (1, 2, 3))


def settle_osc_hold(primitives, gripper, config: MotionConfig = MotionConfig()):
    """Damp the existing contact before handing OSC back to a planned skill.

    Zero pose increments target the measured pose and use the ordinary
    velocity damping. They do not request a Cartesian braking sweep through
    contacted geometry. The gripper command is retained. Fresh route screening
    remains mandatory for the next moving skill; this is not a free-space
    collision certificate.
    """
    trace, stable = [], 0
    action = np.r_[np.zeros(6), gripper]
    for index in range(config.handoff_max_steps):
        if primitives.env.terminated or primitives.env.truncated:
            break
        before, after = public_control(primitives, action)
        speed = float(np.linalg.norm(np.array(after['eef_xyz_m'])-before['eef_xyz_m'])*config.hz)
        angular = float((Rotation.from_quat(after['eef_quat_xyzw'])
            * Rotation.from_quat(before['eef_quat_xyzw']).inv()).magnitude()*config.hz)
        stable = stable+1 if (speed <= config.handoff_speed_m_s
            and angular <= config.handoff_rotation_speed_rad_s) else 0
        trace.append({'step': index+1, 'before': before, 'after': after,
            'action': action.tolist(), 'velocity_m_s': speed, 'angular_velocity_rad_s': angular})
        if stable >= config.handoff_stable_steps:
            # The preceding zero-increment OSC target was the BEFORE pose.
            # Preserve that rest reference instead of resetting to feedback.
            primitives._bounded_rest_reference = {
                'pose': {key: before[key] for key in ('eef_xyz_m', 'eef_quat_xyzw')},
                'control_index': primitives._bounded_control_index, 'measured_robot': after}
            break
    native_stop = primitives.env.terminated or primitives.env.truncated
    settled = stable >= config.handoff_stable_steps
    return {'executed': bool(trace), 'completed': settled or native_stop,
        'reason': 'native_stop' if native_stop else 'osc_damped_hold' if settled else 'hold_not_settled',
        'settled': settled, 'steps_used': len(trace), 'trace': trace,
        'source': 'public_proprioception_and_existing_OSC_damping',
        'scope': 'contact settling only; no new Cartesian route requested or certified'}


def _synchronized_brake(position, derivatives, groups):
    """Join translation/rotation braking polynomials on a common knot grid."""
    parts = [brake(position[indices], *(d[indices] for d in derivatives[:2]),
                   jerk=derivatives[2][indices], limits=limit) for indices, limit in groups]
    knots = sorted({0., *[float(t) for part in parts for t in np.cumsum([s.duration for s in part.segments])]})
    segments = []
    for left, right in zip(knots, knots[1:]):
        duration, mid = right-left, (left+right)/2
        coefficients = np.zeros((6, len(position)))
        for (indices, _), part in zip(groups, parts):
            for order in range(6):
                value = part.at(mid, order) if mid < part.duration or order == 0 else np.zeros_like(position[indices])
                # Taylor expansion at this interval's midpoint, shifted to
                # normalized u=0. Each interval is an exact quintic piece.
                for power in range(order+1):
                    coefficients[power, indices] += value*duration**order/math.factorial(order)*math.comb(order, power)*(-.5)**(order-power)
        segments.append(Segment(coefficients, duration))
    return Trajectory(segments)


class SmoothMotion:
    """Screen and execute the exact sampled quintic, without per-axis clipping."""

    def __init__(self, primitives, screen, config: MotionConfig = MotionConfig()):
        self.p, self.screen, self.config = primitives, screen, config
        self.trace: list[dict] = []

    def _reference_start(self, initial_derivatives):
        measured = measured_robot(self.p)
        previous = getattr(self.p, '_bounded_rest_reference', None)
        if (initial_derivatives is None and previous is not None
                and previous['control_index'] == getattr(self.p, '_bounded_control_index', 0)
                and previous['measured_robot'] == measured):
            # Feedback lag is not a new reference acceleration. Adjacent
            # screened motions continue from the prior reference's rest
            # endpoint, while OSC still controls from CURRENT sensors.
            return ({**measured, **previous['pose']}, (np.zeros(6),)*3, 'previous_rest_reference')
        inherited = measured_derivatives(self.p, self.config.hz) if initial_derivatives is None else initial_derivatives
        source = ('explicit' if initial_derivatives is not None else
                  'public_20hz_sensor_stream' if inherited is not None else 'unmeasured_rest_reference')
        return measured, inherited, source

    def prepare(self, waypoints: list[dict], *, blend: bool = True, initial_derivatives=None):
        start, inherited, source = self._reference_start(initial_derivatives)
        origin = Rotation.from_quat(start["eef_quat_xyzw"])
        points = [np.r_[start["eef_xyz_m"], [0., 0., 0.]]]
        for point in waypoints:
            rotation = Rotation.from_quat(point.get("quat_xyzw", start["eef_quat_xyzw"]))
            points.append(np.r_[point["xyz_m"], (rotation*origin.inv()).as_rotvec()])
        try:
            if inherited is not None and any(np.linalg.norm(derivative[indices]) > bound*1.000001
                    for indices, limit in self.config.groups()
                    for derivative, bound in zip(inherited, (limit.velocity, limit.acceleration, limit.jerk))):
                raise RuntimeError('inherited derivatives require continuous braking')
            trajectory = plan(points, blend=blend, groups=self.config.groups(), initial_derivatives=inherited)
        except RuntimeError:
            if inherited is None:
                raise
            # An inherited speed/acceleration/jerk outside nominal bounds
            # cannot vanish instantaneously. First form a continuous brake,
            # then replan from its rest endpoint. The complete curve is
            # screened below; no unchecked prefix is executed.
            prefix = _synchronized_brake(points[0], inherited, self.config.groups())
            times, values = prefix.samples(self.config.hz)
            prefix_poses = [{"xyz_m": value[:3].tolist(),
                "quat_xyzw": (Rotation.from_rotvec(value[3:])*origin).as_quat().tolist(),
                "time_s": float(t)} for t, value in zip(times, values)]
            evidence = self.screen(prefix_poses)
            if not evidence['passed']:
                # An unreachable stop cannot be followed by a retarget.
                # Its distant hypothetical endpoint can otherwise create
                # hours of reference samples before the stop is screened.
                return prefix, origin, prefix_poses, evidence
            rest = prefix.at(prefix.duration)
            suffix = plan([rest, *points[1:]], blend=blend, groups=self.config.groups())
            trajectory = Trajectory(prefix.segments+suffix.segments,
                [prefix.duration+t for t in suffix.waypoint_times])
        times, values = trajectory.samples(self.config.hz)
        poses = [{"xyz_m": value[:3].tolist(),
                  "quat_xyzw": (Rotation.from_rotvec(value[3:])*origin).as_quat().tolist(),
                  "time_s": float(t)} for t, value in zip(times, values)]
        screen_poses = poses
        if source == 'previous_rest_reference':
            current = measured_robot(self.p)
            # The command reference is continuous, but the feedback robot
            # can lag it. Screen that corrective sweep as well; continuing
            # a reference must not skip the physical start of the route.
            screen_poses = [{'xyz_m': current['eef_xyz_m'],
                'quat_xyzw': current['eef_quat_xyzw'], 'time_s': 0.}, *poses]
        evidence = self.screen(screen_poses)
        return trajectory, origin, poses, evidence

    def _command(self, xyz, quat, gripper):
        state = measured_robot(self.p)
        delta = np.asarray(xyz)-state["eef_xyz_m"]
        # Isotropic command bound preserves direction. This is an OSC action
        # bound, not a claim about actual Cartesian speed or acceleration.
        norm = np.linalg.norm(delta)
        delta *= min(1., self.config.translation_action_scale_m/max(norm, 1e-12))
        rotation = (Rotation.from_quat(quat)*Rotation.from_quat(state["eef_quat_xyzw"]).inv()).as_rotvec()
        angle = np.linalg.norm(rotation)
        rotation *= min(1., self.config.rotation_action_scale_rad/max(angle, 1e-12))
        action = np.r_[delta/self.config.translation_action_scale_m,
                       rotation/self.config.rotation_action_scale_rad, float(gripper)]
        before, after = public_control(self.p, action)
        return before, after, action

    def run(self, waypoints: list[dict], *, gripper: float = -1., blend: bool = True,
            lookahead=None, request_factory=None, contact_stop=None, initial_derivatives=None,
            waypoint_check=None) -> dict:
        if hasattr(self.screen, 'rebase_start'):
            self.screen = self.screen.rebase_start(measured_robot(self.p))
        reference_start, inherited, inherited_source = self._reference_start(initial_derivatives)
        trajectory, origin, poses, screen = self.prepare(waypoints, blend=blend, initial_derivatives=initial_derivatives)
        if not screen["passed"]:
            return {"executed": False, "stop_reason": screen["reason"], "steps_used": 0, "screen": screen}
        trace, stop = [], "endpoint"
        checked_waypoints = []
        waypoint_cursor = 0
        # A zero-velocity reference does not mean OSC feedback has already
        # reached it. Keep the screened endpoint fixed for a bounded tail;
        # never replan beyond it or relax the receipt's arrival tolerance.
        endpoint_holds = [{**poses[-1], 'time_s': trajectory.duration+(i+1)/self.config.hz}
                          for i in range(self.config.endpoint_settle_steps)]
        endpoint_hold_steps = 0
        for pose in [*poses[1:], *endpoint_holds]:
            if self.p.env.terminated or self.p.env.truncated:
                stop = "native_stop"
                break
            holding = pose['time_s'] > trajectory.duration
            if holding:
                current = measured_robot(self.p)
                error = np.linalg.norm(np.asarray(poses[-1]['xyz_m'])-current['eef_xyz_m'])
                angle = (Rotation.from_quat(poses[-1]['quat_xyzw'])
                         * Rotation.from_quat(current['eef_quat_xyzw']).inv()).magnitude()
                if error <= self.config.endpoint_tolerance_m and angle <= .05:
                    break
                endpoint_hold_steps += 1
            if lookahead is not None:
                lookahead.poll(max(0., trajectory.duration-pose["time_s"]), request_factory)
            # OSC tracks a position reference with finite lag. Command the
            # next control sample on this already-screened curve, rather
            # than extrapolating a velocity beyond its collision envelope.
            lead_time = min(trajectory.duration, pose['time_s']+min(self.config.reference_lead_s, 1/self.config.hz))
            lead = trajectory.at(lead_time)
            command_pose = {'xyz_m': lead[:3].tolist(),
                'quat_xyzw': (Rotation.from_rotvec(lead[3:])*origin).as_quat().tolist(), 'time_s': lead_time}
            before, after, action = self._command(command_pose["xyz_m"], command_pose["quat_xyzw"], gripper)
            error = float(np.linalg.norm(np.asarray(pose["xyz_m"])-after["eef_xyz_m"]))
            trace.append({"time_s": pose["time_s"], "desired": pose, "command_reference": command_pose,
                          "before": before, "after": after,
                          "action": action.tolist(), "tracking_error_m": error,
                          "reference_velocity": trajectory.at(pose["time_s"], 1).tolist(),
                          "reference_acceleration": trajectory.at(pose["time_s"], 2).tolist(),
                          "reference_jerk": trajectory.at(pose["time_s"], 3).tolist(),
                          **{'command_reference_'+name: trajectory.at(lead_time, order).tolist()
                             for order, name in enumerate(('velocity', 'acceleration', 'jerk'), 1)},
                          "braking": False, "endpoint_hold": holding})
            if contact_stop is not None and contact_stop(after):
                stop = "public_contact_stop"
                break
            if error > self.config.tracking_error_stop_m:
                stop = "tracking_error"
                break
            while (waypoint_check is not None and waypoint_cursor < len(trajectory.waypoint_times or [])
                    and pose['time_s']+1e-9 >= trajectory.waypoint_times[waypoint_cursor]):
                reason = waypoint_check(waypoint_cursor, after)
                checked_waypoints.append({'index': waypoint_cursor, 'time_s': pose['time_s'], 'failure': reason})
                waypoint_cursor += 1
                if reason:
                    stop = 'expected_receipt_'+reason
                    break
            if stop.startswith('expected_receipt_'):
                break
        # The nominal trajectory ends at zero v/a. An interrupted motion
        # continues the last commanded p/v/a reference into its braking tail.
        braking = None
        if (stop in {"tracking_error", "public_contact_stop"} or stop.startswith('expected_receipt_')) and not (self.p.env.terminated or self.p.env.truncated):
            braking = self._brake(trace, gripper, reference_state=(
                lead, tuple(trajectory.at(lead_time, order) for order in (1, 2, 3)), origin))
            if not braking["executed"]:
                stop = "braking_screen_rejected"
        if lookahead is not None and lookahead.pending is not None and not lookahead.pending[1].done():
            if stop == "endpoint":
                stop = "decision_pending_at_rest_endpoint"
            elif braking is not None and braking["executed"]:
                stop = "decision_pending_braked"
        self.trace.extend(trace)
        positions = [trace[0]["before"]["eef_xyz_m"], *[row["after"]["eef_xyz_m"] for row in trace]] if trace else []
        segment_ends = trajectory.waypoint_times[:-1] if trajectory.waypoint_times else []
        indices = [min(len(trace), int(round(t*self.config.hz))) for t in segment_ends]
        metrics = motion_metrics(positions, hz=self.config.hz, waypoint_indices=indices) if len(positions) >= 5 else {}
        metrics['reference_max_acceleration_jump'] = max((float(np.linalg.norm(
            a.at(a.duration, 2)-b.at(0., 2))) for a, b in zip(trajectory.segments, trajectory.segments[1:])), default=0.)
        for name, axes in (('translation', slice(0, 3)), ('rotation', slice(3, 6))):
            metrics['reference_max_'+name+'_acceleration_jump'] = max((float(np.linalg.norm(
                (a.at(a.duration, 2)-b.at(0., 2))[axes]))
                for a, b in zip(trajectory.segments, trajectory.segments[1:])), default=0.)
        metrics['reference_max_jerk_limit_ratio'] = max((segment.maximum(3, axes)/limit.jerk
            for segment in trajectory.segments for axes, limit in self.config.groups()), default=0.)
        end_error = float(np.linalg.norm(np.asarray(waypoints[-1]["xyz_m"])-measured_robot(self.p)["eef_xyz_m"]))
        end_angle = float((Rotation.from_quat(poses[-1]['quat_xyzw'])
                          * Rotation.from_quat(measured_robot(self.p)['eef_quat_xyzw']).inv()).magnitude())
        if stop in {'endpoint', 'decision_pending_at_rest_endpoint'} and (
                end_error > self.config.endpoint_tolerance_m or end_angle > .05):
            stop = 'endpoint_not_reached'
        rested = (trace and ((stop in {'endpoint', 'decision_pending_at_rest_endpoint'}
                              and end_error <= self.config.endpoint_tolerance_m)
                             or (braking is not None and braking.get('completed')
                                 and trace[-1]['tracking_error_m'] <= self.config.endpoint_tolerance_m)))
        if (rested
                and not (self.p.env.terminated or self.p.env.truncated)):
            self.p._bounded_rest_reference = {
                'control_index': getattr(self.p, '_bounded_control_index', 0),
                'measured_robot': measured_robot(self.p),
                'pose': {'eef_xyz_m': trace[-1]['desired']['xyz_m'],
                         'eef_quat_xyzw': trace[-1]['desired']['quat_xyzw']}}
        return {"executed": bool(trace), "stop_reason": stop, "steps_used": len(trace), "screen": screen,
                "endpoint_error_m": end_error, "max_tracking_error_m": max((row["tracking_error_m"] for row in trace), default=0.),
                "metrics": metrics, "trace": trace, "config": asdict(self.config),
                "initial_derivatives": [d.tolist() for d in inherited] if inherited is not None else None,
                "initial_derivatives_source": inherited_source,
                "reference_start_pose": {key: reference_start[key] for key in ('eef_xyz_m', 'eef_quat_xyzw')},
                "reference_duration_s": trajectory.duration,
                "endpoint_hold_steps": endpoint_hold_steps,
                "waypoint_times_s": list(trajectory.waypoint_times), "braking": braking,
                "checked_waypoints": checked_waypoints}

    def _brake(self, trace: list[dict], gripper: float, *, reference_state=None) -> dict:
        """Continue a commanded reference; use sensors for external handoffs."""
        if not trace:
            return {"executed": False, "steps_used": 0, "reason": "no_motion_evidence"}
        state = measured_robot(self.p)
        origin = Rotation.from_quat(state["eef_quat_xyzw"])
        sensors = ([trace[0]["before"]] if "before" in trace[0] else [])+[r["after"] for r in trace]
        recent = np.array([np.r_[s["eef_xyz_m"],
            (Rotation.from_quat(s["eef_quat_xyzw"])*origin.inv()).as_rotvec()] for s in sensors[-4:]])
        derivatives = []
        for order, name in enumerate(("reference_velocity", "reference_acceleration", "reference_jerk"), 1):
            if len(recent) > order:
                derivatives.append(np.diff(recent, n=order, axis=0)[-1]*self.config.hz**order)
            else:
                derivatives.append(np.asarray(trace[-1].get(name, np.zeros(6)), float))
        measured_initial = dict(zip(('velocity', 'acceleration', 'jerk'),
                                    (d.tolist() for d in derivatives)))
        if reference_state is None:
            current = np.r_[state["eef_xyz_m"], np.zeros(3)]
            source = 'public_20hz_sensor_stream'
        else:
            current, derivatives, origin = reference_state
            source = 'last_command_reference'
        velocity, acceleration, jerk = derivatives
        tails = [brake(current[indices], velocity[indices], acceleration[indices], jerk=jerk[indices], limits=limit)
                 for indices, limit in self.config.groups()]
        duration = max(t.duration for t in tails)
        times = np.r_[np.arange(0., duration, 1/self.config.hz), duration]
        positions = [np.concatenate([t.at(min(s, t.duration)) for t in tails]) for s in times]
        poses = [{"xyz_m": p[:3].tolist(), "quat_xyzw": (Rotation.from_rotvec(p[3:])*origin).as_quat().tolist(),
                  "time_s": float(t)} for t, p in zip(times, positions)]
        # The braking tail starts AFTER the executed motion. Its local IK
        # continuation must start at the current measured joints, rather
        # than the joints captured before that motion. Collision evidence
        # and margins remain the original immutable public capture.
        screen = self.screen.with_measured_robot(state) if hasattr(self.screen, 'with_measured_robot') else self.screen
        evidence = screen([{'xyz_m': state['eef_xyz_m'],
            'quat_xyzw': state['eef_quat_xyzw'], 'time_s': 0.}, *poses])
        result = {"executed": False, "steps_used": 0, "screen": evidence,
                  "initial_derivatives": {"velocity": velocity.tolist(), "acceleration": acceleration.tolist(), "jerk": jerk.tolist()},
                  "initial_derivatives_source": source,
                  "measured_initial_derivatives": measured_initial,
                  "reference_start_pose": {"eef_xyz_m": poses[0]['xyz_m'],
                                           "eef_quat_xyzw": poses[0]['quat_xyzw']},
                  "reference_duration_s": duration}
        if not evidence["passed"]:
            # Cannot claim a safe Cartesian stop without a screened tail.
            # Do not execute an unchecked trajectory through measured geometry.
            trace[-1]["braking_screen_failure"] = evidence
            return {**result, "reason": "braking_screen_rejected"}
        offset = trace[-1]["time_s"]
        for time_s, pose in zip(times[1:], poses[1:]):
            if self.p.env.terminated or self.p.env.truncated:
                break
            before, after, action = self._command(pose["xyz_m"], pose["quat_xyzw"], gripper)
            trace.append({"time_s": offset+pose["time_s"], "desired": pose, "before": before, "after": after,
                          "action": action.tolist(), "tracking_error_m": float(np.linalg.norm(np.asarray(pose["xyz_m"])-after["eef_xyz_m"])),
                          **{name: np.concatenate([t.at(min(time_s, t.duration), d) for t in tails]).tolist()
                             for d, name in enumerate(("reference_velocity", "reference_acceleration", "reference_jerk"), 1)},
                          "braking": True})
            result["steps_used"] += 1
        return {**result, "executed": result["steps_used"] > 0,
                "completed": result["steps_used"] == len(times)-1, "reason": "screened_brake"}
