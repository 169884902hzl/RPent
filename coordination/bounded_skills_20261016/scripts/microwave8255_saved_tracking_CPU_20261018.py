# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Test existing public door tracking on saved captures; never issue controls."""
# ruff: noqa: E402 -- choose CPU and immutable source before robot imports
import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES="", OPENBLAS_NUM_THREADS="1")
parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--self-filter-robot", action="store_true")
parser.add_argument("--tracker", type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import cv2
import numpy as np
from PIL import Image

from robots.libero.v5_microwave_capture import points_mask
from robots.libero.v5_microwave_identity import track_measured_door

if args.tracker:
    spec = importlib.util.spec_from_file_location("candidate_door_tracker", args.tracker)
    candidate_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate_module)
    track_measured_door = candidate_module.track_measured_door

cv2.setNumThreads(1)
root = Path("/public/home/sunyihan/rpent_libero_eval")
directory = next((root / "results/bounded_skills/feasibility_20261017/job8255_120").glob("*oracle*"))
prefix = (directory / "choices.jsonl").read_bytes().splitlines()
rows = [json.loads(line) for line in prefix]
last_step = max(row.get("fixture_measurement_evidence", {}).get("e98", {}).get("source_step", 0) for row in rows)
initial = rows[0]["fixture_measurement_evidence"]["e98"]["door_measurement"]
records, sources = [], []
robots = {}
if args.self_filter_robot:
    from scipy.spatial import cKDTree

    from robots.libero.bounded_self_filter import (
        gripper_at_measured_fingers,
        gripper_visual_boxes,
        remove_current_gripper,
        remove_visual_robot,
    )
    from robots.libero.v5_geometric_grasp import panda_geometry
    from robots.libero.v5_grasp_kinematics import PublicPoseScreen

    def pose_key(robot):
        return tuple(round(value, 10) for field in ("eef_xyz_m", "eef_quat_xyzw") for value in robot[field])

    first_robot = rows[0]["execution_details"][0]["execution"]["trace"][0]["before"]
    poses = {pose_key(first_robot): first_robot}
    for row in rows:
        request_robot = row["request"]["robot"]
        capture = row.get("fixture_measurement_evidence", {}).get("e98", {}).get("source_step")
        if capture is not None and pose_key(request_robot) in poses:
            robots[capture] = poses[pose_key(request_robot)]
        details = {detail["candidate_id"]: detail["execution"] for detail in row.get("execution_details", [])}
        for receipt in row.get("receipts", []):
            trace = details.get(receipt["candidate_id"], {}).get("trace", [])
            if not trace:
                continue
            robot = trace[-1]["after"]
            assert pose_key(robot) == pose_key(receipt["after"])
            captures = [item["capture_step"] for item in receipt["evidence"]]
            if captures:
                robots[max(captures)] = robot
            poses[pose_key(robot)] = robot
    xml = root / ".venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml"
    geometry = {**panda_geometry(xml), "visual_boxes": gripper_visual_boxes(str(xml))}

    def robot_mask_for(world, step):
        robot = robots[step]
        hand = gripper_at_measured_fingers(geometry, robot["finger_positions_m"])
        points = world.reshape(-1, 3)
        cloud, _ = remove_current_gripper(points, robot["eef_xyz_m"], robot["eef_quat_xyzw"], hand, robot["gripper_opening_m"])
        ik = PublicPoseScreen(xml.parent.parent / "robots/panda/robot.xml", robot["joint_positions_rad"],
                             robot["eef_xyz_m"], robot["eef_quat_xyzw"], geometry["site_offset_in_gripper_m"])
        cloud, _ = ik.remove_measured_arm(cloud)
        cloud, _ = remove_visual_robot(cloud, ik)
        return (cKDTree(cloud).query(points, distance_upper_bound=np.nextafter(1e-6, np.inf))[0] > 1e-6).reshape(world.shape[:2])

def load(path):
    path = Path(path)
    raw = path.read_bytes()
    sources.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
    if path.suffix == ".png":
        return np.asarray(Image.open(path))
    with np.load(path) as data:
        return data[data.files[0]]

for camera in initial["source_cameras"]:
    start = next(item for item in initial["instances"] if item["camera"] == camera and item.get("basis") and item.get("candidate_cloud"))
    artifact = start["candidate_cloud"]
    assert hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]
    reference_step = 0
    previous_rgb = load(directory / (camera + "_high.png") / "00.png")
    previous_world = load(directory / (camera + "_world_high.npz") / "00.npz")
    previous_mask = points_mask(previous_world, load(artifact["path"]))
    assert previous_mask.sum() >= 60
    captures = sorted((path for path in (directory / (camera + "_world_high.npz")).glob("*.npz")
                       if 0 < int(path.stem) <= last_step), key=lambda path: int(path.stem))
    for capture in captures:
        step = int(capture.stem)
        rgb = load(directory / (camera + "_high.png") / f"{step:02d}.png")
        world = load(capture)
        robot_mask = robot_mask_for(world, step) if args.self_filter_robot else None
        mask, face, evidence = track_measured_door(previous_rgb, rgb, previous_world, world, previous_mask, None,
                                                 robot_mask=robot_mask)
        records.append({"camera": camera, "reference_step": reference_step, "capture_step": step,
                        "measured": face is not None, "pixels": int(mask.sum()), "face": face, "evidence": evidence})
        if face is not None:
            reference_step, previous_rgb, previous_world, previous_mask = step, rgb, world, mask

report = {"scope": "CPU replay of existing optical-flow/RGB-D door identity on original-task development captures",
    "source": str(args.source), "gpu_used": False, "controls": 0, "private_truth_used": False,
    "training": False, "physical_result": None, "new_segmentation_queries": 0,
    "limitation": "No independent fixed-frame anchor supplied; this tests door identity, not endpoint verification or stopping.",
    "choices_prefix_sha256": hashlib.sha256(b"\n".join(prefix)).hexdigest(),
    "self_filter_robot": args.self_filter_robot,
    "candidate_tracker": ({"path": str(args.tracker), "sha256": hashlib.sha256(args.tracker.read_bytes()).hexdigest()}
                          if args.tracker else None),
    "robot_measurement_source": "recorded public control traces and receipts" if args.self_filter_robot else None,
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "capture_sources": sources, "last_capture_step": last_step, "records": records}
suffix = "_self_filtered" if args.self_filter_robot else ""
if args.tracker:
    suffix += "_candidate"
output = root / f"coordination/bounded_skills_20261016/reports/microwave8255_saved_tracking_CPU_20261018{suffix}.json"
output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"output": str(output), "measurements": [
    {key: record[key] for key in ("camera", "reference_step", "capture_step", "measured", "pixels")}
    | {"reason": record["evidence"]["reason"]} for record in records]}))
