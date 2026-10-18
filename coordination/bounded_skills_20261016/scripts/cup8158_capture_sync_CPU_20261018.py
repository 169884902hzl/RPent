# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402 -- select the CPU/GPU environment and immutable source before imports
"""Compare captured wrist calibration with public robot sensors and static XML."""

import hashlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES="", OPENBLAS_NUM_THREADS="1")
import numpy as np
from scipy.spatial.transform import Rotation

root = Path("/public/home/sunyihan/rpent_libero_eval")
directory = next(
    (root / "results/bounded_skills/feasibility_20261017/job8158_60").glob("*oracle*")
)
robot_xml = (
    root
    / ".venv/lib/python3.10/site-packages/robosuite/models/assets/robots/panda/robot.xml"
)
gripper_xml = robot_xml.parents[2] / "grippers/panda_gripper.xml"
camera = ET.parse(robot_xml).find(".//camera[@name='eye_in_hand']")
hand = ET.parse(gripper_xml).find(".//body[@name='right_gripper']")
eef = hand.find("body[@name='eef']")
site = eef.find("site[@name='grip_site']")


def vector(node, key, default):
    return np.asarray(node.get(key, default).split(), float)


def quaternion(node):
    wxyz = vector(node, "quat", "1 0 0 0")
    return Rotation.from_quat(wxyz[[1, 2, 3, 0]]).as_matrix()


site_offset = quaternion(hand) @ (
    vector(eef, "pos", "0 0 0") + quaternion(eef) @ vector(site, "pos", "0 0 0")
)
camera_offset = vector(camera, "pos", "0 0 0")
camera_rotation = quaternion(camera) @ np.diag([1.0, -1.0, -1.0])
states_path = directory / "states.json"
states = json.loads(states_path.read_text())["steps"]
results = []
for record in states:
    step = record["step_idx"]
    metadata = directory / "wrist_metadata.json" / f"{step:02d}.json"
    if not metadata.exists():
        continue
    raw = record["state"]
    rotation = Rotation.from_quat(raw["robot0_eef_quat"]).as_matrix()
    xyz = np.asarray(raw["robot0_eef_pos"])
    expected_position = xyz + rotation @ (camera_offset - site_offset)
    expected_rotation = rotation @ camera_rotation
    measured = np.asarray(json.loads(metadata.read_text())["extrinsic_cam2world"])
    results.append(
        {
            "capture_step": step,
            "camera_position_residual_m": float(
                np.linalg.norm(expected_position - measured[:3, 3])
            ),
            "camera_rotation_residual_rad": float(
                Rotation.from_matrix(expected_rotation.T @ measured[:3, :3]).magnitude()
            ),
            "metadata_sha256": hashlib.sha256(metadata.read_bytes()).hexdigest(),
        }
    )
point = np.array([0.0107914749532938, 0.08394207060337067, 0.7108669877052307])
meta = json.loads((directory / "wrist_metadata.json/17.json").read_text())
k = np.asarray(meta["intrinsic_K"]) * 4
k[2, 2] = 1
extrinsic = np.asarray(meta["extrinsic_cam2world"])
camera_point = (point - extrinsic[:3, 3]) @ extrinsic[:3, :3]
pixel = k @ camera_point
pixel /= pixel[2]
report = {
    "scope": "saved public robot sensors, camera calibration, static robot XML only; zero controls",
    "private_truth_used": False,
    "gpu_used": False,
    "training": False,
    "states_sha256": hashlib.sha256(states_path.read_bytes()).hexdigest(),
    "robot_xml_sha256": hashlib.sha256(robot_xml.read_bytes()).hexdigest(),
    "gripper_xml_sha256": hashlib.sha256(gripper_xml.read_bytes()).hexdigest(),
    "results": results,
    "max_position_residual_m": max(r["camera_position_residual_m"] for r in results),
    "max_rotation_residual_rad": max(
        r["camera_rotation_residual_rad"] for r in results
    ),
    "blocker_projection": {
        "point_m": point.tolist(),
        "row_col": pixel[[1, 0]].tolist(),
        "half_pixel_world_size_m": float(0.5 * camera_point[2] / k[0, 0]),
    },
}
output = (
    root
    / "coordination/bounded_skills_20261016/reports/cup8158_capture_sync_CPU_20261018.json"
)
output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({key: value for key, value in report.items() if key != "results"}))
