"""Register first-grasp stop/aperture alternatives from an explicit cohort."""

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
    source = json.loads(args.manifest.read_text())
    if source["truth_protocol"]["minimum_first_trials_per_class"] != 100:
        raise ValueError("requires the registered100/class sustained-truth cohort")
    arms = {
        "current_thin80": ("current_direct", None),
        "high_thin160": ("high_short160", None),
        "rpent_high_thin160": ("high_short160", "rpent_pick"),
        "rpent_start_full_thin160": ("start_full160", "rpent_pick"),
    }
    conditions, cases = {}, []
    for name, (parent, stop) in arms.items():
        condition = copy.deepcopy(source["conditions"][parent])
        condition["overrides"]["grasp_thin_aperture_v1"] = True
        if stop:
            condition["contact_stop"] = stop
        conditions[name] = condition
        for case in source["cases"]:
            if case["condition"] == parent:
                cases.append({**case, "condition": name,
                              "name": case["name"].replace("_" + parent + "_", "_" + name + "_")})
    if len(cases) != 2400 or len({c["name"] for c in cases}) != 2400:
        raise ValueError("expected four paired six-class100-trial conditions")
    cases.sort(key=lambda c: (c["trial_index"], c["group"], list(arms).index(c["condition"])))
    plan = {**source, "conditions": conditions,
            "parent_manifest": {"path": str(args.manifest),
                                "sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest()},
            "verifier_change": "optional2mm nonempty aperture, backed by six CPU empty closure controls; unchanged3cm visual rise",
            "method_count_note": "Budget variants and identical clamped direct/above heights do not count as distinct methods. Public descent/ascent stop is compared separately from visual trial-lift stop.",
            "success_gate_unchanged": True, "new_training_rows": 0}
    args.output.mkdir(parents=True, exist_ok=False)
    for kind, selected in (("full", cases), ("smoke", [c for c in cases if c["trial_index"] == 0])):
        path = args.output / (kind + ".json")
        path.write_text(json.dumps({**plan, "cohort": kind, "cases": selected}, indent=2) + "\n")
        print(json.dumps({"path": str(path), "trials": len(selected),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
