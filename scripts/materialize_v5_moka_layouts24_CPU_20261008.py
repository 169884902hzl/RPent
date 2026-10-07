"""Materialize the fixed 24 original moka layouts without a policy or renderer.

This is CPU preparation, not a skill or confirmation run. Private scene
geometry is used only to make and audit original-scene initial states.
"""

import argparse
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import time
import traceback


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_pinned(path, sha):
    actual = identity(path)
    if actual["sha256"] != sha:
        raise ValueError("Pinned input changed: " + actual["path"])
    return json.loads(Path(actual["path"]).read_text()), actual


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--registry-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reset-seed-source", type=Path, required=True)
    parser.add_argument("--reset-seed-source-sha256", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("LIBERO_TYPE=standard is required")
    plan, registry_ref = read_pinned(args.registry, args.registry_sha256)
    rules = plan["layout_rules"]
    if len(rules) != 24 or plan["policy"]["physics_executed"] != 0:
        raise ValueError("The CPU preregistered 24-layout declaration is required")
    if any(r["rule"]["original_scene"] != {"suite": "libero_90", "task": 19}
           or r["rule"]["moved_object_symbol"] != "moka_pot_1" for r in rules):
        raise ValueError("Only the registered original task19 moka object may change")
    import numpy as np
    from rlinf.envs.libero.utils import benchmark
    from libero.libero.envs.env_wrapper import ControlEnv
    seed_reference = identity(args.reset_seed_source)
    if seed_reference["sha256"] != args.reset_seed_source_sha256:
        raise ValueError("Pinned deterministic-reset adapter changed")
    spec = importlib.util.spec_from_file_location("moka_layout_reset_seed", args.reset_seed_source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    attach_reset_seed = module.attach_reset_seed

    suite = benchmark.get_benchmark("libero_90")()
    states = suite.get_task_init_states(19)
    task = suite.get_task(19)
    references = [identity(__file__), identity(inspect.getfile(ControlEnv)), seed_reference]
    source = rules[0]["base_official_state"]
    bddl, init_file = source["bddl"], source["init_file"]
    for reference in (bddl, init_file):
        if identity(reference["path"])["sha256"] != reference["sha256"]:
            raise ValueError("Original asset changed")
    for record in rules:
        base = record["base_official_state"]
        state = np.asarray(states[base["episode"]["seed"]], dtype="<f8", order="C")
        if hashlib.sha256(state.tobytes()).hexdigest() != base["state_sha256"]:
            raise ValueError("Registered official generation-base state changed")
    if task.language != "put the moka pot on the stove":
        raise ValueError("Original task19 instruction changed")
    args.output.mkdir(parents=True, exist_ok=False)
    header = {"registry": registry_ref, "producer_files": references,
              "preflight_only": args.preflight_only, "official_states_checked": 24,
              "physics_executed": False, "jobs_submitted": 0,
              "policy_or_model_used": False, "SAM_used": False, "GPU_used": False}
    if args.preflight_only:
        (args.output / "CPU_preflight.json").write_text(json.dumps(header, indent=2) + "\n")
        print(json.dumps(header, indent=2))
        return
    prior_hashes = {r["state_sha256"] for r in plan["official_state_audit"]}
    prior_hashes.update(plan["training_raw_state_sha256"])
    # Include registered states outside the 200-row pool, without opening outcomes.
    for reference in plan["exclusion_manifests"]:
        manifest, _ = read_pinned(reference["path"], reference["sha256"])
        prior_hashes.update(case["state_sha256"] for case in manifest["cases"])
    seen, records = set(), []
    for declared in rules:
        start = time.perf_counter()
        directory = args.output / declared["name"]
        directory.mkdir()
        row = {"name": declared["name"], "layout_seed": declared["rule"]["layout_seed"],
               "base_used": True, "official_initial_state": False,
               "rule_sha256": declared["rule_sha256"], "base": declared["base_official_state"],
               "private_geometry_use": "state preparation only; never policy/action/stop",
               "qualification": False, "skill_trial_run": False, "gaps": []}
        wrapper = None
        try:
            base = declared["base_official_state"]
            seed = base["episode"]["seed"]
            # Same original task and deterministic reset seeding as the runtime.
            wrapper = ControlEnv(bddl_file_name=bddl["path"], use_camera_obs=False,
                                 has_renderer=False, has_offscreen_renderer=False,
                                 camera_names=[], ignore_done=True, horizon=10000)
            attach_reset_seed(wrapper)
            wrapper.seed(seed)
            wrapper.reset()
            original = np.asarray(states[seed], dtype="<f8", order="C")
            wrapper.set_init_state(original)
            restored = np.asarray(wrapper.get_sim_state(), dtype="<f8", order="C")
            row["base_restore_max_abs_error"] = float(np.max(np.abs(original - restored)))
            if row["base_restore_max_abs_error"] > 1e-8:
                raise ValueError("Official base did not restore exactly")
            env, sim = wrapper.env, wrapper.sim
            objects = env.objects_dict
            obj = objects["moka_pot_1"]
            if len(obj.joints) != 1:
                raise ValueError("Expected one free joint for the original moka object")
            joint = obj.joints[0]
            pose = np.asarray(sim.data.get_joint_qpos(joint), dtype="<f8").copy()
            if pose.shape != (7,):
                raise ValueError("Moka joint is not a free joint")
            qpos_before, qvel_before = np.array(sim.data.qpos), np.array(sim.data.qvel)
            fixture_before = {name: {"model_pos": sim.model.body_pos[index].tolist(),
                                     "model_quat": sim.model.body_quat[index].tolist()}
                              for name, index in env.obj_body_id.items() if name in env.fixtures_dict}
            geometry_before = {name: sim.data.body_xpos[index].tolist()
                               for name, index in env.obj_body_id.items()}
            transform = declared["rule"]["transform"]
            pose[:2] += transform["world_xy_translation_m"]
            angle = math.radians(transform["world_yaw_delta_deg"]) / 2
            # Free-joint MuJoCo quaternions are w,x,y,z. Left-multiply world yaw.
            w, x, y, z = pose[3:]
            c, s = math.cos(angle), math.sin(angle)
            pose[3:] = (c*w-s*z, c*x-s*y, c*y+s*x, c*z+s*w)
            sim.data.set_joint_qpos(joint, pose)
            sim.forward()
            proposed = np.asarray(wrapper.get_sim_state(), dtype="<f8", order="C")
            proposed_pose = np.array(sim.data.get_joint_qpos(joint))
            qpos_addr = sim.model.get_joint_qpos_addr(joint)
            if not isinstance(qpos_addr, tuple) or qpos_addr[1]-qpos_addr[0] != 7:
                raise ValueError("Unexpected original moka qpos slice")
            outside = np.ones(sim.model.nq, dtype=bool)
            outside[qpos_addr[0]:qpos_addr[1]] = False
            if not np.array_equal(qpos_before[outside], np.asarray(sim.data.qpos)[outside]):
                raise ValueError("The declaration modified another joint before stabilization")
            np.save(directory / "proposed_rawstate.npy", proposed)
            row["proposed_state_sha256"] = hashlib.sha256(proposed.tobytes()).hexdigest()
            # Fixed 50 zero-motion/open-gripper controls. No goal predicate controls stopping.
            control = np.zeros(7)
            control[-1] = -1.0
            for _ in range(50):
                wrapper.step(control)
            settled_pose = np.array(sim.data.get_joint_qpos(joint))
            settled_qpos = np.array(sim.data.qpos)
            row["poststabilization_moka_xyz_delta_m"] = (settled_pose[:3]-proposed_pose[:3]).tolist()
            row["poststabilization_other_qpos_max_abs_delta"] = float(np.max(np.abs(settled_qpos[outside]-qpos_before[outside])))
            # Restore only robot initial joints after neutral settling, so the layout
            # does not inherit a different policy start pose. Other objects stay physical.
            robot = env.robots[0]
            robot_indices = np.asarray(robot._ref_joint_pos_indexes, dtype=int)
            gripper_indices = np.asarray([index for values in robot._ref_gripper_joint_pos_indexes.values()
                                          for index in values], dtype=int)
            robot_indices = np.unique(np.concatenate((robot_indices, gripper_indices)))
            sim.data.qpos[robot_indices] = qpos_before[robot_indices]
            sim.data.qvel[robot._ref_joint_vel_indexes] = qvel_before[robot._ref_joint_vel_indexes]
            gripper_vel_indices = [index for values in robot._ref_gripper_joint_vel_indexes.values()
                                   for index in values]
            sim.data.qvel[gripper_vel_indices] = qvel_before[gripper_vel_indices]
            sim.forward()
            state = np.asarray(wrapper.get_sim_state(), dtype="<f8", order="C")
            row["state_sha256"] = hashlib.sha256(state.tobytes()).hexdigest()
            row["robot_initial_qpos_restored_after_settle"] = True
            fixture_after = {name: {"model_pos": sim.model.body_pos[index].tolist(),
                                    "model_quat": sim.model.body_quat[index].tolist()}
                             for name, index in env.obj_body_id.items() if name in env.fixtures_dict}
            row["fixed_furniture_unchanged"] = fixture_before == fixture_after
            row["geometry_before"] = geometry_before
            row["geometry_after"] = {name: sim.data.body_xpos[index].tolist()
                                     for name, index in env.obj_body_id.items()}
            row["other_object_xyz_delta_m"] = {
                name: (np.asarray(row["geometry_after"][name])-np.asarray(position)).tolist()
                for name, position in geometry_before.items() if name in objects and name != "moka_pot_1"}
            if any(np.linalg.norm(delta) > 0.002 for delta in row["other_object_xyz_delta_m"].values()):
                row["gaps"].append("another_original_object_moved_over_2mm_during_settle")
            moka_geoms = {sim.model.geom_name2id(name) for name in obj.contact_geoms}
            contacts = [{"geom1": int(c.geom1), "geom2": int(c.geom2), "dist_m": float(c.dist)}
                        for c in sim.data.contact[:sim.data.ncon]
                        if c.geom1 in moka_geoms or c.geom2 in moka_geoms]
            row["moka_contact_evidence_after_settle"] = contacts
            if any(c["dist_m"] < -0.002 for c in contacts):
                row["gaps"].append("moka_geometry_penetration_over_2mm")
            if not row["fixed_furniture_unchanged"]:
                row["gaps"].append("fixed_furniture_changed")
            if row["state_sha256"] in prior_hashes or row["state_sha256"] in seen:
                row["gaps"].append("registered_rawstate_hash_overlap")
            if not np.isfinite(state).all():
                row["gaps"].append("nonfinite_stabilized_state")
            # Exact restore is audited separately; it is not a skill trial.
            wrapper.set_init_state(state)
            replay = np.asarray(wrapper.get_sim_state(), dtype="<f8", order="C")
            row["layout_restore_max_abs_error"] = float(np.max(np.abs(replay-state)))
            if row["layout_restore_max_abs_error"] > 1e-8:
                row["gaps"].append("registered_state_restore_mismatch")
            rawfile = directory / "registered_rawstate.json"
            rawfile.write_text(json.dumps({"episode": base["episode"], "bddl": bddl,
                                          "layout_seed": row["layout_seed"], "rawstate": state.tolist(),
                                          "state_sha256": row["state_sha256"], "base_used": True,
                                          "rule_sha256": row["rule_sha256"], "qualification": False},
                                         indent=2, allow_nan=False) + "\n")
            row["registered_layout_state"] = identity(rawfile)
            seen.add(row["state_sha256"])
            row.update(status="prepared" if not row["gaps"] else "prep_gap",
                       stabilization_controls=50, goal_asset_sha256=bddl["sha256"],
                       task_goal_changed=False, private_goal_used_to_select_state=False)
        except Exception:
            row.update(status="prep_error", traceback=traceback.format_exc())
        finally:
            if wrapper is not None:
                wrapper.close()
            row["wall_s"] = time.perf_counter()-start
            (directory / "preparation_evidence.json").write_text(json.dumps(row, indent=2, allow_nan=False) + "\n")
            records.append(row)
    summary = {**header, "physics_executed": True, "declared_layouts": 24,
               "prepared": sum(r["status"] == "prepared" for r in records),
               "prep_gap": sum(r["status"] == "prep_gap" for r in records),
               "prep_error": sum(r["status"] == "prep_error" for r in records),
               "unique_rawstate_hashes": len(seen), "records": records,
               "statistical_independence_claimed": False,
               "skill_trials": 0, "qualification": False,
               "no_replacement": "all declarations retained; no displacement/yaw adjusted by results"}
    (args.output / "manifest.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k:v for k,v in summary.items() if k != "records"}, indent=2))
    if summary["prep_error"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
