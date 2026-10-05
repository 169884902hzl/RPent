"""Freeze class recipes before evaluating preselected unseen original states."""

import argparse
import copy
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent_sha = hashlib.sha256(args.parent.read_bytes()).hexdigest()
    pool_sha = hashlib.sha256(args.pool.read_bytes()).hexdigest()
    if parent_sha != "9dca2edd661ccba0d6e69efb595c8951ba9eccb16c74584e48e1007adfb175d0":
        raise ValueError("fixed discovery cohort changed")
    if pool_sha != "89ea5ea7ee50e1cf7dc9eeafcdb925b299cc6cab541090e2b174bbad98fd8f64":
        raise ValueError("preselected confirmation pool changed")
    parent = json.loads(args.parent.read_text())
    pool = json.loads(args.pool.read_text())
    recipes = {"bottle": "rpent_start_bound_full160", "bowl": "rpent_start_bound_full160",
               "box": "rpent_high10_short160", "mug": "rpent_high10_short160"}
    # Pan and moka recipes are still being developed. Their reserved states
    # are not consumed by this fixed four-class confirmation.
    conditions = {f"confirm_{group}": copy.deepcopy(parent["conditions"][name])
                  for group, name in recipes.items()}
    cases = []
    for index in range(100):
        for group in recipes:
            candidates = [c for c in pool["cases"] if c["group"] == group]
            selected = candidates[index]
            cases.append({**selected, "condition": "confirm_" + group, "trial_index": index,
                          "initial_state_repetition": 0})
    if len(cases) != 400 or any(len({c["state_sha256"] for c in cases if c["group"] == g}) != 100
                                for g in recipes):
        raise ValueError("require 100 unique preselected official states in each fixed class")
    plan = {**parent, "groups": list(recipes), "conditions": conditions, "cases": cases,
            "cohort": "independent_confirmation_first_four_classes",
            "purpose": "preselected original-state confirmation only, no training or PRO data",
            "pool_manifest": {"path": str(args.pool), "sha256": pool_sha},
            "discovery_manifest": {"path": str(args.parent), "sha256": parent_sha},
            "frozen_class_recipes": recipes,
            "qualification": "Only the full six-class independent confirmation determines95/90/95; no discovery scores or replacement of failed confirmation states.",
            "distribution": "bottle/bowl/box original40; mug explicitly extends to original LIBERO90, init10-39. All official state hashes exclude3550.",
            "original90_grasp_diagnostic_v1": True,
            "runtime_default_changed": False, "new_training_rows": 0}
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / "full.json"
    path.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"path": str(path), "trials": len(cases),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
