"""Compare independent original-task resets without SAM, VLA or training rows."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types

import numpy as np


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private_geometry(wrapper):
    """Return model fixture poses only to this diagnostic process."""
    env = wrapper.env
    return {
        name: {
            "model_pos": env.sim.model.body_pos[index].tolist(),
            "model_quat": env.sim.model.body_quat[index].tolist(),
            "world_pos": env.sim.data.body_xpos[index].tolist(),
            "world_quat": env.sim.data.body_xquat[index].tolist(),
            "fixture": name in env.fixtures_dict,
        }
        for name, index in env.obj_body_id.items()
    }


def run_child(args):
    from robots.libero import v5_branch_state
    from robots.libero.tools import _metric_depth, _world_from_depth
    from robots.libero.v5_env_server import V5EnvFacade, make_v5_env
    from libero.libero.envs.env_wrapper import ControlEnv
    from libero.libero.envs.regions.base_region_sampler import MultiRegionRandomSampler
    from robosuite.utils.placement_samplers import UniformRandomSampler

    original = v5_branch_state.attach_branch_state

    def attach(worker):
        original(worker)
        worker.v5_reset_private_geometry = types.MethodType(private_geometry, worker)
        return worker

    v5_branch_state.attach_branch_state = attach
    args.output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    env = make_v5_env(0, args.seed, "libero_goal", 10000, branch_state=True,
                      deterministic_reset_v1=args.condition == "seeded")
    facade = V5EnvFacade(env, meta={"suite": "libero_goal", "task": 0, "seed": args.seed})
    try:
        facade.reset()
        worker = env.env.workers[0]
        geometry = worker.env_call("v5_reset_private_geometry", target="self")
        state = worker.get_sim_state()
        np.save(args.output / "sim_state.npy", state)
        (args.output / "private_geometry.json").write_text(json.dumps(geometry, sort_keys=True, indent=2) + "\n")
        cameras = {}
        for camera in ("agentview", "robot0_eye_in_hand"):
            rgb, depth = facade.render_camera(camera, 256, 256, depth=True)
            meta = facade.get_camera_meta(camera, 256, 256)
            world = _world_from_depth(_metric_depth(depth, meta), meta)
            arrays = {"rgb": rgb, "depth": depth, "world": world}
            for name, value in arrays.items():
                np.save(args.output / f"{camera}_{name}.npy", value)
            (args.output / f"{camera}_meta.json").write_text(json.dumps(meta, sort_keys=True, default=lambda v: np.asarray(v).tolist()) + "\n")
            cameras[camera] = {name: digest(args.output / f"{camera}_{name}.npy") for name in arrays}
            cameras[camera]["metadata"] = digest(args.output / f"{camera}_meta.json")
        installed = {inspect.getfile(cls): digest(inspect.getfile(cls))
                     for cls in (ControlEnv, MultiRegionRandomSampler, UniformRandomSampler)}
        result = {
            "suite": "libero_goal", "task": 0, "seed": args.seed,
            "condition": args.condition, "wall_s": time.perf_counter() - start,
            "sim_state_sha256": digest(args.output / "sim_state.npy"),
            "private_geometry_sha256": digest(args.output / "private_geometry.json"),
            "geometry": geometry, "cameras": cameras, "installed_source_sha256": installed,
            "script_sha256": digest(__file__), "interpreter": sys.executable,
        }
        (args.output / "identity.json").write_text(json.dumps(result, indent=2) + "\n")
    finally:
        facade.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--condition", choices=("control", "seeded"))
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("this private reset diagnostic is restricted to original tasks")
    if args.condition:
        run_child(args)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    identities = []
    for condition, seed in (("control", 0), ("seeded", 0), ("seeded", 1)):
        for repeat in range(2):
            output = args.output / f"{condition}_s{seed}_r{repeat}"
            command = [sys.executable, __file__, "--condition", condition, "--seed", str(seed), "--output", str(output)]
            with (args.output / f"{output.name}.log").open("x") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
            identities.append(json.loads((output / "identity.json").read_text()))
    comparisons = []
    for left, right in zip(identities[::2], identities[1::2]):
        comparisons.append({
            "condition": left["condition"], "seed": left["seed"],
            "same_sim_state": left["sim_state_sha256"] == right["sim_state_sha256"],
            "same_private_geometry": left["private_geometry_sha256"] == right["private_geometry_sha256"],
            "same_cameras": {camera: {name: value == right["cameras"][camera][name]
                                      for name, value in fields.items()}
                             for camera, fields in left["cameras"].items()},
            "changed_fixtures": [name for name, value in left["geometry"].items()
                                 if value["fixture"] and value != right["geometry"][name]],
        })
    report = {
        "purpose": "original-task initialization diagnosis; private truth never enters model inputs or training",
        "cases": identities, "comparisons": comparisons,
        "different_seed_changes_state": identities[2]["sim_state_sha256"] != identities[4]["sim_state_sha256"],
        "passed": all(row["same_sim_state"] and row["same_private_geometry"]
                      and all(all(fields.values()) for fields in row["same_cameras"].values())
                      for row in comparisons if row["condition"] == "seeded"),
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}))
    if not report["passed"]:
        raise RuntimeError("seeded independent resets differ; preserve probe and repair")


if __name__ == "__main__":
    main()
