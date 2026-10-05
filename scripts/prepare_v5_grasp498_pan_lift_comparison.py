"""Register an original pan trial-lift comparison without consuming holdouts."""

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
    digest = hashlib.sha256(args.parent.read_bytes()).hexdigest()
    if digest != "7f53e64c71ab6c74309424e6ec2a819c57495417c1c9c92bd1b861dac63eee1c":
        raise ValueError("registered pan discovery cohort changed")
    parent = json.loads(args.parent.read_text())
    conditions = {}
    for name, distance in (("pan_lift5_control160", .05), ("pan_lift10_selected160", .10)):
        condition = copy.deepcopy(parent["conditions"]["original_pan_name160"])
        condition.update(trial_lift_m=distance, private_phase_snapshots=True)
        conditions[name] = condition
    cases = []
    for case in parent["cases"]:
        if case["condition"] != "original_pan_name160":
            continue
        for name in conditions:
            cases.append({**case, "condition": name,
                          "name": case["name"].replace("original_pan_name160", name)})
    if len(cases) != 200 or len({case["name"] for case in cases}) != 200:
        raise ValueError("requires two registered100-trial original discovery arms")
    plan = {**parent, "conditions": conditions, "cases": cases,
            "purpose": "original-only pan trial-lift exploration, not confirmation or training",
            "parent_manifest": {"path": str(args.parent), "sha256": digest},
            "hypothesis": "Four of seven centre failures in the fixed first50 have finger support but insufficient whole-object clearance; compare5cm and10cm lifts without changing the3cm truth threshold.",
            "allowed_change": "Trial-lift distance only; both arms record identical read-only private phase snapshots, never supplied to control or state text.",
            "state_repetition": "50 official original LIBERO10 task2 states reset twice per arm; nominal100 requests, not100 unique initial states.",
            "qualification": "Exploration never awards qualification; all preselected nonoverlapping confirmation states remain untouched.",
            "runtime_default_changed": False, "new_training_rows": 0}
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / "full.json"
    path.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"path": str(path), "trials": len(cases),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
