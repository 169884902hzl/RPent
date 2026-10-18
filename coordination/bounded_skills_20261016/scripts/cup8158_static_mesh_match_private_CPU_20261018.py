# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402 -- select the CPU/GPU environment and immutable source before imports
"""Privately compare rendered robot mesh transforms with public static models."""

import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(
    CUDA_VISIBLE_DEVICES="", LIBERO_TYPE="standard", OPENBLAS_NUM_THREADS="1"
)
root = Path("/public/home/sunyihan/rpent_libero_eval")
sys.path.insert(0, str(root / "source_bounded_276456d_20261018"))
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from robots.libero.bounded_self_filter import (
    gripper_at_measured_fingers,
    gripper_visual_boxes,
)
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_reset_seed import attach_reset_seed

base = root / "results/bounded_skills/feasibility_20261017"
directory = next((base / "job8158_60").glob("*oracle*"))
choices = directory / "choices.jsonl"
rows = [json.loads(line) for line in choices.open()]
reference = rows[16]["private_pre_execution_snapshot"]
raw = Path(reference["path"]).read_bytes()
assert hashlib.sha256(raw).hexdigest() == reference["sha256"]
saved = pickle.loads(raw)
plan = json.loads(
    (base / "preparation/original20_manifest_contact_retry_20261018.json").read_text()
)
case = next(
    case for case in plan["cases"] if case["name"] + "_oracle_k4" == directory.name
)
robot = rows[15]["execution_details"][-1]["execution"]["trace"][-1]["after"]
rotation = (
    Rotation.from_quat(robot["eef_quat_xyzw"]).as_matrix()
    @ Rotation.from_euler("z", -np.pi / 2).as_matrix()
)
xml = (
    root
    / ".venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml"
)
geometry = gripper_at_measured_fingers(
    {**panda_geometry(xml), "visual_boxes": gripper_visual_boxes(str(xml))},
    robot["finger_positions_m"],
)
point = np.array([0.0107914749532938, 0.08394207060337067, 0.7108669877052307])
env = ControlEnv(
    bddl_file_name=case["bddl"]["path"],
    use_camera_obs=False,
    has_renderer=False,
    has_offscreen_renderer=False,
    camera_names=[],
    ignore_done=True,
    horizon=10015,
)
attach_reset_seed(env)
env.seed(case["episode"]["seed"])
env.reset()
results = []
try:
    env.set_init_state(saved["sim_state"])
    restore_actuators(env, saved["actuator_state"])
    sim = env.env.sim
    residual = float(np.max(np.abs(sim.get_state().flatten() - saved["sim_state"])))
    assert residual < 1e-8
    for shell in geometry["visual_boxes"]:
        name = shell["name"]
        geom_id = sim.model.geom_name2id("gripper0_right_" + name)
        mesh_id = sim.model.geom_dataid[geom_id]
        first = sim.model.mesh_vertadr[mesh_id]
        count = sim.model.mesh_vertnum[mesh_id]
        vertices = np.asarray(sim.model.mesh_vert[first : first + count])
        native_world = (
            vertices @ sim.data.geom_xmat[geom_id].reshape(3, 3).T
            + sim.data.geom_xpos[geom_id]
        )
        native_local = (native_world - robot["eef_xyz_m"]) @ rotation
        equations = np.asarray(shell["convex_halfspaces"])
        native_hull = ConvexHull(native_local)
        local_point = (point - robot["eef_xyz_m"]) @ rotation
        results.append(
            {
                "mesh": name,
                "vertices": int(count),
                "compiled_vertices_outside_public_hull_max_m": float(
                    (native_local @ equations[:, :3].T + equations[:, 3]).max()
                ),
                "compiled_visual_hull_point_residual_m": float(
                    (
                        native_hull.equations[:, :3] @ local_point
                        + native_hull.equations[:, 3]
                    ).max()
                ),
                "public_visual_hull_point_residual_m": float(
                    (equations[:, :3] @ local_point + equations[:, 3]).max()
                ),
                "compiled_bounds": [
                    native_local.min(0).tolist(),
                    native_local.max(0).tolist(),
                ],
                "public_bounds": [shell["lower"], shell["upper"]],
            }
        )
finally:
    env.close()
report = {
    "scope": "private rendered-robot geometry audit only, no rendering/controls",
    "model_visible": False,
    "used_for_control": False,
    "gpu_used": False,
    "training": False,
    "snapshot": reference,
    "restore_max_residual": residual,
    "choices_sha256": hashlib.sha256(choices.read_bytes()).hexdigest(),
    "results": results,
}
output = (
    root
    / "coordination/bounded_skills_20261016/reports/cup8158_static_mesh_match_private_CPU_20261018.json"
)
output.write_text(
    json.dumps(report, indent=2, default=lambda value: value.tolist()) + "\n"
)
print(json.dumps(report, default=lambda value: value.tolist()))
