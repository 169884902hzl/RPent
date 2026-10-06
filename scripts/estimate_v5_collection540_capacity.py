"""CPU-only capacity estimate from explicitly pinned original catalogs/ledgers.

This report registers no training rows, physics visits, or confirmation trials.
Incomplete exclusion metadata is reported rather than assumed empty.
"""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics

LABELS = ("drawer_open", "drawer_close", "microwave_open", "microwave_close",
          "stove_turn_on", "stove_turn_off")
ORIGINAL_SUITES = {"libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}


def file_identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def private_goal_labels(task):
    labels = set()
    for goal in task.get("oracle_goal_predicates", []):
        if len(goal) < 2:
            continue
        mode = {"turnon": "turn_on", "turnoff": "turn_off"}.get(goal[0], goal[0])
        symbol = goal[1]
        kind = ("microwave" if "microwave" in symbol else
                "drawer" if "cabinet" in symbol or "drawer" in symbol else
                "stove" if "stove" in symbol else None)
        label = f"{kind}_{mode}"
        if label in LABELS:
            labels.add(label)
    return labels


def fixture_labels(task):
    names = [name for values in task.get("fixtures", {}).values() for name in values]
    kinds = {"microwave" if "microwave" in name else "drawer" if "cabinet" in name else
             "stove" if "stove" in name else None for name in names}
    return {label for label in LABELS if label.split("_", 1)[0] in kinds}


def timing_summary(values):
    values = sorted(values)
    if not values:
        return {"n": 0}
    p90 = values[min(len(values) - 1, int(.9 * len(values)))]
    return {"n": len(values), "sum_s": sum(values), "mean_s": statistics.mean(values),
            "median_s": statistics.median(values), "p90_s": p90, "max_s": max(values)}


def estimate(index):
    sources = []

    def read(ref, label, jsonl=False):
        if not Path(ref["path"]).is_absolute():
            raise ValueError("estimate index references must be absolute")
        record = file_identity(ref["path"])
        if record["sha256"] != ref["sha256"]:
            raise ValueError(f"registered estimate input changed: {ref['path']}")
        record["role"] = label
        sources.append(record)
        raw = Path(record["path"]).read_text()
        return [json.loads(line) for line in raw.splitlines() if line] if jsonl else json.loads(raw)

    catalog = read(index["catalog"], "original_catalog")
    if len(catalog) != 130 or {t["suite"] for t in catalog} != ORIGINAL_SUITES:
        raise ValueError("the estimate requires exactly 40+90 explicitly cataloged original tasks")
    states = {}
    for task in catalog:
        if len(task["state_sha256"]) != task["trials"]:
            raise ValueError("catalog trials/state SHA count differs")
        for seed, digest in enumerate(task["state_sha256"]):
            states[task["suite"], task["task"], seed] = digest
    excluded_hashes, exclusion_counts = set(), {}
    for ref in index["exclusion_manifests"]:
        plan = read(ref, "selection_or_confirmation_manifest")
        cases = plan.get("cases", [])
        digests = set()
        for case in cases:
            episode = case["episode"]
            if episode["suite"] not in ORIGINAL_SUITES:
                raise ValueError("an exclusion manifest is not original LIBERO")
            key = episode["suite"], episode["task"], episode["seed"]
            if key not in states:
                raise ValueError("exclusion state is outside the catalog")
            digest = states[key]
            if case.get("state_sha256") not in (None, digest):
                raise ValueError("registered exclusion SHA differs from official catalog")
            digests.add(digest)
        excluded_hashes |= digests
        exclusion_counts[ref["path"]] = {"cases": len(cases), "unique_state_sha": len(digests)}
    for scope in index.get("public_reserved_ranges", []):
        # Public metadata only: this does not open a sealed payload or test file.
        for (suite, task, seed), digest in states.items():
            if suite == scope["suite"] and task in scope["tasks"] and seed in scope["init_states"]:
                excluded_hashes.add(digest)
    eligible = {key: digest for key, digest in states.items()
                if key[2] not in {*range(10), 40, 41} and digest not in excluded_hashes}
    train = {key: digest for key, digest in eligible.items() if 10 <= key[2] <= 39}
    validation = {key: digest for key, digest in eligible.items() if 42 <= key[2] <= 49}
    goal_pools, scene_pools, goal_safe, scene_safe = (defaultdict(set) for _ in range(4))
    per_task = []
    for task in catalog:
        prefix = task["suite"], task["task"]
        unvisited = {digest for key, digest in states.items()
                     if key[:2] == prefix and digest not in excluded_hashes}
        safe = {digest for key, digest in eligible.items() if key[:2] == prefix}
        for label in private_goal_labels(task):
            goal_pools[label] |= unvisited
            goal_safe[label] |= safe
        for label in fixture_labels(task):
            scene_pools[label] |= unvisited
            scene_safe[label] |= safe
        per_task.append({"suite": prefix[0], "task": prefix[1], "official_states": task["trials"],
                         "remaining_unreserved_states": len(unvisited), "eligible_public_upper_bound": len(safe),
                         "train_init10_39_upper_bound": sum(key[:2] == prefix for key in train),
                         "validation_init42_49_upper_bound": sum(key[:2] == prefix for key in validation)})
    walls, decisions = [], []
    for ref in index.get("expert_timing_ledgers", []):
        for row in read(ref, "expert_timing_ledger", jsonl=True):
            result = row["result"]
            if isinstance(result.get("wall_s"), (int, float)):
                walls.append(result["wall_s"])
            if isinstance(result.get("decisions"), int):
                decisions.append(result["decisions"])
    skill_report = read(index["skill_timing_report"], "single_skill_timing_report")
    skill_walls = [r["wall_s"] for r in skill_report["rows"] if isinstance(r.get("wall_s"), (int, float))]
    rollouts = 2 * len(train)  # one expert and one done-gated DAgger rollout per training init
    wall_stats, skill_stats = timing_summary(walls), timing_summary(skill_walls)
    scenarios = []
    if walls and skill_walls:
        for keyframes in (2, 4):
            for candidates in (3, 6, 24):
                branches = rollouts * keyframes * candidates * 4
                scenarios.append({"keyframes_per_rollout_assumption": keyframes,
                                  "candidates_per_keyframe_assumption": candidates, "seeds_per_candidate": 4,
                                  "physical_branch_attempts": branches,
                                  "expert_and_dagger_gpu_hours_at_historical_mean": rollouts * wall_stats["mean_s"] / 3600,
                                  "branch_gpu_hours_at_fresh_skill_median": branches * skill_stats["median_s"] / 3600,
                                  "branch_gpu_hours_at_fresh_skill_p90": branches * skill_stats["p90_s"] / 3600})
    gaps = list(index.get("unknown_exclusion_metadata", []))
    if not index.get("sealed_range_metadata_complete", False):
        gaps.append("explicit sealed init-range metadata is not located; no sealed payload was opened")
    if not index.get("all_selection_confirmation_registry_complete", False):
        gaps.append("the manifest list is explicit but may omit other selection/confirmation access registrations")
    gaps += ["fixture-present pools are metadata candidates, not measured applicability or confirmation results",
             "future frozen recipe and snapshot branch throughput are not yet measured",
             "LIBERO90 count extension is a planning estimate; this report does not authorize training it"]
    return {"version": "collection540-capacity-estimate/1", "scope": "CPU estimate only; not training admission",
            "new_physical_trials": 0, "new_training_rows": 0, "collection_authorized": False,
            "input_files": sources, "exclusion_manifest_counts": exclusion_counts,
            "official_tasks": 130, "official_state_tuples": len(states),
            "official_unique_state_sha": len(set(states.values())), "excluded_by_named_manifests_or_ranges": len(excluded_hashes),
            "remaining_public_upper_bound": len(eligible), "train_init10_39_upper_bound": len(train),
            "validation_init42_49_upper_bound": len(validation), "split_scope": "init-level, never row-level",
            "per_suite": {suite: {"official_states": sum(key[0] == suite for key in states),
                                   "train_upper_bound": sum(key[0] == suite for key in train),
                                   "validation_upper_bound": sum(key[0] == suite for key in validation)}
                          for suite in sorted(ORIGINAL_SUITES)}, "per_task": per_task,
            "independent_articulation_pool": {label: {
                "goal_matching_unreserved_states": len(goal_pools[label]),
                "goal_matching_public_seed_safe_upper_bound": len(goal_safe[label]),
                "fixture_present_unreserved_states": len(scene_pools[label]),
                "fixture_present_public_seed_safe_upper_bound": len(scene_safe[label]),
                "goal_only_shortfall_to100": max(0, 100 - len(goal_safe[label])),
                "fixture_metadata_shortfall_to100": max(0, 100 - len(scene_safe[label]))}
                for label in LABELS},
            "future_episode_plan_upper_bound": {"expert": len(train), "dagger": len(train), "total": rollouts},
            "historical_expert_wall": wall_stats, "historical_expert_decisions": timing_summary(decisions),
            "historical_single_skill_wall": skill_stats,
            "cost_scenarios": scenarios,
            "cost_scope": "one GPU per serial trajectory/branch; no assumed gain from 2–3 processes/GPU; fresh-reset timings include overhead; snapshot timing and shared decision-service GPU cost remain unmeasured",
            "gaps": gaps, "sealed_payload_opened": False, "PRO_payload_opened": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError("estimate output must be new")
    report = estimate(json.loads(args.index.read_text()))
    report["index"] = file_identity(args.index)
    report["producer"] = file_identity(__file__)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": file_identity(output), "official_state_tuples": report["official_state_tuples"],
                      "train_upper_bound": report["train_init10_39_upper_bound"],
                      "validation_upper_bound": report["validation_init42_49_upper_bound"],
                      "independent_articulation_pool": report["independent_articulation_pool"]}, indent=2))


if __name__ == "__main__":
    main()
