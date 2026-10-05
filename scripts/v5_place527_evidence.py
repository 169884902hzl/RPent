"""Save public placement observations and separate private diagnostic labels.

This probe hook reads already captured RGB-D artifacts. It never steps the
environment, substitutes simulator dimensions, or changes a receipt.
"""

import copy
import hashlib
from pathlib import Path
import time

import numpy as np

from robots.libero.v5_state import entity_record


def file_record(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def public_placement_frame(executor, objects, index, phase):
    """Persist current object/target clouds, masks and camera artifacts.

    Old clouds stay explicitly cached rather than becoming current because
    their enclosing record uses a newer step. The stored world maps are the
    existing float16 RGB-D measurements; no raw-depth precision is claimed.
    """
    state = executor.toolkit._state
    step = state.latest_step
    result = {"version": "public-placement-rgbd/1-dev", "source_step": step,
              "sample_index": index, "phase": phase, "recorded_monotonic_s": time.perf_counter(),
              "src": "perception", "new_robot_actions": 0, "cameras": {}, "entities": {}}
    for camera in ("agentview", "wrist"):
        artifacts = {}
        for kind, name in (("rgb", f"{camera}_high.png"),
                           ("world_xyz", f"{camera}_world_high.npz"),
                           ("camera_metadata", f"{camera}_metadata.json")):
            artifacts[kind] = file_record(state.artifact_path(name, step=step)) if state.exists(name, step=step) else None
        artifacts["depth_representation"] = "existing_float16_world_xyz; raw_metric_depth_not_saved"
        artifacts["metadata_resolution"] = "existing_camera_metadata; high_rgb_and_world_resolution_stored_in_artifacts"
        result["cameras"][camera] = artifacts
    for role, original in objects.items():
        current = executor.scene.entities.get(original.id)
        views = executor.scene.measurement_views.get(original.id, {})
        clouds = executor.scene.measurement_clouds_by_view.get(original.id, {})
        entity = {"id": original.id, "selected_before": entity_record(original),
                  "current": entity_record(current) if current else None, "per_view": {},
                  "perception_evidence": copy.deepcopy(executor.scene.perception_evidence.get(original.id, {}))}
        for camera in ("agentview", "wrist"):
            measured, cloud = views.get(camera), clouds.get(camera)
            view = {"measurement": entity_record(measured) if measured else None,
                    "cloud": None, "current": False}
            if cloud is not None:
                points = np.asarray(cloud["xyz_world"])
                name = f"placement527_{index:04d}_{role}_{camera}_{original.id}.npz"
                if state.save(name, points, step=step) is None:
                    raise RuntimeError("placement probe could not persist a measured cloud")
                view["cloud"] = {**file_record(state.artifact_path(name, step=step)),
                                 "source_step": cloud.get("source_step"), "src": cloud.get("src"),
                                 "shape": list(points.shape), "dtype": points.dtype.str}
                view["current"] = bool(cloud.get("source_step") == step and cloud.get("src") == "perception"
                                       and cloud.get("object_id") == original.id)
            entity["per_view"][camera] = view
        result["entities"][role] = entity
    result["robot"] = {"opening_m": float(executor.p._last_obs_gripper),
                       "eef_xyz_m": list(map(float, executor.p._last_obs_eef_pos)), "held": executor.held}
    name = f"placement527_{index:04d}_public.json"
    if state.save(name, result, step=step) is None:
        raise RuntimeError("placement probe could not persist public frame metadata")
    result["metadata"] = file_record(state.artifact_path(name, step=step))
    return result
