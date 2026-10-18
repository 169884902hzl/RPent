# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare a saved cup's public surface fit with private motion, without controls."""
# ruff: noqa: E402 -- select CPU-only immutable source before simulator imports
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES="", LIBERO_TYPE="standard", OPENBLAS_NUM_THREADS="1")
root = Path("/public/home/sunyihan/rpent_libero_eval")
base = root / "coordination/bounded_skills_20261016"
sys.path.insert(0, str(root / "source_bounded_chunk_v3_support_plane_20261018_ec89f74"))

import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

directory, = (root / "results/bounded_skills/feasibility_20261017/job9026_69").glob("*oracle*")
rows = [json.loads(line) for line in (directory / "choices.jsonl").read_bytes().splitlines()]
ledger = json.loads((directory.parent / "episodes.jsonl").read_bytes().splitlines()[0])
public = json.loads((base / "reports/9026_69_support_final_CPU_20261018.json").read_text())
registered, = [s for s in public["stages"] if s["name"] == "registered"]
evidence, = [e for e in registered["boundary"] if "surface_registration" in e]
fit = evidence["surface_registration"]
assert fit["accepted"]
reference = rows[0]["public_geometry_evidence"]["bounded_screen_e48_1_target"]
raw = Path(reference["path"]).read_bytes()
assert hashlib.sha256(raw).hexdigest() == reference["sha256"]
with np.load(reference["path"]) as data:
    points = data[data.files[0]]
_, indices = np.unique(np.floor(points / .001).astype(int), axis=0, return_index=True)
voxel = points[np.sort(indices)]
centre = voxel[::max(1, len(voxel) // 8000)].mean(0)
corrected = (points - centre) @ np.asarray(fit["rotation_matrix"]).T + centre + fit["translation_m"]

env = ControlEnv(bddl_file_name=ledger["case"]["bddl"]["path"], use_camera_obs=False,
                 has_renderer=False, has_offscreen_renderer=False, camera_names=[],
                 ignore_done=True, horizon=10015)
attach_reset_seed(env)
env.seed(0)
env.reset()
poses = []
try:
    for index in (0, 2):
        reference = rows[index]["private_pre_execution_snapshot"]
        raw = Path(reference["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == reference["sha256"]
        saved = pickle.loads(raw)
        env.set_init_state(saved["sim_state"])
        restore_actuators(env, saved["actuator_state"])
        sim = env.env.sim
        error = float(np.max(np.abs(sim.get_state().flatten() - saved["sim_state"])))
        assert error < 1e-8
        body = env.env.obj_body_id["porcelain_mug_1"]
        poses.append({"row": index, "snapshot": reference, "flat_restore_error": error,
                      "xyz_m": sim.data.body_xpos[body].copy().tolist(),
                      "rotation": sim.data.body_xmat[body].reshape(3, 3).copy().tolist()})
finally:
    env.close()
before, after = poses
rotation = np.asarray(after["rotation"]) @ np.asarray(before["rotation"]).T
true_points = (points - before["xyz_m"]) @ rotation.T + after["xyz_m"]
distance = np.linalg.norm(corrected - true_points, axis=1)
blockers = np.unique([p for cloud in registered["route_screen"]["public_scene_collision_points"].values()
                      for p in cloud], axis=0)
report = {
    "scope": "Private saved-state registration diagnosis only; not runtime or training input",
    "job": "9026_69", "poses": poses, "public_fit": fit,
    "private_translation_m": (np.asarray(after["xyz_m"]) - before["xyz_m"]).tolist(),
    "private_rotation_rad": float(Rotation.from_matrix(rotation).magnitude()),
    "public_vs_private_surface_error_quantiles_m": np.quantile(distance, [0, .5, .9, 1]).tolist(),
    "blockers": [{"xyz_m": p.tolist(),
                  "distance_to_private_transformed_reference_m": float(cKDTree(true_points).query(p)[0]),
                  "distance_to_public_transformed_reference_m": float(cKDTree(corrected).query(p)[0])}
                 for p in blockers],
    "controls_sent": 0, "gpu_used": False, "runtime_use": False, "training": False,
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
output = base / "reports/cup69_registration_pose_diagnostic_CPU_20261018.json"
output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: report[k] for k in (
    "private_translation_m", "private_rotation_rad", "public_vs_private_surface_error_quantiles_m", "blockers"
)}))
