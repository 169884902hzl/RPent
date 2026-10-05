"""Register original-scene pan prompt, handle and budget discovery arms."""

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
        raise ValueError("registered discovery parent changed")
    parent = json.loads(args.parent.read_text())
    base = "rpent_high10_alias160"
    arms = {
        "original_pan_name160": {},
        "original_pan_handle160": {"contact_approach": "measured_handle"},
        "original_pan_name320": {"max_chunks": 320},
        "original_pan_handle320": {"contact_approach": "measured_handle", "max_chunks": 320},
    }
    conditions = {}
    for name, changes in arms.items():
        conditions[name] = {**copy.deepcopy(parent["conditions"][base]),
                            "contact_verification": "stable_lower_gripper", **changes}
    cases = [
        {**case, "condition": name, "name": case["name"].replace(base, name)}
        for case in parent["cases"] if case["condition"] == base and case["group"] == "frypan"
        for name in arms
    ]
    if len(cases) != 400 or len({c["name"] for c in cases}) != 400:
        raise ValueError("requires 100 registered first-trial cases in each of four arms")
    plan = {**parent, "groups": ["frypan"], "conditions": conditions, "cases": cases,
            "parent_manifest": {"path": str(args.parent), "sha256": parent_sha},
            "purpose": "original-only pan discovery; never a held-out confirmation or training set",
            "hypotheses": ["Use the original LIBERO noun phrase frying pan in a grasp-only prompt.",
                           "Stage over a currently measured handle rather than the body centre.",
                           "Compare160/320 action chunks without changing the public pick stop.",
                           "Always trial-lift5cm,require two fresh lower-rise frames0.5s apart and measured gripper proximity."],
            "prompt": "pick up the frying pan",
            "prompt_source": "Original LIBERO-90 task18/21/40/41/42/45 language uses frying pan; no PRO prompt or memory.",
            "verifier": {"version": "trial_lift_lower_two_frames_gripper/2", "minimum_lower_rise_m": .03,
                         "trial_lift_m": .05, "hold_steps": 10, "gripper_xy_margin_m": .04,
                         "tcp_to_fingers_m": .15, "inputs": "RGB-D and public proprioception only"},
            "repeated_state_disclosure": "50 original task2 official initial states reset twice per arm;100 nominal first trials.",
            "confirmation": "None of these states or scores determines qualification; use independently registered nonoverlapping original initial states after choosing the recipe.",
            "runtime_default_changed": False, "new_training_rows": 0}
    args.output.mkdir(parents=True, exist_ok=False)
    for kind, rows in (("full", cases), ("smoke", [c for c in cases if c["trial_index"] == 0])):
        path = args.output / (kind + ".json")
        path.write_text(json.dumps({**plan, "cohort": kind, "cases": rows}, indent=2) + "\n")
        print(json.dumps({"path": str(path), "trials": len(rows),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
