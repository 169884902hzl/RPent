# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402 -- select the CPU/GPU environment and immutable source before imports
"""Render one saved original state with/without MSAA; issue no controls."""

import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(
    LIBERO_TYPE="standard",
    MUJOCO_GL="egl",
    PYOPENGL_PLATFORM="egl",
    OPENBLAS_NUM_THREADS="1",
)
root = Path("/public/home/sunyihan/rpent_libero_eval")
sys.path.insert(0, str(root / "source_bounded_276456d_20261018"))
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from PIL import Image

from robots.libero.tools import _metric_depth, _world_from_depth
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

base = root / "results/bounded_skills/feasibility_20261017"
directory = next((base / "job8158_60").glob("*oracle*"))
row = json.loads((directory / "choices.jsonl").read_bytes().splitlines()[16])
reference = row["private_pre_execution_snapshot"]
raw = Path(reference["path"]).read_bytes()
assert hashlib.sha256(raw).hexdigest() == reference["sha256"]
saved = pickle.loads(raw)
plan = json.loads(
    (base / "preparation/original20_manifest_contact_retry_20261018.json").read_text()
)
case = next(
    case for case in plan["cases"] if case["name"] + "_oracle_k4" == directory.name
)
out = (
    root
    / "coordination/bounded_skills_20261016/reports"
    / ("cup8158_depth_resolve_GPU_job" + os.environ["SLURM_JOB_ID"])
)
out.mkdir()
env = ControlEnv(
    bddl_file_name=case["bddl"]["path"],
    use_camera_obs=False,
    has_renderer=False,
    has_offscreen_renderer=True,
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
    before = sim.get_state().flatten().copy()
    assert np.max(np.abs(before - saved["sim_state"])) < 1e-8
    default_samples = int(sim.model.vis.quality.offsamples)
    context = sim._render_context_offscreen
    for samples in (default_samples, 0):
        sim.model.vis.quality.offsamples = samples
        context.con.free()
        context._set_mujoco_context_and_buffers()
        for camera, name in (
            ("agentview", "agentview"),
            ("robot0_eye_in_hand", "wrist"),
        ):
            rgb, depth = sim.render(
                width=1024, height=1024, camera_name=camera, depth=True
            )
            meta = json.loads(
                (directory / (name + "_metadata.json") / "17.json").read_text()
            )
            meta["intrinsic_K"] = (np.asarray(meta["intrinsic_K"]) * 4).tolist()
            meta["intrinsic_K"][2][2] = 1
            world = _world_from_depth(_metric_depth(depth, meta)[::-1], meta).astype(
                np.float32
            )
            stem = name + "_samples" + str(samples)
            Image.fromarray(rgb[::-1]).save(out / (stem + ".png"))
            np.savez_compressed(out / (stem + "_world.npz"), world=world)
            with np.load(directory / (name + "_world_high.npz") / "17.npz") as archive:
                previous = archive[archive.files[0]]
            norm = np.linalg.norm(world - previous, axis=-1)
            results.append(
                {
                    "camera": name,
                    "offsamples": samples,
                    "image": str(out / (stem + ".png")),
                    "world": str(out / (stem + "_world.npz")),
                    "world_sha256": hashlib.sha256(
                        (out / (stem + "_world.npz")).read_bytes()
                    ).hexdigest(),
                    "difference_from_saved_median_m": float(np.median(norm)),
                    "difference_from_saved_p99_m": float(np.quantile(norm, 0.99)),
                    "wrist_blocker_pixel_world_m": world[853, 481].tolist()
                    if name == "wrist"
                    else None,
                }
            )
    assert np.array_equal(before, sim.get_state().flatten()), "render advanced physics"
finally:
    env.close()
report = {
    "scope": "same saved original state, calibrated RGB-D rendering comparison, zero controls",
    "job": os.environ["SLURM_JOB_ID"],
    "snapshot": reference,
    "training": False,
    "confirmation": False,
    "private_truth_used_for_control": False,
    "default_offsamples": default_samples,
    "results": results,
    "source_commit": "276456d3d426f314600b52acc9348fcb24886da5",
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
