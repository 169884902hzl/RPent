"""Collect fixed public multi-frame evidence, independent of private labels."""

import json
from pathlib import Path

import numpy as np

from public_temporal_verifier import identity, VERSION


def capture_public_sequence(executor, measured_entity, output, *, phase, gripper_control,
                            frame_count=3, controls_between_frames=6):
    """Hold zero Cartesian motion, then measure; caller supplies grip command."""
    if frame_count != 3 or controls_between_frames not in (0, 6):
        raise ValueError("registered sampler requires three frames and 0/6 hold controls")
    if gripper_control not in (-1, 1):
        raise ValueError("explicit existing open/closed gripper command is required")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    frames = []
    for index in range(frame_count):
        if index:
            action = np.asarray([0, 0, 0, 0, 0, 0, gripper_control], dtype=np.float32)
            for _ in range(controls_between_frames):
                executor.p._step_env(action)
        executor.capture()
        state = executor.toolkit._state
        step = state.latest_step
        views = {camera: {"raw_rgb": identity(state.artifact_path(camera + "_high.png", step=step)),
                          "raw_world": identity(state.artifact_path(camera + "_world_high.npz", step=step)),
                          "source_step": step} for camera in ("agentview", "wrist")}
        frames.append({"phase": phase, "index": index, "source_step": step, "views": views,
            "public_robot_observation": {"eef_xyz_m": executor.p._last_obs_eef_pos.tolist(),
                                         "gripper_opening_m": float(executor.p._last_obs_gripper)},
            "hold_controls_since_previous_frame": controls_between_frames if index else 0,
            "coordinate_source": "calibrated_rgbd_and_robot_proprioception",
            "private_object_or_joint_values": False})
    measured = ({"id": measured_entity.id, "name": measured_entity.name,
                 "lower": list(measured_entity.lower), "upper": list(measured_entity.upper),
                 "source_step": measured_entity.source_step, "src": "perception"}
                if measured_entity is not None else None)
    result = {"version": VERSION, "phase": phase, "frames": frames, "initial_measured_bounds": measured,
        "bounds_are_cache_not_current_visibility": True, "status": "captured" if measured else "unknown",
        "unknown_reason": None if measured else "fixture_initial_measurement_missing",
        "fixed_hold_controls": (frame_count - 1) * controls_between_frames,
        "fixed_gripper_control": gripper_control, "stop_based_on_private_label": False,
        "unobstructed_view_claim": "after_retreat requests cleared view; current RGBD must establish visibility"}
    path = output / "public_sequence.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    return identity(path)

