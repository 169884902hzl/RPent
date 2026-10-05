"""Register twelve original40 runtime-profile trials without outcome selection."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from scripts.probe_v5_skill501_original import validate_manifest


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def class_name(category):
    name = category.lower()
    if "bowl" in name:
        return "bowl"
    if "bottle" in name or name in {"ketchup", "salad dressing", "barbecue sauce"}:
        return "bottle"
    if "mug" in name:
        return "mug"
    if "box" in name or name in {"cream cheese", "butter", "chocolate pudding"}:
        return "box"
    return None


def flatten(value):
    if isinstance(value, list):
        return [item for child in value for item in flatten(child)]
    return [value]


def build_manifest(parent, calibration, parent_identity, calibration_identity):
    catalog = parent["original_task_catalog"]
    if len(catalog) != 40 or any(t["suite"] not in {"libero_spatial", "libero_object", "libero_goal", "libero_10"} for t in catalog):
        raise ValueError("requires the explicit original40 catalog")
    if calibration["runtime_object_truth_used"] is not False:
        raise ValueError("robot calibration must not supply object truth")
    inherited = copy.deepcopy(parent["conditions"]["centre_full_subtask160"]["overrides"])
    inherited.update(grasp_category_profiles_v1=True, grasp_independent_views_v1=True,
        grasp_measurement_calibration=copy.deepcopy(calibration),
        grasp_safe_approach_v2=True, grasp_approach_v1=False, grasp_retry_v1=False,
        wrist_refine_v1=False, grasp_clearance_v1=False, grasp_rim_v1=False,
        native_grasp_stop_v1=False, skill_profile="none", legal_memory_manifest=None,
        manual="none", card=None, rpent_memory_index=None)
    condition_name = "runtime_first4_category160_independent_verifier"
    condition = {"executor": "current", "max_chunks": 160, "private_frame_sync": True,
        "overrides": inherited,
        "public_control": "runtime grasp_category_profiles_v1; no probe helper or profile override",
        "new_interventions": ["independent two-view verifier with robot calibration513",
            "C public return to observed episode pose after registered recovery displacement"],
        "qualification_authorized": False}
    cases = []
    for group in ("bottle", "bowl", "box", "mug"):
        eligible = []
        for task in catalog:
            goal_symbols = set(flatten(task["oracle_goal_predicates"]))
            for symbol, category in sorted(task["symbol_categories"].items()):
                if class_name(category) == group and symbol in goal_symbols:
                    eligible.append((task, symbol, category))
        selected, tasks_seen = [], set()
        for entry in eligible:
            key = entry[0]["suite"], entry[0]["task"]
            if key in tasks_seen:
                continue
            selected.append(entry)
            tasks_seen.add(key)
            if len(selected) == 2:
                break
        if len(selected) != 2:
            raise ValueError("requires two fixed original40 goal-object tasks per class")
        trials = [(selected[0], "initial", 0), (selected[1], "initial", 0),
                  (selected[0], "public_recovery", 0)]
        for index, ((task, symbol, category), phase, seed) in enumerate(trials):
            setup = [] if phase == "initial" else [
                {"tool": "retreat", "mode": "public_retreat"},
                {"tool": "measured_offset", "offset_m": [.10, 0., 0.], "gripper": -1}]
            case = {"name": f"first4_{group}_{task['suite']}_t{task['task']}_s{seed}_{phase}",
                "kind": "grasp", "type": "runtime_first4_" + group, "group": group,
                "mode": "direct", "runtime_tool": "grasp" if phase == "initial" else "regrasp_restage",
                "object_symbol": symbol, "object_category": category,
                "original_instruction": task["instruction"],
                "instruction_sha256": task["instruction_sha256"],
                "episode": {"suite": task["suite"], "task": task["task"], "seed": seed},
                "state_sha256": task["state_sha256"][seed],
                "bddl": task["bddl"], "init_file": task["init_file"],
                "setup": setup, "condition": condition_name, "trial_index": index,
                "phase": phase, "qualification": False,
                "private_metadata_use": "original-task expert binding and diagnostic labels only; motion uses public perception/proprioception"}
            cases.append(case)
    plan = {"version": "grasp525_first4_runtime_smoke/1",
        "purpose": "runtime integration smoke, not confirmation or training admission",
        "parent_manifest": parent_identity, "runtime_calibration_file": calibration_identity,
        "base_config": parent["base_config"], "conditions": {condition_name: condition},
        "cases": cases, "selection": "first two distinct original40 goal-object tasks in explicit catalog order; no results read",
        "pairing": "each public-recovery trial starts from the same official state as its first initial trial; real public retreat then measured+10cm X movement",
        "qualification_authorized": False, "new_training_rows": 0,
        "runtime_default_changed": False, "state_truth_in_runtime": False,
        "public_motion_source": "measured EEF XYZ/quat and object perception only, no private restore/attach",
        "metrics": ["post-receipt0.5s true sustained grasp", "public grasp_verified true/false/null",
            "verifier TP/TN/FP/FN/unknown", "actual Pi0 actions", "C public pose return residual", "source and per-case choices SHA"],
        "frozen_recipe_caveat": "C target_first+current original instruction and B selected-category short prompt preserve 160chunks, but independent verifier and later C return are NEW interventions, not old first4 qualification"}
    validate_manifest(plan)
    return plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--parent-sha", required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--calibration-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent_id, calibration_id = identity(args.parent), identity(args.calibration)
    if parent_id["sha256"] != args.parent_sha or calibration_id["sha256"] != args.calibration_sha:
        raise ValueError("explicit input changed")
    plan = build_manifest(json.loads(args.parent.read_text()), json.loads(args.calibration.read_text()), parent_id, calibration_id)
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output / "smoke.json"
    output.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"cases": len(plan["cases"]), "manifest": identity(output), "qualification_authorized": False}))


if __name__ == "__main__":
    main()
