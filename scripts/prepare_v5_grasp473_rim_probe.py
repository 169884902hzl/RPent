"""Register an isolated measured-rim comparison on the existing original cohort."""

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
    base_name = "rpent_high10_alias160"
    names = (base_name + "_centre_control", base_name + "_measured_rim")
    conditions = {name: copy.deepcopy(parent["conditions"][base_name]) for name in names}
    conditions[names[1]]["contact_approach"] = "measured_rim"
    cases = [{**case, "condition": name, "name": case["name"].replace(base_name, name)}
             for case in parent["cases"] if case["condition"] == base_name for name in names]
    if len(cases) != 1200 or len({case["name"] for case in cases}) != 1200:
        raise ValueError("expected two registered six-class100-trial arms")
    plan = {**parent, "conditions": conditions,
            "parent_manifest": {"path": str(args.parent), "sha256": expected},
            "hypothesis": "Hollow-container bounds-centre staging can enter the cavity; compare measured visible-rim xy at the identical10cm height.",
            "only_registered_delta": "bowl/mug/ramekin approach xy from current measured points; all other approach coordinates/prompt/budget/stop/verifier settings retained",
            "not_causal_from_smoke": "Random policy noise is not paired. Smoke only verifies instrumentation; full100/class required for qualification.",
            "runtime_default_changed": False, "new_training_rows": 0,
            "method_count_note": "A measured-geometry variant within the existing high/short approach family; not five completed distinct methods.",
            "private_truth_is_only_post_trial_label": True}
    args.output.mkdir(parents=True, exist_ok=False)
    for kind, selected in (("smoke", [c for c in cases if c["trial_index"] == 0]), ("full", cases)):
        path = args.output / (kind + ".json")
        path.write_text(json.dumps({**plan, "cohort": kind, "cases": selected}, indent=2) + "\n")
        print(json.dumps({"path": str(path), "trials": len(selected),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
