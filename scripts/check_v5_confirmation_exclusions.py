"""Check permanent exclusion guards using explicit registered confirmation files."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from robots.libero.v5_confirmation_exclusions import (
    check_original_collection_episode,
    check_registered_training_layout,
    check_registered_training_original_state,
)


def reference(path):
    if not path.is_absolute():
        raise ValueError("explicit absolute registration path required")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def require_rejection(call, reason):
    try:
        call()
    except ValueError as error:
        if reason not in str(error):
            raise
    else:
        raise AssertionError("registered exclusion was not enforced")


def check(original_path, layout_path):
    original = json.loads(original_path.read_bytes())
    layouts = json.loads(layout_path.read_bytes())
    original_ref, layout_ref = reference(original_path), reference(layout_path)
    for record in original["records"]:
        state = {"episode": record["episode"], "state_sha256": record["state_sha256"]}
        require_rejection(
            lambda: check_registered_training_original_state(state, original_ref),
            "permanent original confirmation")
        episode = {**record["episode"], "init_state_sha256": record["state_sha256"],
                   "counterfactual_spec": "synthetic_changed_goal_only"}
        require_rejection(
            lambda: check_original_collection_episode(
                episode, {"confirmation_exclusions": {"original": original_ref}}),
            "permanent original confirmation")
    for index, record in enumerate(layouts["records"]):
        case = {key: copy.deepcopy(record[key]) for key in (
            "layout_seed", "layout_parameters", "state_sha256", "geometry_fingerprint",
            "settled_moka_xy_m")}
        require_rejection(lambda: check_registered_training_layout(case, layout_ref),
                          "separately registered range")
        # Metadata-only probe: distinct identity, identical settled XY. This is
        # not a generated simulator state or a training-admitted physical layout.
        case.update(layout_seed=680100 + index,
                    layout_parameters={"synthetic_guard_probe": index},
                    state_sha256="synthetic_state_" + str(index),
                    geometry_fingerprint="synthetic_geometry_" + str(index))
        require_rejection(lambda: check_registered_training_layout(case, layout_ref),
                          "less than 5 cm")
    return {"original_registry": original_ref, "layout_registry": layout_ref,
            "original_registered_identities_rejected": len(original["records"]),
            "changed_goal_attempts_rejected": len(original["records"]),
            "layout_registered_seeds_rejected": len(layouts["records"]),
            "new_seed_same_position_attempts_rejected": len(layouts["records"]),
            "minimum_moka_xy_distance_m": .05,
            "historical_coverage_complete": original.get("coverage_complete") is True,
            "synthetic_guard_inputs_only": True, "new_training_rows": 0,
            "new_physical_requests": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-registry", type=Path, required=True)
    parser.add_argument("--layout-registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.original_registry, args.layout_registry)
    result["checker_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["guard_sha256"] = hashlib.sha256(
        (Path(__file__).resolve().parents[1] / "robots/libero/v5_confirmation_exclusions.py").read_bytes()
    ).hexdigest()
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))
