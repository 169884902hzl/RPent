"""Isolate original π0.5 sentence versus transfer template at its initial pose."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from scripts.probe_v5_skill501_original import validate_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    parent = json.loads(args.parent_manifest.read_text())
    base_condition = copy.deepcopy(parent["conditions"]["centre_full_subtask160"])
    base_condition.update(profile="original_initial_pose", private_frame_sync=True)
    base_condition["overrides"]["record_sam_masks_v6"] = True
    conditions = {"initial_pose_transfer_template160": copy.deepcopy(base_condition),
                  "initial_pose_exact_original160": copy.deepcopy(base_condition)}
    conditions["initial_pose_exact_original160"]["contact_prompt_source"] = "exact_original_instruction"
    cases = []
    for original in parent["cases"]:
        if (original["condition"] != "centre_full_subtask160" or original["object_category"] != "moka pot"
                or original["initial_state_repetition"] != 0 or original["episode"]["seed"] >= 4):
            continue
        if original["episode"] != {"suite": "libero_10", "task": 2, "seed": original["episode"]["seed"]}:
            raise ValueError("paired original-task sentence must actually target the selected moka pot")
        for condition in conditions:
            case = copy.deepcopy(original)
            case.update(name=f"moka530_{condition}_s{original['episode']['seed']}", condition=condition,
                        parent_case_name=original["name"], qualification=False,
                        control_scope="complete original task" if "exact_original" in condition else "complete single transfer subtask")
            cases.append(case)
    if len(cases) != 8 or len({c["state_sha256"] for c in cases}) != 4:
        raise ValueError("expected four paired original development states")
    plan = {"version": "moka-original-prompt-initial-pose/1-dev", "base_config": parent["base_config"],
            "choice_package": parent["choice_package"], "conditions": conditions, "cases": cases,
            "parent_manifest": {"path": str(args.parent_manifest),
                                "sha256": hashlib.sha256(args.parent_manifest.read_bytes()).hexdigest()},
            "qualification": False, "new_training_rows": 0,
            "hypothesis": "initial pose and original instruction distribution, independently of SAM query repair",
            "pairing": "same four official states; same 160 chunks and measurements; only sentence differs",
            "limits": ["Development pilot, not independent confirmation; old trials retained.",
                       "Exact original instruction includes stove turn-on; transfer-only prompt does not.",
                       "During-skill sustained grasp, final placement and whole original solved() are distinct.",
                       "No high-approach pose modification; not claimed to be the old target-first C recipe.",
                       "No new query ladder or verifier thresholds are enabled."]}
    validate_manifest(plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(plan, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"cases": len(cases), "unique_states": 4,
                      "manifest_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
