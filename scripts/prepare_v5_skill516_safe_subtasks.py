"""Register two measured safe approaches on explicit original skill500 cases.

This paired, repeated-state exploration is not independent qualification or
training. It reads only its named parent manifest and robot calibration file.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path


ORIGINAL_SUITES = {"libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}
TYPES = {"pan_handle_full": "frypan", "moka_handle_full": "moka pot"}
ARMS = ("centre_full_subtask160", "handle_full_subtask160")


def identity(path: Path) -> dict:
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load_explicit(path: Path, expected_sha: str) -> dict:
    actual = identity(path)
    if actual["sha256"] != expected_sha:
        raise ValueError(f"explicit input changed: {path}")
    return json.loads(path.read_text())


def state_identity(case: dict) -> tuple:
    ep = case["episode"]
    return ep["suite"], ep["task"], ep["seed"], case["state_sha256"]


def digest_records(records: list) -> str:
    return hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_manifest(parent: dict, calibration: dict, parent_file: dict, calibration_file: dict) -> dict:
    selected = [case for case in parent["cases"]
                if case["condition"] == "handle_full_subtask160" and case["type"] in TYPES]
    if Counter(case["type"] for case in selected) != Counter({kind: 100 for kind in TYPES}):
        raise ValueError("requires the explicit parent hundred nominal trials per original object category")
    if calibration.get("runtime_object_truth_used") is not False:
        raise ValueError("calibration must not use runtime object truth")
    if calibration["opening_calibration"].get("minimum_points_per_finger") is not None:
        raise ValueError("this registered exploration preserves uncalibrated wide-opening point threshold")
    opening = calibration["opening_calibration"]
    if not 0 <= opening["closed_empty_max_m"] < opening["open_empty_min_m"] <= opening["max_sensor_opening_m"]:
        raise ValueError("measured opening calibration is invalid")
    if calibration["robot_rigid_transform_validation"]["policy_proprio_dims"] != 39:
        raise ValueError("π0.5 proprio contract changed")

    conditions = {}
    template = parent["conditions"]["handle_full_subtask160"]
    for arm in ARMS:
        condition = copy.deepcopy(template)
        condition.update(executor="vla_subtask", profile="high_short", mode="direct", max_chunks=160,
                         contact_standoff_m=.10, contact_stop="subtask_measurement_or_budget",
                         grasp_early_stop=False, contact_category_aliases={"frypan": "frying pan"},
                         contact_approach="measured_bounds_centre" if arm.startswith("centre_") else "measured_handle")
        condition.pop("handle_missing_policy", None)
        if arm.startswith("handle_"):
            condition["contact_approach_fallback"] = "measured_bounds_centre"
        else:
            condition.pop("contact_approach_fallback", None)
        condition["overrides"].update(grasp_independent_views_v1=True,
                                       grasp_measurement_calibration=copy.deepcopy(calibration))
        conditions[arm] = condition

    cases = []
    for kind, category in TYPES.items():
        originals = sorted((case for case in selected if case["type"] == kind), key=lambda c: c["trial_index"])
        if [case["trial_index"] for case in originals] != list(range(100)):
            raise ValueError("parent trial index is incomplete or repeated")
        for original in originals:
            if (original["episode"]["suite"] not in ORIGINAL_SUITES
                    or original["kind"] != "grasp_then_subtask"
                    or original["object_category"] != category
                    or original["mode"] not in {"on", "in"}
                    or not original.get("target_symbol")
                    or len(original["state_sha256"]) != 64):
                raise ValueError("requires a registered original full contact/transfer subtask")
            if category == "frypan" and "frying pan" not in original["subtask_prompt"]:
                raise ValueError("registered pan prompt must use original LIBERO frying pan name")
            if category == "moka pot" and "moka pot" not in original["subtask_prompt"]:
                raise ValueError("registered moka prompt must use original LIBERO moka pot name")
            for arm in ARMS:
                case = copy.deepcopy(original)
                ep = case["episode"]
                case.update(name=f"{kind}_{ep['suite']}_t{ep['task']}_s{ep['seed']}_r{case['initial_state_repetition']}_{arm}",
                            condition=arm, parent_case_name=original["name"], qualification=False,
                            prompt_scope="complete original-scene single transfer subtask, not a grasp-only prompt",
                            instruction_sha256=hashlib.sha256(case["subtask_prompt"].encode()).hexdigest())
                cases.append(case)

    counts = Counter(f"{case['type']}/{case['condition']}" for case in cases)
    expected = Counter({f"{kind}/{arm}": 100 for kind in TYPES for arm in ARMS})
    if counts != expected or len({case["name"] for case in cases}) != 400:
        raise ValueError("paired four-hundred-trial registration failed")
    state_rows = [dict(episode=case["episode"], state_sha256=case["state_sha256"],
                       type=case["type"], condition=case["condition"],
                       trial_index=case["trial_index"], initial_state_repetition=case["initial_state_repetition"])
                  for case in cases]
    by_arm = {}
    for label in counts:
        subset = [case for case in cases if f"{case['type']}/{case['condition']}" == label]
        unique = len({state_identity(case) for case in subset})
        by_arm[label] = {"nominal_requests": len(subset), "unique_scene_states": unique,
                         "repeated_requests": len(subset) - unique,
                         "state_sha256_sequence": [case["state_sha256"] for case in subset],
                         "episode_seed_sequence_sha256": digest_records([case["episode"] for case in subset])}
    plan = {k: copy.deepcopy(v) for k, v in parent.items() if k not in {"conditions", "cases", "preregistered_requests_by_type_arm"}}
    plan.update(version="original-safe-subtask-exploration/1", parent_manifest=parent_file,
                runtime_calibration_file=calibration_file, conditions=conditions, cases=cases,
                qualification=False, confirmation=False, new_training_rows=0, runtime_default_changed=False,
                purpose="paired original-task pan/moka complete single-subtask exploration, not confirmation or training",
                state_repetition="explicit parent 50 official resets twice per category and approach; not 100 independent states",
                training_boundary="no training task additions; original40/90 allowed only for this single-skill exploration",
                paired_state_audit={"nominal_requests": 400,
                    "unique_scene_states_across_all_categories_and_arms": len({state_identity(c) for c in cases}),
                    "by_type_arm": by_arm, "registered_case_seed_records_sha256": digest_records(state_rows)},
                preregistered_requests_by_type_arm=dict(counts),
                approach_policy={"centre": "current measured bounds centre at object top + 0.10m",
                    "handle": "only a currently measured true handle; otherwise explicitly recorded measured_bounds_centre fallback",
                    "no_synthetic_handle": True,
                    "no_object_truth_in_runtime": True},
                independent_confirmation_required={"new_nonoverlapping_states_per_class": 100,
                    "overall_truth_success_min": .95, "per_class_truth_success_min": .90,
                    "runtime_verifier_agreement_min": .95, "evaluated_in_this_exploration": False})
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--calibration-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent = load_explicit(args.parent_manifest, args.parent_sha256)
    calibration = load_explicit(args.calibration, args.calibration_sha256)
    plan = build_manifest(parent, calibration, identity(args.parent_manifest), identity(args.calibration))
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = args.output / "full.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    smoke = copy.deepcopy(plan)
    smoke["cases"] = [next(case for case in plan["cases"] if case["type"] == kind and case["condition"] == arm)
                      for kind in TYPES for arm in ARMS]
    smoke["purpose"] = "four-case development smoke; never a score or independent confirmation"
    smoke["preregistered_requests_by_type_arm"] = dict(Counter(f"{c['type']}/{c['condition']}" for c in smoke["cases"]))
    smoke["full_exploration_manifest"] = identity(manifest)
    smoke["paired_state_audit"] = {"nominal_requests": len(smoke["cases"]),
                                  "unique_scene_states_across_all_categories_and_arms": len({state_identity(c) for c in smoke["cases"]}),
                                  "qualification": False}
    smoke_path = args.output / "smoke.json"
    smoke_path.write_text(json.dumps(smoke, indent=2) + "\n")
    audit = {"prepare_script": identity(Path(__file__)), "parent_manifest": identity(args.parent_manifest),
             "runtime_calibration_file": identity(args.calibration), "full_manifest": identity(manifest),
             "smoke_manifest": identity(smoke_path), "qualification": False, "new_training_rows": 0,
             "requests": len(plan["cases"]), "requests_by_type_arm": plan["preregistered_requests_by_type_arm"],
             "paired_state_audit": plan["paired_state_audit"],
             "prompt_examples": {kind: next(c["subtask_prompt"] for c in plan["cases"] if c["type"] == kind) for kind in TYPES},
             "runtime_source_not_snapshotted": True}
    (args.output / "registration.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({k: v for k, v in audit.items() if k != "paired_state_audit"}, indent=2))


if __name__ == "__main__":
    main()
