"""Register outcome-unfiltered original exploration frame-calibration pilot.

Read only explicit skill516 parent manifest; no confirmation data or file
discovery. No threshold fitting, runtime edit, motion or Slurm submission.
"""

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path


ARMS = ("centre_full_subtask160", "handle_full_subtask160")
TYPES = ("pan_handle_full", "moka_handle_full")


def descriptor(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def digest_records(records):
    return hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build(parent, parent_file, trials_per_arm):
    if not 1 <= trials_per_arm <= 50:
        raise ValueError("pilot uses only the first repetition of the original registered exploration")
    if parent.get("qualification") is not False or parent.get("new_training_rows") != 0:
        raise ValueError("parent must be an original exploration, never confirmation or training")
    expected = {f"{kind}/{arm}": 100 for kind in TYPES for arm in ARMS}
    if parent["preregistered_requests_by_type_arm"] != expected:
        raise ValueError("requires the explicitly registered skill516 four-hundred-case parent")
    cases = []
    for case in parent["cases"]:
        if case["trial_index"] >= trials_per_arm:
            continue
        if case["initial_state_repetition"] != 0 or case["episode"]["suite"] not in {
                "libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}:
            raise ValueError("pilot must retain original task/init registrations")
        new = copy.deepcopy(case)
        new.update(name=case["name"] + "_sync520", parent_case_name=case["name"],
                   skill500_source_case_name=case.get("parent_case_name"), qualification=False)
        cases.append(new)
    if Counter(f"{c['type']}/{c['condition']}" for c in cases) != Counter({k: trials_per_arm for k in expected}):
        raise ValueError("stratified first-trial registration is incomplete")
    plan = copy.deepcopy(parent)
    plan.update(version="original-grasp-frame-calibration-pilot/1", parent_manifest=parent_file,
                cases=cases, qualification=False, confirmation=False, new_training_rows=0,
                purpose="outcome-unfiltered original single-subtask public-point/private-frame diagnostic pilot; no threshold fitting",
                frame_calibration={"phase_key": "private_frame_sync", "phase_key_default": False,
                    "label_source": "private measurement synchronized to public frame; never later final sustained-hold label",
                    "public_input": "same-capture per-view pre-fusion target points plus raw public qpos/EEF/body-quat",
                    "source_support": "requires parent-final probe implementation; old source is not declared compatible",
                    "threshold": None, "threshold_fitted_in_pilot": False,
                    "runtime_decisions_stop_receipts_changed": False,
                    "diagnostic_capture_policy": "read at existing refresh points; any necessary diagnostic scene/cache work must be isolated/restored; toolkit capture steps are never rolled back",
                    "sampling": f"first {trials_per_arm} parent trial indices per type/arm, before observing outcomes",
                    "shortfall": "if natural positive/negative/wide-aperture counts are insufficient, preregister further original trials/methods; retain all outcomes, do not tune on confirmation"})
    for condition in plan["conditions"].values():
        if condition["max_chunks"] != 160:
            raise ValueError("keep existing contact budget unchanged")
        if condition["overrides"]["grasp_measurement_calibration"]["opening_calibration"]["minimum_points_per_finger"] is not None:
            raise ValueError("pilot must not introduce an unmeasured point-count threshold")
        condition["private_frame_sync"] = True
        condition["overrides"]["record_sam_masks_v6"] = True
    plan["preregistered_requests_by_type_arm"] = dict(Counter(f"{c['type']}/{c['condition']}" for c in cases))
    seeds = [{"episode": c["episode"], "state_sha256": c["state_sha256"],
              "type": c["type"], "condition": c["condition"], "parent_case_name": c["parent_case_name"]} for c in cases]
    plan["paired_state_audit"] = {"nominal_requests": len(cases),
        "unique_scene_states_across_all_categories_and_arms": len({(c['episode']['suite'], c['episode']['task'], c['episode']['seed'], c['state_sha256']) for c in cases}),
        "registered_case_seed_records_sha256": digest_records(seeds), "labels_not_used_for_selection": True}
    return plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--trials-per-arm", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent_identity = descriptor(args.parent_manifest)
    if parent_identity["sha256"] != args.parent_sha256:
        raise ValueError("registered skill516 parent changed")
    parent = json.loads(args.parent_manifest.read_text())
    plan = build(parent, parent_identity, args.trials_per_arm)
    args.output.mkdir(parents=True, exist_ok=False)
    full = args.output / "pilot.json"
    full.write_text(json.dumps(plan, indent=2) + "\n")
    smoke = copy.deepcopy(plan)
    smoke["cases"] = [next(c for c in plan["cases"] if c["type"] == kind and c["condition"] == arm) for kind in TYPES for arm in ARMS]
    smoke["purpose"] = "four-case frame capture contract smoke, not qualification or threshold fitting"
    smoke["preregistered_requests_by_type_arm"] = {f"{kind}/{arm}": 1 for kind in TYPES for arm in ARMS}
    smoke["paired_state_audit"] = {"nominal_requests": 4, "unique_scene_states_across_all_categories_and_arms": 1,
                                  "labels_not_used_for_selection": True}
    smoke["pilot_manifest"] = descriptor(full)
    smoke_path = args.output / "smoke4.json"
    smoke_path.write_text(json.dumps(smoke, indent=2) + "\n")
    registration = {"prepare_script": descriptor(Path(__file__)), "parent_manifest": parent_identity,
                    "pilot_manifest": descriptor(full), "smoke_manifest": descriptor(smoke_path),
                    "requests": len(plan["cases"]), "requests_by_type_arm": plan["preregistered_requests_by_type_arm"],
                    "paired_state_audit": plan["paired_state_audit"], "phase_key": "condition.private_frame_sync=True",
                    "mask_key": "condition.overrides.record_sam_masks_v6=True", "qualification": False,
                    "new_training_rows": 0, "point_threshold": None, "source_not_created": True, "slurm_not_submitted": True}
    (args.output / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    print(json.dumps(registration, indent=2))


if __name__ == "__main__":
    main()
