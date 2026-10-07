"""Compare each registered layout with the unchanged same-base CPU settle.

Preserve materialized records; explain natural settling separately from
declared perturbation. Geometry fingerprints exclude time, velocity and robot
qpos. This audit does not execute a skill or decide a confirmation outcome.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_pinned(reference):
    actual = identity(reference["path"])
    if actual["sha256"] != reference["sha256"]:
        raise ValueError("Pinned input changed: " + actual["path"])
    return json.loads(Path(actual["path"]).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--registry-sha256", required=True)
    parser.add_argument("--materialized", type=Path, required=True)
    parser.add_argument("--materialized-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("LIBERO_TYPE=standard is required")
    registry_ref = {"path": str(args.registry), "sha256": args.registry_sha256}
    materialized_ref = {"path": str(args.materialized), "sha256": args.materialized_sha256}
    registry, generated = read_pinned(registry_ref), read_pinned(materialized_ref)
    if generated["registry"] != registry_ref or len(generated["records"]) != 24:
        raise ValueError("The same registered 24 layout records are required")
    producer_files = generated["producer_files"]
    for reference in producer_files[1:]:
        if identity(reference["path"])["sha256"] != reference["sha256"]:
            raise ValueError("Installed/reset preparation dependency changed")
    from libero.libero.envs.env_wrapper import ControlEnv
    from rlinf.envs.libero.utils import benchmark
    import numpy as np

    seed_ref = producer_files[2]
    spec = importlib.util.spec_from_file_location("moka_layout_reset_seed", seed_ref["path"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args.output.mkdir(parents=True, exist_ok=False)
    suite = benchmark.get_benchmark("libero_90")()
    official_states = suite.get_task_init_states(19)
    declared = {record["name"]: record for record in registry["layout_rules"]}
    old_fingerprints, fingerprints, records = set(), set(), []
    def qpos_geometry(state, env):
        qpos = np.asarray(state)[1:1+env.sim.model.nq]
        result = {}
        for symbol, obj in {**env.objects_dict, **env.fixtures_dict}.items():
            poses = []
            for joint in obj.joints:
                address = env.sim.model.get_joint_qpos_addr(joint)
                pose = np.asarray(qpos[slice(*address)] if isinstance(address, tuple)
                                  else [qpos[address]], dtype=float).copy()
                if len(pose) == 7:
                    quaternion = pose[3:]
                    # q and -q denote the same orientation.
                    if next((value for value in quaternion if abs(value) > 1e-12), 1.0) < 0:
                        pose[3:] *= -1
                poses.append(np.round(pose, 6).tolist())
            result[symbol] = poses
        raw = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return hashlib.sha256(raw).hexdigest(), result
    for record in generated["records"]:
        rule = declared[record["name"]]
        row = {"name": record["name"], "original_preparation_status": record["status"],
               "original_gaps_retained": record["gaps"], "baseline_controls": 50,
               "baseline_policy": "same base, same 50 zero-motion/open controls, no perturbation",
               "audit_gaps": [], "qualification": False, "skill_trial_run": False}
        if record["status"] == "prep_error":
            row["audit_gaps"].append("original_preparation_error")
            records.append(row)
            continue
        base = record["base"]
        wrapper = ControlEnv(bddl_file_name=base["bddl"]["path"], use_camera_obs=False,
                             has_renderer=False, has_offscreen_renderer=False,
                             camera_names=[], ignore_done=True, horizon=10000)
        try:
            module.attach_reset_seed(wrapper)
            wrapper.seed(base["episode"]["seed"])
            wrapper.reset()
            original = np.asarray(official_states[base["episode"]["seed"]], dtype="<f8", order="C")
            if hashlib.sha256(original.tobytes()).hexdigest() != base["state_sha256"]:
                raise ValueError("Official generation base changed")
            wrapper.set_init_state(original)
            env = wrapper.env
            for state in official_states:
                old_fingerprints.add(qpos_geometry(state, env)[0])
            control = np.zeros(7)
            control[-1] = -1.0
            for _ in range(50):
                wrapper.step(control)
            baseline_state = np.asarray(wrapper.get_sim_state(), dtype="<f8", order="C")
            baseline_geometry = {name: env.sim.data.body_xpos[index].tolist()
                                 for name, index in env.obj_body_id.items()}
            baseline_file = args.output / f"{row['name']}_unchanged_baseline.json"
            baseline_file.write_text(json.dumps({"base": base, "rawstate": baseline_state.tolist(),
                "state_sha256": hashlib.sha256(baseline_state.tobytes()).hexdigest(),
                "geometry": baseline_geometry, "controls": 50, "goal_changed": False}, indent=2) + "\n")
            row["baseline_state"] = identity(baseline_file)
            raw = read_pinned(record["registered_layout_state"])
            state = np.asarray(raw["rawstate"], dtype="<f8", order="C")
            if hashlib.sha256(state.tobytes()).hexdigest() != record["state_sha256"]:
                raise ValueError("Materialized rawstate changed")
            fingerprint, poses = qpos_geometry(state, env)
            row.update(geometry_fingerprint=fingerprint, geometry_pose_data=poses,
                       geometry_fingerprint_encoding="named object/fixture joint qpos, normalized quaternion hemisphere, rounded1e-6; excludes robot/time/qvel; static furniture separately checked",
                       geometry_fingerprint_overlap_prior_official_task19=fingerprint in old_fingerprints,
                       geometry_fingerprint_overlap_another_layout=fingerprint in fingerprints)
            if fingerprint in old_fingerprints or fingerprint in fingerprints:
                row["audit_gaps"].append("geometric_state_overlap")
            fingerprints.add(fingerprint)
            other_deltas = {name: (np.asarray(record["geometry_after"][name])-np.asarray(position)).tolist()
                            for name, position in baseline_geometry.items()
                            if name in env.objects_dict and name != "moka_pot_1"}
            row["other_object_delta_vs_unchanged_baseline_m"] = other_deltas
            maximum = max((float(np.linalg.norm(delta)) for delta in other_deltas.values()), default=0.0)
            row["other_object_max_difference_vs_baseline_m"] = maximum
            row["self_added_2mm_check_source"] = "implementation preparation heuristic, not user skill/confirmation threshold; compare against same-budget baseline rather than floating official reset"
            row["natural_settle_only_gap_explained"] = maximum <= 0.002
            if maximum > 0.002:
                row["audit_gaps"].append("another_object_differs_from_unchanged_baseline_over2mm")
            actual_delta = np.asarray(record["geometry_after"]["moka_pot_1"])[:2]-np.asarray(baseline_geometry["moka_pot_1"])[:2]
            expected = np.asarray(rule["rule"]["transform"]["world_xy_translation_m"])
            row["moka_xy_delta_vs_baseline_m"] = actual_delta.tolist()
            row["moka_xy_transform_error_vs_baseline_m"] = (actual_delta-expected).tolist()
            if float(np.linalg.norm(actual_delta-expected)) > 0.002:
                row["audit_gaps"].append("registered_xy_transform_not_preserved_after_settle")
            row["remaining_original_gaps"] = [gap for gap in record["gaps"]
                if gap != "another_original_object_moved_over_2mm_during_settle"]
            row["audit_gaps"] += row["remaining_original_gaps"]
            row["status"] = "baseline_audit_prepared" if not row["audit_gaps"] else "baseline_audit_gap"
        finally:
            wrapper.close()
        records.append(row)
    summary = {"registry": registry_ref, "materialized": materialized_ref,
               "producer": identity(__file__), "records": records,
               "declared_layouts": 24, "baseline_audited": len(records),
               "prepared_after_same_budget_baseline_audit": sum(row.get("status") == "baseline_audit_prepared" for row in records),
               "unique_geometry_fingerprints": len(fingerprints),
               "physics_scope": "24 unchanged-base fixed50-control preparation diagnostics only",
               "skill_trials": 0, "qualification": False,
               "statistical_independence_claimed": False,
               "old_records_overwritten": False, "layout_rule_changed": False,
               "new_training_rows": 0, "GPU_used": False}
    (args.output / "report.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key:value for key,value in summary.items() if key != "records"}, indent=2))


if __name__ == "__main__":
    main()
