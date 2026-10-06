# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Shared public pan acquisition and coupled-lift verification.

The original-task probe and runtime call the same RGB-D procedure. No
private grasp predicate, object pose, or simulator goal is read here.
"""

import base64
import hashlib
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measured_pan_handle_views(executor, before, views, *, cross_view_handle_v1=False):
    """Acquire target-bound visible handles on each existing RGB-D capture."""
    from robots.libero.v5_grasp_measurement import bind_visible_handle
    from rpent.robots.components.sam3_client import Sam3Client

    state, handles, diagnostics = executor.toolkit._state, {}, {}
    current = [entity for entity in executor.scene.entities.values()
               if entity.name == before.name and entity.visible and entity.source_step == state.latest_step]
    if len(current) != 1 or current[0].id != before.id:
        return {}, {"reason": "current_target_binding_not_unique"}
    cameras = ("agentview", "wrist") if cross_view_handle_v1 else tuple(views)
    for camera in cameras:
        # A wrist close-up can show only the held handle. Associate it with
        # the unique current body measured in the other calibrated view;
        # never fabricate a wrist body detection or reuse a cached body.
        entity = views.get(camera, current[0])
        image = base64.b64encode(state.load_bytes(f"{camera}_high.png")).decode("ascii")
        world = state.load(f"{camera}_world_high.npz")
        query = "handle of the frying pan"
        reply = executor.scene.rpc.call("sam3.segment_all", kwargs={
            "image_base64": image, "text_prompt": query, "min_score": .35}, timeout_s=120)
        executor.scene.calls += 1
        accepted, details = [], []
        for item in reply.get("instances", []):
            mask = Sam3Client._decode_result(item).mask
            if mask is None or mask.shape != world.shape[:2]:
                details.append({"reason": "invalid_current_handle_mask"})
                continue
            cloud = world[mask]
            cloud = cloud[np.isfinite(cloud).all(axis=1) & (np.abs(cloud).sum(axis=1) > 1e-6)]
            handle, reason = bind_visible_handle(before, entity, cloud)
            details.append({"reason": reason, "score": item.get("score"),
                            "measured_points": len(cloud)})
            if handle is not None:
                accepted.append((handle, cloud))
        if len(accepted) == 1:
            handle, cloud = accepted[0]
            name = f"pan_handle_{before.id}_{camera}_s{state.latest_step}.npz"
            if state.save(name, cloud, step=state.latest_step) is None:
                raise RuntimeError("could not persist current handle measurements")
            path = state.artifact_path(name, step=state.latest_step)
            handles[camera] = {**handle, "query": query, "camera": camera,
                               "points_file": {"path": str(path), "sha256": sha(path)}}
        diagnostics[camera] = {"query": query, "source_step": state.latest_step,
                               "accepted_instances": len(accepted), "instances": details,
                               "body_measurement_in_this_view": camera in views,
                               "body_binding_source": "same_view" if camera in views else "unique_current_fused_target"}
    return handles, diagnostics


def rpent_pick_then_independent_handle_measure(executor, prompt, max_chunks, obj, *, trial_lift_m, evidence,
                                               cross_view_handle_v1=False, coupled_lift_v1=False):
    """Preserve the pan recipe and replace its verifier's acquisition path."""
    from scipy.spatial.transform import Rotation

    from robots.libero.v5_grasp_measurement import (
        evaluate_grasp_frame,
        evaluate_grasp_pair,
        evaluate_coupled_lift_pair,
    )
    from robots.libero.v5_perception_geometry import measured_work_surface

    calibration = executor.grasp_measurement_calibration
    if calibration is None or obj.name != "frypan":
        raise ValueError("independent handle verification requires a registered pan sensor calibration")
    support = measured_work_surface(executor.toolkit._state.load(
        "agentview_world_high.npz", step=obj.source_step), [obj])
    measurements = {"version": "pan_independent_views_bound_handle_two_frames/1-dev", "frames": [],
                    "measured_support": support, "hold_steps": 10, "registered_control_frequency_hz": 20,
                    "trial_lift_m": trial_lift_m, "runtime_inputs": "camera-specific RGB-D and calibrated robot proprioception"}
    evidence["stable_visual_grasp"] = measurements
    primitive = executor.p.pi0_pick(prompt, max_chunks=max_chunks)
    evidence["rpent_pick_result"] = primitive
    receipt = {"executed": primitive["chunks_used"] > 0, "chunks": primitive["chunks_used"],
               "stop_condition": "grasp_verified", "stop": "grasp_unmeasured", "grasp_verified": None,
               "final_grasp_measurement": True}
    if executor.p.env.terminated or executor.p.env.truncated:
        measurements["unverified_reason"] = "native_termination_before_trial_lift"
        return receipt
    if not executor.opening_may_hold(executor.p._last_obs_gripper):
        measurements["unverified_reason"] = "calibrated_opening_does_not_allow_hold_measurement"
        return receipt
    lift = executor.p._last_obs_eef_pos.copy()
    lift[2] += trial_lift_m
    motion = executor.move(lift, 1, tolerance_m=.02, recoverable=True)
    measurements["trial_lift_motion"] = motion
    if not motion.get("waypoint_reached") or executor.p.env.terminated or executor.p.env.truncated:
        measurements["unverified_reason"] = "trial_lift_not_completed"
        return receipt
    previous_step = obj.source_step
    for index in range(2):
        if index:
            if coupled_lift_v1:
                # Public active measurement, independent of the private
                # grasp label: move at fixed wrist orientation and test that
                # the current RGB-D body follows the measured robot motion.
                translated = executor.p._last_obs_eef_pos.copy()
                translated[2] += .05
                measurements["coupled_lift_motion"] = executor.move(
                    translated, 1, tolerance_m=.02, recoverable=True)
                if (not measurements["coupled_lift_motion"].get("waypoint_reached")
                        or executor.p.env.terminated or executor.p.env.truncated):
                    measurements["unverified_reason"] = "coupled_lift_not_completed"
                    return receipt
            executor.p.set_gripper(gripper=1, steps=10)
            if executor.p.env.terminated or executor.p.env.truncated:
                measurements["unverified_reason"] = "native_termination_before_second_frame"
                return receipt
        executor._refresh([obj.name])
        step = executor.toolkit._state.latest_step
        views = {camera: entity for camera, entity in executor.scene.measurement_views.get(obj.id, {}).items()
                 if entity.source_step == step}
        handles, details = measured_pan_handle_views(executor, obj, views,
                                                     cross_view_handle_v1=cross_view_handle_v1)
        raw = executor.p.env.raw_obs()
        xyz = np.asarray(raw["robot0_eef_pos"], dtype=float)
        geometry = calibration["grip_site_geometry"]
        rotation = Rotation.from_quat(raw["robot0_eef_quat"]).as_matrix() @ np.asarray(geometry["rotation_body_to_site"])
        finger = {"rotation_world_from_fingers": rotation.tolist(),
                  "origin_world": (xyz + rotation @ np.asarray(geometry["finger_centre_offset_from_site_m"])).tolist(),
                  "closing_axis": geometry["closing_axis"], "depth_half_m": geometry["pad_depth_half_m"],
                  "height_half_m": geometry["pad_height_half_m"],
                  "provenance": calibration["robot_rigid_transform_validation"]}
        frame = evaluate_grasp_frame(obj, views, float(np.abs(raw["robot0_gripper_qpos"]).sum()),
            xyz.tolist(), previous_step=previous_step, opening_calibration=calibration["opening_calibration"],
            finger_frame=finger, measured_points_by_view=executor.scene.measurement_clouds_by_view.get(obj.id),
            support_top_z_m=support["height_m"] if support else None, require_support_clearance=True,
            handle_measurements_by_view=handles, cross_view_handle_v1=cross_view_handle_v1)
        frame.update(handle_acquisition=details, captured_step=step,
                     body_quat_xyzw=np.asarray(raw["robot0_eef_quat"]).tolist())
        measurements["frames"].append(frame)
        previous_step = step
    pair = evaluate_grasp_pair(*measurements["frames"], 10 / 20)
    if coupled_lift_v1:
        measurements["handle_only_paired_verdict"] = pair
        pair = evaluate_coupled_lift_pair(*measurements["frames"], 10 / 20)
    measurements["paired_verdict"] = pair
    receipt.update(grasp_verified=pair["verified"],
                   stop="grasp_verified" if pair["verified"] is True
                        else "grasp_not_verified" if pair["verified"] is False else "grasp_unmeasured")
    return receipt

