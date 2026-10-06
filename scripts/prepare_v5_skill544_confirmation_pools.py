"""Prepare method-free original-state pools from explicit pinned metadata."""

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
import re


ORIGINAL_SUITES = {"libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}
TYPES = ("drawer_open", "drawer_close", "microwave_open", "microwave_close",
         "stove_turn_on", "stove_turn_off", "place_on", "place_in")
SAFE_INIT = (*range(10, 40), *range(42, 50))
INVERSE = {"open": "close", "close": "open", "turn_on": "turn_off", "turn_off": "turn_on"}


def identity(path):
    path = Path(path).expanduser().resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_pinned(reference):
    if not Path(reference["path"]).is_absolute():
        raise ValueError("input references must be explicit absolute paths")
    actual = identity(reference["path"])
    if actual["sha256"] != reference["sha256"]:
        raise ValueError("registered input SHA changed: " + actual["path"])
    return json.loads(Path(actual["path"]).read_text()), actual


def task_objects(task):
    return {symbol: category.replace("_", " ") for category, symbols in task.get("objects", {}).items()
            for symbol in symbols}


def fixture_specs(task, label):
    """Enumerate only named parts of fixtures already present in the catalog."""
    fixture_kind, mode = label.split("_", 1)
    fixtures = {symbol for names in task.get("fixtures", {}).values() for symbol in names}
    regions = task.get("regions", {})
    specs = []
    if fixture_kind == "drawer":
        for parent in sorted(symbol for symbol in fixtures if "cabinet" in symbol):
            for part in ("top", "middle", "bottom"):
                symbol = f"{parent}_{part}_region"
                if symbol in regions and regions[symbol].get("target") == parent:
                    specs.append({"object_symbol": symbol, "object_category": f"cabinet {part} drawer",
                                  "fixture_parent": parent})
    else:
        for symbol in sorted(fixtures):
            if (fixture_kind == "microwave" and "microwave" in symbol
                    or fixture_kind == "stove" and "stove" in symbol):
                specs.append({"object_symbol": symbol, "object_category": fixture_kind,
                              "fixture_parent": symbol})
    predicate = {"turn_on": "turnon", "turn_off": "turnoff"}.get(mode, mode)
    original = {tuple(goal) for goal in task.get("oracle_goal_predicates", [])}
    for spec in specs:
        spec["requested_predicate"] = [predicate, spec["object_symbol"]]
        spec["original_goal_match"] = tuple(spec["requested_predicate"]) in original
        spec["setup"] = [{"tool": "articulate", "object_symbol": spec["object_symbol"],
                          "object_category": spec["object_category"], "mode": INVERSE[mode]}]
    return sorted(specs, key=lambda spec: (not spec["original_goal_match"], spec["object_symbol"]))


def place_specs(task, mode):
    """Keep actual original placement predicates; do not invent new regions."""
    objects = task_objects(task)
    fixtures = {symbol for names in task.get("fixtures", {}).values() for symbol in names}
    regions = task.get("regions", {})
    specs = []
    for goal in task.get("oracle_goal_predicates", []):
        if len(goal) != 3 or goal[0] != mode or goal[1] not in objects:
            continue
        source, target = goal[1:]
        if target not in objects and target not in fixtures and target not in regions:
            raise ValueError("original placement goal target is absent from catalog: " + target)
        region = regions.get(target)
        parent = region.get("target") if region else None
        target_category = objects.get(target)
        if parent and "cabinet" in parent:
            part = next((name for name in ("top", "middle", "bottom") if target == f"{parent}_{name}_region"), None)
            target_category = f"cabinet {part} drawer" if part else "cabinet top surface"
        elif parent and "microwave" in parent:
            target_category = "microwave"
        elif parent and "stove" in parent:
            target_category = "stove"
        elif parent in objects:
            target_category = objects[parent]
        setup = []
        if mode == "in" and parent and "cabinet" in parent:
            setup.append({"tool": "articulate", "object_symbol": target,
                          "object_category": target_category, "mode": "open"})
        elif mode == "in" and parent and "microwave" in parent:
            setup.append({"tool": "articulate", "object_symbol": parent,
                          "object_category": "microwave", "mode": "open"})
        setup.append({"tool": "grasp", "object_symbol": source, "object_category": objects[source],
                      "approach_method": None, "required_public_receipt": "grasp_verified"})
        specs.append({"object_symbol": source, "object_category": objects[source],
                      "target_symbol": target, "target_category": target_category,
                      "target_region_parent": parent, "requested_predicate": list(goal),
                      "original_goal_match": True, "setup": setup,
                      "public_region_binding_pending": target_category is None})
    return sorted(specs, key=lambda spec: tuple(spec["requested_predicate"]))


def exclusions(catalog, manifests, reserved_ranges):
    states = {(task["suite"], task["task"], seed): digest for task in catalog
              for seed, digest in enumerate(task["state_sha256"])}
    excluded, counts = defaultdict(list), []
    for reference, plan in manifests:
        hashes = set()
        for case in plan.get("cases", []):
            episode = case["episode"]
            key = episode["suite"], episode["task"], episode["seed"]
            if key not in states:
                raise ValueError("exclusion case is outside the original catalog")
            digest = states[key]
            if case.get("state_sha256") not in (None, digest):
                raise ValueError("exclusion case SHA differs from original catalog")
            hashes.add(digest)
        for digest in sorted(hashes):
            excluded[digest].append(reference["path"])
        counts.append({**reference, "cases": len(plan.get("cases", [])), "unique_state_sha256": len(hashes)})
    for scope in reserved_ranges:
        if scope["suite"] not in ORIGINAL_SUITES:
            raise ValueError("reserved range is outside original LIBERO")
        for (suite, task, seed), digest in states.items():
            if suite == scope["suite"] and task in scope["tasks"] and seed in scope["init_states"]:
                excluded[digest].append("explicit_public_reserved_range")
    return excluded, counts


def build_pools(catalog, excluded, target_per_type=100):
    seen_tasks = set()
    pools, audits = {}, {}
    for task in catalog:
        key = task["suite"], task["task"]
        if task["suite"] not in ORIGINAL_SUITES or key in seen_tasks:
            raise ValueError("catalog has a duplicate or non-original task")
        seen_tasks.add(key)
        if len(task["state_sha256"]) != task["trials"] or any(
                not re.fullmatch(r"[0-9a-f]{64}", digest) for digest in task["state_sha256"]):
            raise ValueError("catalog state SHA/trial count is invalid")
    for label in TYPES:
        is_place = label.startswith("place_")
        mode = label.split("_", 1)[1]
        rows, seen, counts = [], set(), Counter()
        for task in sorted(catalog, key=lambda task: (task["suite"], task["task"])):
            specs = place_specs(task, mode) if is_place else fixture_specs(task, label)
            if not specs:
                continue
            counts["metadata_applicable_tasks"] += 1
            for seed, digest in enumerate(task["state_sha256"]):
                if seed not in SAFE_INIT:
                    counts["reserved_seed_states_excluded"] += 1
                    continue
                if digest in excluded:
                    counts["known_old_access_or_reservation_states_excluded"] += 1
                    continue
                if digest in seen:
                    counts["duplicate_raw_states_not_counted"] += 1
                    continue
                seen.add(digest)
                # One spec per raw initial state; extra drawer parts/objects
                # never inflate the independent-state denominator.
                original_specs = [spec for spec in specs if spec["original_goal_match"]]
                options = original_specs or specs
                spec = copy.deepcopy(options[seed % len(options)])
                row = {"name": f"pool_{label}_{task['suite']}_t{task['task']}_s{seed}",
                       "episode": {"suite": task["suite"], "task": task["task"], "seed": seed},
                       "kind": "place" if is_place else "articulate", "type": label, "mode": mode,
                       "state_sha256": digest, "official_init_index": seed,
                       "state_hash_encoding": "C contiguous little endian float64",
                       "bddl": task["bddl"], "init_file": task["init_file"],
                       "original_instruction_sha256": task.get("language_sha256"),
                       "selected_method": None, "physical_applicability_verified": False,
                       "scope": "private original metadata and proposed setup; never runtime state geometry",
                       "binding_source": "actual_original_goal" if spec["original_goal_match"] else "actual_original_fixture_counterfactual",
                       **spec}
                rows.append(row)
        pools[label] = rows
        audits[label] = {"candidate_states": len(rows), "unique_raw_state_sha256": len(seen),
                        "target_per_type": target_per_type, "shortfall": max(0, target_per_type - len(rows)),
                        "original_goal_states": sum(row["original_goal_match"] for row in rows),
                        "counterfactual_fixture_states": sum(not row["original_goal_match"] for row in rows),
                        "per_suite": dict(Counter(row["episode"]["suite"] for row in rows)),
                        "per_task": dict(Counter(f"{row['episode']['suite']}/t{row['episode']['task']}" for row in rows)),
                        "counts": dict(counts)}
    return pools, audits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--index-sha256", required=True)
    parser.add_argument("--extra-exclusion", nargs=2, action="append", default=[], metavar=("PATH", "SHA256"))
    parser.add_argument("--target-per-type", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    index, index_file = read_pinned({"path": str(args.index), "sha256": args.index_sha256})
    catalog, catalog_file = read_pinned(index["catalog"])
    if len(catalog) != 130:
        raise ValueError("the registered original130 catalog is required")
    references = list(index["exclusion_manifests"])
    references += [{"path": path, "sha256": digest} for path, digest in args.extra_exclusion]
    deduped = {}
    for reference in references:
        path = reference["path"]
        if path in deduped and deduped[path] != reference:
            raise ValueError("same exclusion file has different registered identities")
        deduped[path] = reference
    manifests = []
    for reference in deduped.values():
        plan, actual = read_pinned(reference)
        manifests.append((actual, plan))
    excluded, exclusion_files = exclusions(catalog, manifests, index.get("public_reserved_ranges", []))
    pools, audits = build_pools(catalog, excluded, args.target_per_type)
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    policy = {"version": "skill544-method-free-confirmation-candidate-pool/1", "cohort": "candidate_pool",
              "pool_only": True, "not_reserved": True, "reservation_authorized": False,
              "training_exclusion_authorized": False,
              "qualification_authorized": False, "new_training_rows": 0, "new_physical_trials": 0,
              "method_binding_authorized": False, "selected_method": None,
              "safe_public_init_indices": list(SAFE_INIT), "excluded_seed_indices": [*range(10), 40, 41],
              "seed_selection": "all known eligible states; never select by outcomes; one spec per SHA/type",
              "reservation_policy": "this pool reserves no state and creates no training exclusion; after method selection, separately register 100 states/type; only actually registered or physically visited confirmation states are excluded from training",
              "setup_policy": "real measured skills only; fixture opposite endpoint before tested action; placement open container then grasp; preserve every setup failure and retain planned denominator; setup methods unbound",
              "truth_policy": "private requested predicate before/after and joint state are labels only; full-task solved() never substitutes for skill success; already-satisfied endpoints reported separately; no private-label gating",
              "runtime_policy": "actual binding, geometry and verification must use public RGB-D/proprioception; catalog BDDL symbols/SHA and predicates are diagnostic metadata only",
              "registry_scope": "excluded every case in the explicit known registry, regardless of visit/success; unpublished access registrations remain a reported gap"}
    pool_files = {}
    for label, rows in pools.items():
        path = output / f"{label}_pool.json"
        path.write_text(json.dumps({**policy, "type": label, "cases": rows}, indent=2) + "\n")
        pool_files[label] = identity(path)
    sets = {label: {row["state_sha256"] for row in rows} for label, rows in pools.items()}
    overlaps = {f"{left}/{right}": len(sets[left] & sets[right])
                for i, left in enumerate(TYPES) for right in TYPES[i + 1:] if sets[left] & sets[right]}
    gaps = list(index.get("unknown_exclusion_metadata", []))
    if not index.get("all_selection_confirmation_registry_complete", False):
        gaps.append("explicit known access registry is incomplete; unindexed visits are not assessed; no extra admission rule is imposed")
    if not index.get("sealed_range_metadata_complete", False):
        gaps.append("sealed range metadata remains incomplete; sealed payload not opened; public 0-9/40/41 excluded")
    gaps += ["candidate applicability and public unique binding are unmeasured; no qualifying physical outcomes",
             "setup recipes and the tested method remain unbound; actual setups may fail and must stay in the planned denominator"]
    report = {**policy, "index": index_file, "catalog": catalog_file, "exclusion_files": exclusion_files,
              "producer": identity(__file__), "excluded_unique_state_sha256": len(excluded),
              "by_type": audits, "pool_files": pool_files, "cross_type_shared_raw_states": overlaps,
              "global_unique_raw_state_sha256": len(set().union(*sets.values())),
              "known_exclusion_overlap_states": sum(len(values & excluded.keys()) for values in sets.values()),
              "all_types_have_target_candidate_count": all(audit["shortfall"] == 0 for audit in audits.values()),
              "gaps": gaps, "sealed_payload_opened": False, "PRO_payload_opened": False,
              "asset_payloads_reopened": False, "timing_reports_or_ledgers_reopened": False,
              "jobs_submitted": 0}
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": identity(report_path), "by_type": {key: {field: value[field] for field in (
        "candidate_states", "unique_raw_state_sha256", "shortfall", "counterfactual_fixture_states")}
        for key, value in audits.items()}, "new_physical_trials": 0, "qualification_authorized": False}, indent=2))


if __name__ == "__main__":
    main()
