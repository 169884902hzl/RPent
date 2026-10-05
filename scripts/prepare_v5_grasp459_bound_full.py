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
    arms = {"rpent_start_bound_full160": ("start_full160", {"full_prompt_binding": "target_first"}),
            "rpent_high10_short160": ("high_short160", {"contact_standoff_m": .10})}
    conditions, cases = {}, []
    for name, (base, changes) in arms.items():
        condition = copy.deepcopy(parent["conditions"][base])
        condition.update(contact_stop="rpent_pick", **changes)
        condition["overrides"]["grasp_thin_aperture_v1"] = True
        conditions[name] = condition
        cases.extend({**c, "condition": name, "name": c["name"].replace("_" + base + "_", "_" + name + "_")}
                     for c in parent["cases"] if c["condition"] == base)
    if len(cases) != 1200 or parent["truth_protocol"]["minimum_first_trials_per_class"] != 100:
        raise ValueError("requires the registered six-class100-trial cohort")
    cases.sort(key=lambda c: (c["trial_index"], c["group"], list(arms).index(c["condition"])))
    plan = {**parent, "conditions": conditions,
            "parent_manifest": {"path": str(args.manifest),
                                "sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest()},
            "binding_fix": "Full original instruction retained after explicit first pick of selected measured category. Original frypan grasp-only prompt unchanged.",
            "approach_fix": "Measured top+10cm final standoff with the same lift/translate/descend safe path; no original reset-height clamp on final waypoint.",
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
