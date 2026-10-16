"""20 Hz smooth references translated into the existing Panda OSC interface."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.spatial.transform import Rotation

from rpent.skill_package.trajectory import Limits, brake, motion_metrics, plan


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
            "joint_positions_rad": np.asarray(obs["robot0_joint_pos"], float).tolist()}


class SmoothMotion:
    """Screen and execute the exact sampled quintic, without per-axis clipping."""

    def __init__(self, primitives, screen, config: MotionConfig = MotionConfig()):
        self.p, self.screen, self.config = primitives, screen, config
        self.trace: list[dict] = []

    def prepare(self, waypoints: list[dict], *, blend: bool = True):
        start = measured_robot(self.p)
        origin = Rotation.from_quat(start["eef_quat_xyzw"])
        points = [np.r_[start["eef_xyz_m"], [0., 0., 0.]]]
        for point in waypoints:
            rotation = Rotation.from_quat(point.get("quat_xyzw", start["eef_quat_xyzw"]))
            points.append(np.r_[point["xyz_m"], (rotation*origin.inv()).as_rotvec()])
        trajectory = plan(points, blend=blend, groups=self.config.groups())
        times, values = trajectory.samples(self.config.hz)
        poses = [{"xyz_m": value[:3].tolist(),
                  "quat_xyzw": (Rotation.from_rotvec(value[3:])*origin).as_quat().tolist(),
                  "time_s": float(t)} for t, value in zip(times, values)]
        evidence = self.screen(poses)
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
        self.p._step_env(action)
        return state, measured_robot(self.p), action

    def run(self, waypoints: list[dict], *, gripper: float = -1., blend: bool = True,
            lookahead=None, request_factory=None, contact_stop=None) -> dict:
        trajectory, origin, poses, screen = self.prepare(waypoints, blend=blend)
        if not screen["passed"]:
            return {"executed": False, "stop_reason": screen["reason"], "steps_used": 0, "screen": screen}
        trace, stop = [], "endpoint"
        for pose in poses[1:]:
            if self.p.env.terminated or self.p.env.truncated:
                stop = "native_stop"
                break
            if lookahead is not None:
                lookahead.poll(trajectory.duration-pose["time_s"], request_factory)
            before, after, action = self._command(pose["xyz_m"], pose["quat_xyzw"], gripper)
            error = float(np.linalg.norm(np.asarray(pose["xyz_m"])-after["eef_xyz_m"]))
            trace.append({"time_s": pose["time_s"], "desired": pose, "before": before, "after": after,
                          "action": action.tolist(), "tracking_error_m": error,
                          "reference_velocity": trajectory.at(pose["time_s"], 1).tolist(),
                          "reference_acceleration": trajectory.at(pose["time_s"], 2).tolist(),
                          "reference_jerk": trajectory.at(pose["time_s"], 3).tolist(), "braking": False})
            if contact_stop is not None and contact_stop(after):
                stop = "public_contact_stop"
                break
            if error > self.config.tracking_error_stop_m:
                stop = "tracking_error"
                break
        # The nominal trajectory ends at zero v/a. An interrupted reference or
        # a late decision uses a p/v/a-continuous measured braking tail.
        if stop in {"tracking_error", "public_contact_stop"} and not (self.p.env.terminated or self.p.env.truncated):
            self._brake(trace, gripper)
        if lookahead is not None and lookahead.pending is not None and not lookahead.pending[1].done():
            stop = "decision_pending_stopped_smoothly"
        self.trace.extend(trace)
        positions = [trace[0]["before"]["eef_xyz_m"], *[row["after"]["eef_xyz_m"] for row in trace]] if trace else []
        segment_ends = trajectory.waypoint_times[:-1] if trajectory.waypoint_times else []
        indices = [min(len(trace), int(round(t*self.config.hz))) for t in segment_ends]
        metrics = motion_metrics(positions, hz=self.config.hz, waypoint_indices=indices) if len(positions) >= 5 else {}
        end_error = float(np.linalg.norm(np.asarray(waypoints[-1]["xyz_m"])-measured_robot(self.p)["eef_xyz_m"]))
        return {"executed": bool(trace), "stop_reason": stop, "steps_used": len(trace), "screen": screen,
                "endpoint_error_m": end_error, "max_tracking_error_m": max((row["tracking_error_m"] for row in trace), default=0.),
                "metrics": metrics, "trace": trace, "config": asdict(self.config),
                "reference_duration_s": trajectory.duration}

    def _brake(self, trace: list[dict], gripper: float) -> None:
        recent = np.array([r["after"]["eef_xyz_m"] for r in trace[-4:]])
        if len(recent) < 3:
            velocity, acceleration = np.zeros(3), np.zeros(3)
        else:
            velocity = (recent[-1]-recent[-2])*self.config.hz
            acceleration = (recent[-1]-2*recent[-2]+recent[-3])*self.config.hz**2
        state = measured_robot(self.p)
        jerk = (recent[-1]-3*recent[-2]+3*recent[-3]-recent[-4])*self.config.hz**3 if len(recent) >= 4 else np.zeros(3)
        tail = brake(state["eef_xyz_m"], velocity, acceleration, jerk=jerk, limits=self.config.groups()[0][1])
        times, positions = tail.samples(self.config.hz)
        poses = [{"xyz_m": p.tolist(), "quat_xyzw": state["eef_quat_xyzw"], "time_s": float(t)}
                 for t, p in zip(times, positions)]
        evidence = self.screen(poses)
        if not evidence["passed"]:
            # Cannot claim a safe Cartesian stop without a screened tail.
            # Do not execute an unchecked trajectory through measured geometry.
            trace[-1]["braking_screen_failure"] = evidence
            return
        offset = trace[-1]["time_s"]
        for pose in poses[1:]:
            if self.p.env.terminated or self.p.env.truncated:
                break
            before, after, action = self._command(pose["xyz_m"], pose["quat_xyzw"], gripper)
            trace.append({"time_s": offset+pose["time_s"], "desired": pose, "before": before, "after": after,
                          "action": action.tolist(), "tracking_error_m": float(np.linalg.norm(np.asarray(pose["xyz_m"])-after["eef_xyz_m"])),
                          "braking": True})
