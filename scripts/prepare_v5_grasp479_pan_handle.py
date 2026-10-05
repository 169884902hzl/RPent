"""Register measured-pan-handle staging against the identical alias control."""

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
        raise ValueError("registered first100/class parent changed")
    parent = json.loads(args.parent.read_text())
    base = "rpent_high10_alias160"
    names = (base + "_handle_control", base + "_measured_pan_handle")
    conditions = {name: copy.deepcopy(parent["conditions"][base]) for name in names}
    conditions[names[1]]["contact_approach"] = "measured_handle"
    cases = [{**case, "condition": name, "name": case["name"].replace(base, name)}
             for case in parent["cases"] if case["condition"] == base for name in names]
    if len(cases) != 1200 or len({case["name"] for case in cases}) != 1200:
        raise ValueError("expected two registered six-class100-trial arms")
    plan = {**parent, "conditions": conditions,
            "parent_manifest": {"path": str(args.parent), "sha256": expected},
            "hypothesis": "An oversized pan body is not a grippable handle; compare current RGB-D measured-handle staging with bounds-centre staging.",
            "only_registered_delta": "frypan approach pose from existing SAM handle query and RGB-D,using normal-English frying pan alias already shared by both arms; max(measured handle z,object upper z)+10cm. Other classes retain centre staging.",
            "not_causal_from_smoke": "Same initial states,not paired policy noise. Ten pan-only trials check feasibility,not qualification.",
            "missing_geometry": "No unique measured handle means an unverified visible_handle_not_measured receipt,no invented pose.",
            "runtime_default_changed": False, "new_training_rows": 0,
            "method_count_note": "Measured grasp-affordance variant of the high approach family,not an additional completed100/class method.",
            "private_truth_is_only_post_trial_label": True}
    args.output.mkdir(parents=True, exist_ok=False)
    smoke = [case for case in cases if case["group"] == "frypan" and case["trial_index"] < 5]
    for kind, rows in (("smoke", smoke), ("full", cases)):
        path = args.output / (kind + ".json")
        path.write_text(json.dumps({**plan, "cohort": kind, "cases": rows}, indent=2) + "\n")
        print(json.dumps({"path": str(path), "trials": len(rows),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
