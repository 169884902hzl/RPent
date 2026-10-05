"""Register original pan trials with current dual-view placement evidence."""

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
    condition = copy.deepcopy(parent["conditions"]["centre_full_subtask160"])
    condition.update(placement_rgbd_evidence=True, private_frame_sync=True)
    condition.setdefault("overrides", {}).update(record_sam_masks_v6=True)
    cases = []
    for original in parent["cases"]:
        if (original["condition"] == "centre_full_subtask160" and original["object_category"] == "frypan"
                and original["initial_state_repetition"] == 0 and original["episode"]["seed"] < 12):
            case = copy.deepcopy(original)
            case.update(name=original["name"] + "_place527", condition="centre_full_subtask160_place527",
                        qualification=False, parent_case_name=original["name"])
            cases.append(case)
    if len(cases) != 12 or len({case["state_sha256"] for case in cases}) != 12:
        raise ValueError("expected 12 distinct registered original development scenes")
    plan = {"version": "original-placement-rgbd-evidence/1-dev",
            "parent_manifest": {"path": str(args.parent_manifest),
                                "sha256": hashlib.sha256(args.parent_manifest.read_bytes()).hexdigest()},
            "base_config": parent["base_config"], "choice_package": parent["choice_package"],
            "conditions": {"centre_full_subtask160_place527": condition}, "cases": cases,
            "qualification": False, "training_rows": 0,
            "sampling": "existing first and second post-subtask captures; selected target queried in both",
            "limits": ["Original development states reuse is explicit; not an independent confirmation batch.",
                       "Private predicates are separate read-only labels; public verifier is unchanged.",
                       "Natural physical failures are retained; no failure record is replaced.",
                       "Existing world maps are float16; raw metric depth is unavailable."]}
    validate_manifest(plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(plan, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"cases": len(cases), "manifest": str(args.output),
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
