"""Register moka reset/overhead/handle probes after the saved failure audit."""

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
    parent_sha = hashlib.sha256(args.parent.read_bytes()).hexdigest()
    if parent_sha != "9dca2edd661ccba0d6e69efb595c8951ba9eccb16c74584e48e1007adfb175d0":
        raise ValueError("original discovery cohort changed")
    parent = json.loads(args.parent.read_text())
    conditions = {
        "moka_reset_selected160": {**copy.deepcopy(parent["conditions"]["rpent_start_bound_full160"]),
                                  "contact_prompt_binding": "selected_only"},
        "moka_overhead_selected160": copy.deepcopy(parent["conditions"]["rpent_high10_short160"]),
        "moka_handle_selected160": {**copy.deepcopy(parent["conditions"]["rpent_high10_short160"]),
                                   "contact_approach": "measured_handle", "handle_categories": ["moka pot"]},
    }
    for condition in conditions.values():
        condition["contact_verification"] = "stable_lower_gripper_wrist"
    cases = [{**case, "condition": name, "name": case["name"].replace("rpent_high10_short160", name)}
             for case in parent["cases"]
             if case["group"] == "moka_pot" and case["condition"] == "rpent_high10_short160"
             for name in conditions]
    if len(cases) != 300 or len({c["name"] for c in cases}) != 300:
        raise ValueError("requires 100 registered original trials for each moka arm")
    plan = {**parent, "groups": ["moka_pot"], "conditions": conditions, "cases": cases,
            "purpose": "original-only moka discovery, no confirmation states or training",
            "parent_manifest": {"path": str(args.parent), "sha256": parent_sha},
            "audit_motivation": "Budget failures3/5/7 are secondary; reset/full often stops before whole-object clearance,overhead often has no target lift; full instruction released one held moka onto the stove.",
            "contact_prompt": "pick up the moka pot",
            "verifier": "Always trial-lift5cm,two fresh lower-rise>=3cm frames0.5s apart and measured gripper proximity; rejected main-view evidence gets a fresh wrist view,original rejected measurement retained.",
            "state_repetition": "50 official original LIBERO10 task2 states reset twice per arm;100 nominal first requests,not100 independent initial states.",
            "confirmation": "Reserved nonoverlapping original90 states untouched until the class recipe is fixed.",
            "runtime_default_changed": False, "new_training_rows": 0}
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / "full.json"
    path.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"path": str(path), "trials": len(cases),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
