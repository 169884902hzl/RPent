"""Register the next original-task grasp probe without changing an active cohort."""

import argparse
import copy
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = "9dca2edd661ccba0d6e69efb595c8951ba9eccb16c74584e48e1007adfb175d0"
    if hashlib.sha256(args.parent.read_bytes()).hexdigest() != expected:
        raise ValueError("registered1800-case parent manifest changed")
    parent = json.loads(args.parent.read_text())
    conditions, cases = {}, []
    for base in ("rpent_start_bound_full160", "rpent_high10_alias160"):
        name = base + "_stable_lower"
        conditions[name] = {**copy.deepcopy(parent["conditions"][base]),
                            "contact_verification": "stable_lower"}
        for case in parent["cases"]:
            if case["condition"] == base:
                cases.append({**case, "condition": name,
                              "name": case["name"].replace(base, name)})
    plan = {**parent, "conditions": conditions,
            "parent_manifest": {"path": str(args.parent), "sha256": expected},
            "verification_hypothesis": "public Pi0 pick then5cm trial lift, two fresh measured lower-extents>=3cm, separated by10 public close/hold steps at20Hz; wrist measurement if main view absent",
            "runtime_default_changed": False,
            "new_training_rows": 0,
            "method_count_note": "A verification/lift combination within the existing reset/full and high/short families; not a new genuinely distinct approach method.",
            "truth_protocol": {**parent["truth_protocol"],
                "measurement_only": True, "runtime_stop_uses_private_truth": False},
            "comparison_scope": "Smoke tests instrument correctness only. Full100/class required for qualification. Policy noise is not fixed across conditions."}
    args.output.mkdir(parents=True, exist_ok=False)
    for kind, selected in (("smoke", [c for c in cases if c["trial_index"] == 0]), ("full", cases)):
        path = args.output / (kind + ".json")
        path.write_text(json.dumps({**plan, "cohort": kind, "cases": selected}, indent=2) + "\n")
        print(json.dumps({"path": str(path), "trials": len(selected),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
