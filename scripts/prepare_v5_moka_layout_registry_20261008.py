"""Register original moka state availability and 24 unmaterialized layouts.

Read only explicitly pinned metadata and manifests. No outcomes, environment,
physics, PRO payload, runtime code, or confirmation trial is opened or run.
"""

import argparse
from collections import Counter
import copy
import hashlib
import itertools
import json
from pathlib import Path


ORIGINAL40 = ("libero_spatial", "libero_object", "libero_goal", "libero_10")
STATE_ENCODING = "C contiguous little endian float64"
RULE_VERSION = "moka-original-layout-preregistration/1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_pinned(reference):
    if not Path(reference["path"]).is_absolute():
        raise ValueError("Explicit absolute input paths are required")
    actual = identity(reference["path"])
    if actual["sha256"] != reference["sha256"]:
        raise ValueError("Pinned metadata changed: " + actual["path"])
    return json.loads(Path(actual["path"]).read_text()), actual


def state_hashes(plan):
    hashes = set()
    for case in plan.get("cases", []):
        episode = case["episode"]
        if episode["suite"] not in (*ORIGINAL40, "libero_90"):
            raise ValueError("Exclusion manifests must contain original episodes only")
        value = case.get("state_sha256")
        if not value:
            raise ValueError("Explicit exclusion case is missing its raw-state hash")
        hashes.add(value)
    return hashes


def build_layout_rules(bases):
    rules = []
    # The whole Cartesian grid is registered before seeing any trial result.
    # Equal grid cells are not claimed to be independent physical states.
    offsets = itertools.product((-0.015, -0.005, 0.005, 0.015),
                                (-0.015, 0.0, 0.015), (-10.0, 10.0))
    for index, (dx, dy, yaw) in enumerate(offsets):
        base = bases[index]
        rule = {
            "version": RULE_VERSION,
            "layout_seed": 580100 + index,
            "original_scene": {"suite": "libero_90", "task": 19},
            "moved_object_symbol": "moka_pot_1",
            "transform": {"world_xy_translation_m": [dx, dy],
                          "world_z_translation_m": 0.0, "world_yaw_delta_deg": yaw},
            "unchanged": ["original_BDDL_goal", "instruction", "furniture",
                          "target_region", "all_other_objects", "robot_initial_qpos"],
            "selection_rule": "all 24 fixed grid cells in lexical product order; no outcome filtering",
            "private_metadata_use": "original-scene layout generation only; never policy/ROI/stop",
        }
        rules.append({
            "name": f"moka_layout_{580100 + index}", "rule": rule,
            "rule_sha256": digest(rule), "base_official_state": copy.deepcopy(base),
            "base_used": True,
            "state_sha256": None, "registered_layout_state": None,
            "status": "not_ready_pending_rawstate_materialization_and_physical_stabilization",
            "official_initial_state": False, "independent_physical_state_verified": False,
            "excluded_from_training": True, "confirmation_run_authorized": False,
        })
    return rules


def register(visited_ref, task_sources_ref, training_catalog_ref, extra_exclusions=()):
    visited, visited_identity = read_pinned(visited_ref)
    selection, selection_identity = read_pinned(visited["selection"]["parent_selection"])
    pools, pool_identity = read_pinned(selection["access_pool"])
    task_sources, task_sources_identity = read_pinned(task_sources_ref)
    training_catalog, training_catalog_identity = read_pinned(training_catalog_ref)
    if len(training_catalog) != 40 or {row["suite"] for row in training_catalog} != set(ORIGINAL40):
        raise ValueError("The explicit original40 training catalog is required")
    training_hashes = {row["state_sha256"][seed] for row in training_catalog
                       for seed in range(10, 40)}
    source_tasks = {row["task"]: row for row in task_sources
                    if row["suite"] == "libero_90" and row["task"] in (18, 19, 20, 21)}
    if len(source_tasks) != 4:
        raise ValueError("All four original90 source-task descriptions are required")
    pool = pools["moka_pot"]
    if len(pool) != 200 or any(c["episode"]["suite"] != "libero_90" or
                              c["episode"]["task"] not in (18, 19, 20, 21) for c in pool):
        raise ValueError("Expected the explicit four original90 moka scenes")
    if len({c["state_sha256"] for c in pool}) != len(pool):
        raise ValueError("The original pool contains duplicate raw-state hashes")
    selection_hashes = state_hashes(selection)
    # All registered/visited states are excluded independently of their result.
    excluded = {c["state_sha256"] for c in pool if c["visited"] or
                c["reserved_by_explicit_prior_plan"]} | selection_hashes | state_hashes(visited)
    excluded |= training_hashes
    reasons = {c["state_sha256"]: [] for c in pool}
    for case in pool:
        if case["visited"]:
            reasons[case["state_sha256"]].append("pool_records_prior_visit")
        if case["reserved_by_explicit_prior_plan"]:
            reasons[case["state_sha256"]].append("pool_records_prior_reservation")
        if case["state_sha256"] in selection_hashes:
            reasons[case["state_sha256"]].append(selection_identity["path"])
        if case["state_sha256"] in training_hashes:
            reasons[case["state_sha256"]].append(training_catalog_identity["path"])
    references = [*selection["explicit_state_exclusions"], *extra_exclusions]
    deduped = {}
    for ref in references:
        if ref["path"] in deduped and deduped[ref["path"]] != ref:
            raise ValueError("One exclusion path was pinned with two identities")
        deduped[ref["path"]] = ref
    exclusion_audit = []
    pool_hashes = set(reasons)
    for ref in deduped.values():
        plan, actual = read_pinned(ref)
        hashes = state_hashes(plan)
        overlap = hashes & pool_hashes
        excluded |= hashes
        for value in overlap:
            reasons[value].append(actual["path"])
        exclusion_audit.append({**actual, "registered_cases": len(plan.get("cases", [])),
                                "registered_raw_states": len(hashes),
                                "moka_pool_overlap": len(overlap)})
    rows = []
    for case in pool:
        row = copy.deepcopy(case)
        # Only original40 init10-39 are the authorized collection range.
        ep = case["episode"]
        training_overlap = ep["suite"] in ORIGINAL40 and 10 <= ep["seed"] <= 39
        if training_overlap:
            excluded.add(case["state_sha256"])
            reasons[case["state_sha256"]].append("original40_training_init10_39")
        task = source_tasks[ep["task"]]
        if task["bddl"]["sha256"] != case["bddl"]["sha256"] or task["instruction"] != case["original_instruction"]:
            raise ValueError("Original task goal/instruction metadata differs from the pool")
        moka_goal = ["on", "moka_pot_1", "flat_stove_1_cook_region"]
        row.update(exclusion_reasons=reasons[case["state_sha256"]],
                   available_by_explicit_known_registry=case["state_sha256"] not in excluded,
                   training_range_overlap=training_overlap,
                   original_goal_is_moka_transfer=moka_goal in task["oracle_goal_predicates"],
                   physical_readiness_verified=False, confirmation_run_authorized=False)
        rows.append(row)
    available = [row for row in rows if row["available_by_explicit_known_registry"]]
    compatible = [row for row in available if row["original_goal_is_moka_transfer"]]
    bases = sorted((c for c in rows if c["episode"]["task"] == 19),
                   key=lambda c: c["episode"]["seed"])[:24]
    if len(bases) != 24 or any(c["available_by_explicit_known_registry"] for c in bases):
        raise ValueError("Expected the 24 explicitly known used official task19 generation bases")
    layout_rules = build_layout_rules(bases)
    return {
        "version": RULE_VERSION, "analysis_role": "CPU_registration_only",
        "inputs": {"visited_manifest": visited_identity, "selection_manifest": selection_identity,
                   "official_pool": pool_identity},
        "original_task_source_metadata": task_sources_identity,
        "training_catalog": training_catalog_identity,
        "training_raw_state_sha256": sorted(training_hashes),
        "original_task_goal_evidence": [{key: task[key] for key in (
            "suite", "task", "instruction", "instruction_sha256", "bddl", "oracle_goal_predicates")}
            for task in source_tasks.values()],
        "exclusion_manifests": exclusion_audit, "official_state_audit": rows,
        "available_official_states": available, "layout_rules": layout_rules,
        "counts": {"requested_official": 76, "official_pool": len(pool),
                   "available_after_all_explicit_exclusions": len(available),
                   "original_moka_goal_compatible_available": len(compatible),
                   "official_requested_shortfall": max(0, 76 - len(available)),
                   "available_by_task": dict(Counter(str(c["episode"]["task"]) for c in available)),
                   "layout_rules_registered": len(layout_rules), "layout_rawstates_materialized": 0,
                   "confirmed_independent_layout_states": 0,
                   "training_range_overlap": sum(c["training_range_overlap"] for c in rows)},
        "policy": {"original_goal_changed": False, "outcome_files_read": False,
                   "PRO_payload_read": False, "sealed_payload_read": False,
                   "artifact_directory_enumeration": False, "jobs_submitted": 0,
                   "physics_executed": 0, "new_training_rows": 0,
                   "confirmation_run_authorized": False,
                   "training_ranges": {"suites": list(ORIGINAL40), "init_states": list(range(10, 40))},
                   "registry_completeness": "explicit ancestor registry only; unindexed later access remains a gap",
                   "layout_identity": "rule_sha256 identifies declarations, never rawstate or physical independence",
                   "base_policy": "task19 official seed0-23, in source identity order, are used generation bases only; no base is counted as a fresh confirmation trial",
                   "correlation": "generated layouts share original task/assets with used base states; distinct hashes alone do not prove IID sampling"},
        "stabilization_estimate": {
            "required_before_running": True,
            "proposed_controls_per_layout": 50, "total_proposed_controls": 1200,
            "model_or_SAM_needed": False, "GPU_needed": False,
            "estimated_wall_minutes": [5, 15], "measured_estimate": False,
            "before_after_checks": ["only registered free-joint xy/yaw modified before settle",
                                    "furniture and BDDL SHA unchanged", "finite settled state",
                                    "moka resting on its original support without penetrating geometry",
                                    "rawstate SHA differs from all registered prior/training states",
                                    "all 24 attempted, no success-based replacement"],
        },
        "remaining_gaps": [
            "The stated 76-state cohort was not found in the explicit reference chain.",
            "Other available moka-containing scenes have original goals for pan/stove; they cannot be substituted for original moka transfer.",
            "All task19 official states are excluded by known selection or confirmation references.",
            "The 24 declarations have used official generation bases, but no materialized or stabilized rawstate and are not runnable confirmation cases.",
            "No physical skill qualification or statistical independence has been established.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--visited-manifest", type=Path, required=True)
    parser.add_argument("--visited-manifest-sha256", required=True)
    parser.add_argument("--task-sources", type=Path, required=True)
    parser.add_argument("--task-sources-sha256", required=True)
    parser.add_argument("--training-catalog", type=Path, required=True)
    parser.add_argument("--training-catalog-sha256", required=True)
    parser.add_argument("--extra-exclusion", nargs=2, action="append", default=[], metavar=("PATH", "SHA256"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = register({"path": str(args.visited_manifest), "sha256": args.visited_manifest_sha256},
                      {"path": str(args.task_sources), "sha256": args.task_sources_sha256},
                      {"path": str(args.training_catalog), "sha256": args.training_catalog_sha256},
                      [{"path": path, "sha256": sha} for path, sha in args.extra_exclusion])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report["producer"] = identity(__file__)
    report["actual_arguments"] = {
        "visited_manifest": str(args.visited_manifest),
        "visited_manifest_sha256": args.visited_manifest_sha256,
        "task_sources": str(args.task_sources), "task_sources_sha256": args.task_sources_sha256,
        "training_catalog": str(args.training_catalog),
        "training_catalog_sha256": args.training_catalog_sha256,
        "extra_exclusions": args.extra_exclusion, "output": str(output),
    }
    references = {}
    for name, value in (("official_state_audit.json", report["official_state_audit"]),
                        ("available_official_states.json", report["available_official_states"]),
                        ("layout_rules24.json", report["layout_rules"]),
                        ("manifest.json", report)):
        path = output / name
        path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        references[name] = identity(path)
    handoff = {"counts": report["counts"], "files": references,
               "status": "not_ready", "qualification": False,
               "remaining_gaps": report["remaining_gaps"], "jobs_submitted": 0}
    (output / "handoff.json").write_text(json.dumps(handoff, indent=2) + "\n")
    print(json.dumps(handoff, indent=2))


if __name__ == "__main__":
    main()
