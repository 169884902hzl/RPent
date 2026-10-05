"""Register reset-pose full/selected-only prompts on explicit original scenes."""

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
    base = "rpent_start_bound_full160"
    control, selected = base + "_control", "rpent_start_selected_short160"
    conditions = {name: copy.deepcopy(parent["conditions"][base]) for name in (control, selected)}
    conditions[selected]["contact_prompt_binding"] = "selected_only"
    # Keep identical spelling across the paired arms: this experiment changes
    # task clauses, not object aliases, stop rules or measured verification.
    cases = [{**case, "condition": name, "name": case["name"].replace(base, name)}
             for case in parent["cases"] if case["condition"] == base for name in (control, selected)]
    if len(cases) != 1200 or len({case["name"] for case in cases}) != 1200:
        raise ValueError("expected two registered six-class100-trial arms")
    plan = {**parent, "conditions": conditions,
            "parent_manifest": {"path": str(args.parent), "sha256": expected},
            "hypothesis": "Full multi-object task clauses can override the selected-object prefix in Pi0.5; test reset-pose selected-only prompt.",
            "only_registered_delta": "Remove other objects, placement goals and task clauses from the low-level prompt; keep reset pose, measured category spelling,160 chunks,public pick stop and single-frame verifier.",
            "not_causal_from_smoke": "Policy noise is not paired. Smoke verifies instrumentation,not qualification.",
            "runtime_default_changed": False, "new_training_rows": 0,
            "method_count_note": "Combination within the reset-pose/contact-prompt family; not an additional completed physical method.",
            "private_truth_is_only_post_trial_label": True}
    args.output.mkdir(parents=True, exist_ok=False)
    for kind, rows in (("smoke", [case for case in cases if case["trial_index"] == 0]), ("full", cases)):
        path = args.output / (kind + ".json")
        path.write_text(json.dumps({**plan, "cohort": kind, "cases": rows}, indent=2) + "\n")
        print(json.dumps({"path": str(path), "trials": len(rows),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
