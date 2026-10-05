"""Prepare pan/moka confirmation only after an explicit recipe is fixed.

The discovery and pool identities match prepare_v5_grasp492_confirmation.
This entry point never reads report metrics or chooses a winning condition.
Its output is a qualification diagnostic, never a training manifest.
"""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re

from scripts.prepare_v5_grasp487_original_pool import SOURCE_SHA, file_record


POOL_SHA = "89ea5ea7ee50e1cf7dc9eeafcdb925b299cc6cab541090e2b174bbad98fd8f64"
RECIPE_SCHEMA = "original-grasp-frozen-class-recipe/1"
REMAINING_GROUPS = {"frypan", "moka_pot"}
DISCOVERY_SUITES = {"libero_spatial", "libero_object", "libero_goal", "libero_10"}
STATE_ENCODING = "C contiguous little endian float64"


def load_pinned_json(path, expected_sha):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise ValueError("explicit lowercase SHA256 required")
    actual = file_record(path)
    if actual["sha256"] != expected_sha:
        raise ValueError(f"registered file changed: {path}")
    return json.loads(path.read_text()), actual


def validate_recipe(recipe, group):
    """Validate an opaque, explicitly selected recipe without inspecting scores."""
    if (group not in REMAINING_GROUPS or recipe.get("group") != group
            or recipe.get("schema") != RECIPE_SCHEMA or recipe.get("frozen") is not True):
        raise ValueError("explicit frozen pan/moka recipe with the registered schema required")
    if not re.fullmatch(r"[A-Za-z0-9_]+", recipe.get("name", "")):
        raise ValueError("explicit recipe name required")
    condition = recipe.get("condition", {})
    if (condition.get("profile") not in {"current", "start_full", "high_short"}
            or condition.get("mode") not in {"direct", "above_10cm", "yaw_90"}
            or type(condition.get("max_chunks")) is not int or condition["max_chunks"] <= 0
            or not isinstance(condition.get("overrides"), dict)):
        raise ValueError("recipe must contain one complete probe condition")
    overrides = condition["overrides"]
    if (overrides.get("done_gated") or overrides.get("collection") is not None
            or overrides.get("counterfactual_spec") is not None
            or overrides.get("libero_type", "standard") != "standard"):
        raise ValueError("confirmation recipe cannot enable training or non-original assets")
    evidence = recipe.get("exploration_reports")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("explicit exploration report paths and SHA256 required")
    for report in evidence:
        if (not isinstance(report, dict) or not report.get("path")
                or not re.fullmatch(r"[0-9a-f]{64}", report.get("sha256", ""))):
            raise ValueError("explicit exploration report paths and SHA256 required")
    return copy.deepcopy(condition)


def build_confirmation(parent, pool, recipe, *, group, state_sha_for, verify_case_assets):
    """Verify reserved states before constructing a single fixed-condition plan.

    ``state_sha_for`` decodes the current official state using the same
    canonical encoding as the runtime probe. No row is replaced when an
    exclusion, state identity, or asset verification fails.
    """
    condition = validate_recipe(recipe, group)
    old_tuples = {(r["episode"]["suite"], r["episode"]["task"], r["episode"]["seed"])
                  for r in parent["cases"]}
    if {s for s, _, _ in old_tuples} - DISCOVERY_SUITES:
        raise ValueError("discovery must contain only the fixed original40 tasks")
    old_hashes = {state_sha_for(s, t, i) for s, t, i in sorted(old_tuples)}
    reserved = [r for r in pool["cases"] if r["group"] == group]
    if len(reserved) != 100:
        raise ValueError("confirmation requires exactly100 preselected states in this class")
    seen_tuples, seen_hashes, cases = set(), set(), []
    condition_name = "confirm_" + group
    for index, row in enumerate(reserved):
        ep = row["episode"]
        key = (ep["suite"], ep["task"], ep["seed"])
        if (ep["suite"] != "libero_90" or not 0 <= ep["task"] < 90
                or type(ep["seed"]) is not int or not 10 <= ep["seed"] < 40
                or row.get("official_init_index") != ep["seed"]
                or row.get("state_hash_encoding") != STATE_ENCODING
                or row.get("source") != "official_original_LIBERO90"):
            raise ValueError("remaining confirmation uses registered official original90 init10-39")
        if key in old_tuples or key in seen_tuples:
            raise ValueError("confirmation tuple overlaps discovery or repeats")
        verify_case_assets(row)
        digest = state_sha_for(*key)
        if digest != row.get("state_sha256"):
            raise ValueError("registered original confirmation state changed")
        if digest in old_hashes or digest in seen_hashes:
            raise ValueError("confirmation raw state overlaps discovery or repeats")
        seen_tuples.add(key)
        seen_hashes.add(digest)
        cases.append({**row, "condition": condition_name, "trial_index": index,
                      "initial_state_repetition": 0,
                      "name": f'{group}_{ep["suite"]}_t{ep["task"]}_s{ep["seed"]}_{recipe["name"]}_confirmation'})
    return {**parent, "groups": [group], "conditions": {condition_name: condition}, "cases": cases,
            "cohort": "independent_confirmation_remaining_class",
            "purpose": "preselected original-state qualification diagnostic only; no training or PRO data",
            "frozen_class_recipes": {group: recipe["name"]},
            "recipe_selection": "Explicit recipe JSON only; report contents are opaque hashes, never used to select a condition",
            "qualification": "No qualification awarded by preparation or the legacy summarizer. Only the complete six-class independent confirmation determines95/90/95; failed states are retained and never replaced.",
            "distribution": "Explicit extension to original LIBERO90 official init10-39; not a new original40 state cohort",
            "confirmation_audit": {"selected": 100, "unique_scene_tuples": len(seen_tuples),
                                   "unique_raw_state_hashes": len(seen_hashes),
                                   "discovery_unique_scene_tuples": len(old_tuples),
                                   "discovery_unique_raw_state_hashes": len(old_hashes),
                                   "tuple_overlap": 0, "raw_state_hash_overlap": 0,
                                   "state_hash_encoding": STATE_ENCODING},
            "original90_grasp_diagnostic_v1": True,
            "runtime_default_changed": False, "new_training_rows": 0}


def make_official_state_validator(pool):
    """Load only explicitly named original tasks using the registered config."""
    config = pool["config"]
    config_path = Path(config["path"])
    if file_record(config_path)["sha256"] != config["sha256"]:
        raise ValueError("registered runtime asset config changed")
    os.environ["LIBERO_TYPE"] = "standard"
    os.environ["LIBERO_CONFIG_PATH"] = str(config_path.parent)
    import numpy as np
    from libero.libero import get_libero_path
    from rlinf.envs.libero.utils import benchmark

    if benchmark.__name__ != pool["benchmark_python_namespace"]:
        raise ValueError("registered original benchmark backend changed")
    roots = {k: Path(get_libero_path(k)).absolute() for k in ("bddl_files", "init_states", "assets")}
    if {k: str(v) for k, v in roots.items()} != pool["asset_roots"]:
        raise ValueError("registered original asset roots changed")
    allowed = DISCOVERY_SUITES | {"libero_90"}
    suites, arrays = {}, {}

    def task(suite, task_id):
        if suite not in allowed:
            raise ValueError("non-original task is not a confirmation input")
        if suite not in suites:
            suites[suite] = benchmark.get_benchmark(suite)()
        result = suites[suite].get_task(task_id)
        if result.problem_folder != suite:
            raise ValueError("original task folder differs from explicit suite")
        return result

    def state_sha_for(suite, task_id, init_id):
        task(suite, task_id)
        if (suite, task_id) not in arrays:
            arrays[suite, task_id] = np.asarray(suites[suite].get_task_init_states(task_id))
        state = arrays[suite, task_id][init_id]
        return hashlib.sha256(np.asarray(state, dtype="<f8", order="C").tobytes()).hexdigest()

    def verify_case_assets(row):
        ep = row["episode"]
        original = task(ep["suite"], ep["task"])
        paths = {"bddl": roots["bddl_files"] / original.problem_folder / original.bddl_file,
                 "init_file": roots["init_states"] / original.problem_folder / original.init_states_file}
        for key, path in paths.items():
            descriptor = row[key]
            if (path.resolve() != Path(descriptor["path"]).resolve()
                    or file_record(path)["sha256"] != descriptor["sha256"]):
                raise ValueError("registered original confirmation asset changed")
    return state_sha_for, verify_case_assets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--group", choices=sorted(REMAINING_GROUPS), required=True)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--recipe-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("confirmation output must be a new directory")
    parent, parent_record = load_pinned_json(args.parent, SOURCE_SHA)
    pool, pool_record = load_pinned_json(args.pool, POOL_SHA)
    recipe, recipe_record = load_pinned_json(args.recipe, args.recipe_sha256)
    validate_recipe(recipe, args.group)
    # Read explicit bytes for identity only. Report metrics never enter selection.
    for report in recipe["exploration_reports"]:
        if file_record(Path(report["path"]))["sha256"] != report["sha256"]:
            raise ValueError("registered exploration report changed")
    if pool["source_manifest"]["sha256"] != parent_record["sha256"]:
        raise ValueError("pool does not exclude this discovery manifest")
    state_sha_for, verify_case_assets = make_official_state_validator(pool)
    plan = build_confirmation(parent, pool, recipe, group=args.group,
                              state_sha_for=state_sha_for, verify_case_assets=verify_case_assets)
    plan.update(pool_manifest=pool_record, discovery_manifest=parent_record,
                frozen_recipe=recipe_record, exploration_reports=copy.deepcopy(recipe["exploration_reports"]))
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / "full.json"
    path.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"path": str(path), "trials": len(plan["cases"]),
                      "sha256": file_record(path)["sha256"]}))


if __name__ == "__main__":
    main()
