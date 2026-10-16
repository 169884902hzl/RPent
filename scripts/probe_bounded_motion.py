"""Paired original-scene motion diagnostics; no SAM, VLA or training."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from robots.libero.bounded_motion import SmoothMotion, measured_robot
from rpent.skill_package.trajectory import motion_metrics


class LocalRPC:
    """In-process diagnostic transport; all motion still uses public sensors."""
    def __init__(self, facade):
        self.facade = facade
    def call(self, method, args=(), kwargs=None, **_):
        return self.facade._rpc[method](*args, **(kwargs or {}))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x))+"\n")


def original_session(suite: str, task: int, seed: int, budget: int):
    """Own a fresh original simulator and its diagnostic-only private facade."""
    from scripts.probe_v5_skill501_original import make_probe_env
    from robots.libero.tools import LiberoPrimitives
    from robots.libero.v5_env_client import V5SkillEnvClient
    from robots.libero.v5_oracle_server import OriginalOracleFacade
    meta = {"suite": suite, "task": task, "seed": seed, "max_episode_steps": budget}
    if suite == "libero_90":
        meta["original90_grasp_diagnostic_v1"] = True
    facade = OriginalOracleFacade(make_probe_env(task, seed, suite, budget), meta=meta,
                                  motion_trace_v1=True, original90_diagnostic=suite == "libero_90")
    env = V5SkillEnvClient(LocalRPC(facade), expected_meta=meta)
    primitives = LiberoPrimitives(env, None, None, lambda: None)
    primitives.set_obs(env.last_obs)
    return facade, primitives


def public_screen(primitives):
    import robosuite
    from robots.libero.bounded_screen import PublicRouteScreen
    from robots.libero.tools import _metric_depth, _world_from_depth
    from robots.libero.v5_geometric_grasp import panda_geometry, remove_measured_hand, _voxel
    from robots.libero.v5_grasp_kinematics import PublicPoseScreen
    from robots.libero.bounded_self_filter import remove_visual_robot
    root = Path(robosuite.__file__).parent/"models/assets"
    geometry = panda_geometry(root/"grippers/panda_gripper.xml")
    robot = measured_robot(primitives)
    ik = PublicPoseScreen(root/"robots/panda/robot.xml", robot["joint_positions_rad"],
        robot["eef_xyz_m"], robot["eef_quat_xyzw"], geometry["site_offset_in_gripper_m"], warm_start=True)
    clouds = []
    for camera in ("agentview", "robot0_eye_in_hand"):
        rendered = primitives.env.render_camera(camera, height=256, width=256, depth=True)
        meta = primitives.env.get_camera_meta(camera, height=256, width=256)
        # Match tools._save_observation_artifacts: raw MuJoCo render buffers
        # need a vertical flip before projection with the returned matrices.
        depth = rendered[1]
        clouds.append(_world_from_depth(_metric_depth(depth, meta)[::-1], meta).reshape(-1, 3))
    cloud, _ = remove_measured_hand(np.concatenate(clouds), robot["eef_xyz_m"],
        robot["eef_quat_xyzw"], geometry, robot["gripper_opening_m"])
    cloud, _ = ik.remove_measured_arm(cloud)
    cloud, _ = remove_visual_robot(cloud, ik)
    return PublicRouteScreen(_voxel(cloud), geometry, ik, opening=robot["gripper_opening_m"])


def run(seed, output):
    from robots.libero.v5_runtime import V5Executor
    facade, p = original_session("libero_spatial", 0, seed, 10000)
    try:
        snapshot = facade.snapshot()
        start = np.array(measured_robot(p)["eef_xyz_m"])
        sequences = [
            [[0, 0, .08], [.10, .04, .08], [.16, .08, .10]],
            [[0, 0, .10], [-.10, .06, .10], [-.16, .10, .08]],
            [[0, 0, .08], [.18, .04, .08], [.30, .06, .08]],
        ]
        results = []
        for sequence_index, offsets in enumerate(sequences):
            waypoints = [{"xyz_m": (start+offset).tolist()} for offset in offsets]
            for method in ("legacy_move_to", "legacy_move", "smooth_k1", "smooth_k4"):
                restored = facade.restore(snapshot)
                p.env.terminated = p.env.truncated = False
                p.env.last_obs = restored
                p.set_obs(restored)
                trace, stops, error, old_step = [], [], None, p._step_env
                def traced(action):
                    before = measured_robot(p)
                    old_step(action)
                    after = measured_robot(p)
                    trace.append({"before": before, "after": after, "action": np.asarray(action).tolist()})
                p._step_env = traced
                details = []
                try:
                    if method.startswith("smooth"):
                        screen = public_screen(p)
                        np.savez_compressed(output/f"seed{seed}_sequence{sequence_index}_{method}_public_cloud.npz",
                            points=screen.points, robot_eef=start, robot_joints=measured_robot(p)["joint_positions_rad"],
                            robot_quat=measured_robot(p)["eef_quat_xyzw"])
                        motion = SmoothMotion(p, screen)
                        if method == "smooth_k4":
                            details.append(motion.run(waypoints))
                        else:
                            for point in waypoints:
                                details.append(motion.run([point], blend=False))
                                stops.append(len(trace))
                    else:
                        executor = SimpleNamespace(p=p, motion_trace_v1=False, skill_profiles=None,
                            motion_outcome_v1=True, motion_evidence=[])
                        for point in waypoints:
                            if method == "legacy_move_to":
                                details.append(p.move_to(point["xyz_m"], gripper=-1., trace_steps=True))
                            else:
                                details.append(V5Executor.move(executor, point["xyz_m"], -1., recoverable=True))
                            stops.append(len(trace))
                except Exception as exc:
                    error = {"type": type(exc).__name__, "message": str(exc)}
                finally:
                    p._step_env = old_step
                positions = [start.tolist(), *[t["after"]["eef_xyz_m"] for t in trace]]
                if method == "smooth_k4" and details and details[0].get("trace"):
                    duration = details[0]["reference_duration_s"]
                    # Actual waypoint passages are found by nearest measured
                    # point, with ordered waypoint locations.
                    stops = [int(np.linalg.norm(np.asarray(positions)-point["xyz_m"], axis=1).argmin()) for point in waypoints]
                metrics = motion_metrics(positions, waypoint_indices=stops[:-1]) if len(positions) >= 5 else {}
                tracking = [d.get("max_tracking_error_m") for d in details if d.get("max_tracking_error_m") is not None]
                metrics["max_tracking_error_m"] = max(tracking) if tracking else None
                if not method.startswith("smooth") and trace:
                    metrics["max_tracking_error_m"] = max(float(np.linalg.norm(np.asarray(t["before"]["eef_xyz_m"])
                        +np.asarray(t["action"][:3])*.05-t["after"]["eef_xyz_m"])) for t in trace)
                metrics["commanded_segment_stops"] = len(waypoints)-1 if method != "smooth_k4" else 0
                metrics["max_waypoint_residual_m"] = max((min(np.linalg.norm(np.asarray(positions)-point["xyz_m"], axis=1)) for point in waypoints), default=None)
                record = {"seed": seed, "sequence": sequence_index, "method": method, "steps": len(trace),
                          "metrics": metrics, "error": error, "details": details,
                          "private_truth_used_for_motion": False, "waypoints": waypoints}
                write(output/f"seed{seed}_sequence{sequence_index}_{method}.json", {**record, "trace": trace})
                results.append(record)
                if error:
                    raise RuntimeError(f"motion diagnostic failed: {error}")
        return results
    finally:
        facade.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for seed in range(args.seed, args.seed+args.count):
        rows.extend(run(seed, args.output))
        write(args.output/"summary.json", rows)
    if not any(row["steps"] for row in rows):
        raise RuntimeError("no physical requests executed")


if __name__ == "__main__":
    main()
