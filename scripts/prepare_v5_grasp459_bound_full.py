"""Register target-first full-instruction probes on the same original scenes."""

import argparse
import copy
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent = json.loads(args.manifest.read_text())
    name = "rpent_start_bound_full160"
    condition = copy.deepcopy(parent["conditions"]["start_full160"])
    condition["contact_stop"] = "rpent_pick"
    condition["full_prompt_binding"] = "target_first"
    condition["overrides"]["grasp_thin_aperture_v1"] = True
    cases = [{**c, "condition": name, "name": c["name"].replace("_start_full160_", "_" + name + "_")}
             for c in parent["cases"] if c["condition"] == "start_full160"]
    if len(cases) != 600 or parent["truth_protocol"]["minimum_first_trials_per_class"] != 100:
        raise ValueError("requires the registered six-class100-trial cohort")
    plan = {**parent, "conditions": {name: condition},
            "parent_manifest": {"path": str(args.manifest),
                                "sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest()},
            "binding_fix": "Full original instruction retained after explicit first pick of selected measured category. Original frypan grasp-only prompt unchanged.",
            "method_count_note": "This fixes target ordering within the reset/full-instruction family; it is not an additional physical approach method.",
            "success_gate_unchanged": True, "new_training_rows": 0}
    args.output.mkdir(parents=True, exist_ok=False)
    for kind, selected in (("full", cases), ("smoke", [c for c in cases if c["trial_index"] == 0])):
        p = args.output / (kind + ".json")
        p.write_text(json.dumps({**plan, "cohort": kind, "cases": selected}, indent=2) + "\n")
        print(json.dumps({"path": str(p), "trials": len(selected),
                          "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
