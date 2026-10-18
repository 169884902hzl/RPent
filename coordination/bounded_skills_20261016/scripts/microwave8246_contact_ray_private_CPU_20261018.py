# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402 -- select CPU and immutable source before imports
"""Identify the saved public blocker ray privately; never a runtime input."""

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
import mujoco
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv

from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

base = root / "results/bounded_skills/feasibility_20261017"
directory = next((base / "job8246_140").glob("*oracle*"))
captured = (directory / "choices.jsonl").read_bytes()
row = json.loads(captured.splitlines()[3])
ref = row["private_pre_execution_snapshot"]
raw = Path(ref["path"]).read_bytes()
assert hashlib.sha256(raw).hexdigest() == ref["sha256"]
saved = pickle.loads(raw)
plan = json.loads(
    (base / "preparation/original20_manifest_boundary_convergence_20261018.json").read_text()
)
case = next(c for c in plan["cases"] if c["name"] + "_oracle_k4" == directory.name)
point = np.array([-0.07354718446731567, -0.10573653131723404, 1.0200669765472412])
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
    for camera in ("agentview", "wrist"):
        meta = json.loads(
            (directory / (camera + "_metadata.json") / "03.json").read_text()
        )
        transform = np.asarray(meta["extrinsic_cam2world"])
        origin, rotation = transform[:3, 3], transform[:3, :3]
        local = (point - origin) @ rotation
        k = np.asarray(meta["intrinsic_K"]) * 4
        for dx, dy in ((0.0, 0.0), (0.5, 0.5), (0.5, -0.5), (-0.5, 0.5), (-0.5, -0.5)):
            corrected = point + rotation @ [
                dx * local[2] / k[0, 0],
                dy * local[2] / k[1, 1],
                0.0,
            ]
            direction = corrected - origin
            length = float(np.linalg.norm(direction))
            direction /= length
            identity = np.array([-1], np.int32)
            depth = mujoco.mj_ray(
                sim.model._model,
                sim.data._data,
                origin,
                direction,
                np.array([0, 1, 0, 0, 0, 0], np.uint8),
                1,
                -1,
                identity,
            )
            name = (
                mujoco.mj_id2name(
                    sim.model._model, mujoco.mjtObj.mjOBJ_GEOM, int(identity[0])
                )
                if identity[0] >= 0
                else None
            )
            results.append(
                {
                    "camera": camera,
                    "pixel_shift_xy": [dx, dy],
                    "private_visual_geom": name,
                    "ray_length_m": length,
                    "private_depth_minus_public_m": float(depth - length),
                    "world_position_shift_m": float(np.linalg.norm(corrected - point)),
                }
            )
finally:
    env.close()
report = {
    "scope": "private ray identity diagnosis only; zero controls/no renderer",
    "model_visible": False,
    "used_for_control": False,
    "gpu_used": False,
    "training": False,
    "snapshot": ref,
    "restore_max_residual": residual,
    "results": results,
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
output = (
    root
    / "coordination/bounded_skills_20261016/reports/microwave8246_contact_ray_private_CPU_20261018.json"
)
output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
