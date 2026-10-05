"""Register a public-proprioception stop comparison from an explicit cohort."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original = json.loads(args.manifest.read_text())
    assert original["truth_protocol"]["minimum_first_trials_per_class"] == 100
    cases = []
    for case in original["cases"]:
        if case["condition"] == "high_short160":
            cases.append({**case, "condition": "rpent_high_short160",
                          "name": case["name"].replace("_high_short160_", "_rpent_high_short160_")})
    if len(cases) != 600 or len({c["name"] for c in cases}) != 600:
        raise ValueError("expected the explicit six-class100-trial cohort")
    condition = {**original["conditions"]["high_short160"], "contact_stop": "rpent_pick"}
    plan = {**original, "conditions": {"rpent_high_short160": condition}, "cases": cases,
            "parent_manifest": {"path": str(args.manifest), "sha256": sha(args.manifest)},
            "hypothesis": "Public descent/ascent stop avoids continuing contact execution after visually missed lifts; private truth is never a stop condition.",
            "method_identity": "measured overhead approach + short object prompt + original RPent pi0_pick descent/ascent/gripper stop + unchanged final visual verification",
            "new_training_rows": 0}
    args.output.mkdir(parents=True, exist_ok=False)
    for kind, selected in (("full", cases), ("smoke", [c for c in cases if c["trial_index"] == 0])):
        path = args.output / (kind + ".json")
        path.write_text(json.dumps({**plan, "cohort": kind, "cases": selected}, indent=2) + "\n")
        print(json.dumps({"path": str(path), "sha256": sha(path), "trials": len(selected)}))


if __name__ == "__main__":
    main()
