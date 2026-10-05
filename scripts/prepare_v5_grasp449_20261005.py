"""Register a paired first-grasp cohort from explicit original-task ledgers."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


GROUPS = {
    "bowl": {"bowl", "ramekin"},
    "mug": {"porcelain mug", "red coffee mug", "white yellow mug"},
    "bottle": {"ketchup", "salad dressing", "barbecue sauce", "wine bottle"},
    "box": {"cream cheese", "butter", "chocolate pudding", "cookie box"},
    "moka_pot": {"moka pot"},
    "frypan": {"frypan"},
}


def descriptor(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--choice-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (args.choice_package / "tokenizer_config.json").is_file():
        raise ValueError("choice package does not contain the registered tokenizer")
    from libero.libero import get_libero_path
    from libero.libero.envs.bddl_utils import robosuite_parse_problem
    from rlinf.envs.libero.utils import benchmark
    from robots.libero.v5_oracle_policy import _kind

    args.output.mkdir(parents=True, exist_ok=False)
    tasks, sources, goal_categories = defaultdict(dict), [], {}
    for ledger in args.ledger:
        sources.append(descriptor(ledger))
        for row in map(json.loads, ledger.read_text().splitlines()):
            ep = row["episode"]
            assert ep["suite"] in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
            key = (ep["suite"], ep["task"])
            if key not in goal_categories:
                task = benchmark.get_benchmark(ep["suite"])().get_task(ep["task"])
                bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
                goals = robosuite_parse_problem(str(bddl))["goal_state"]
                goal_categories[key] = {_kind(goal[1]) for goal in goals
                                        if len(goal) == 3 and goal[0] in ("on", "in")}
                sources.append(descriptor(bddl))
            initial = Path(row["output_dir"]) / "initial_measurements.json"
            data = json.loads(initial.read_text())
            sources.append(descriptor(initial))
            counts = Counter(e["name"] for e in data["entities"] if e["visible"])
            for group, names in GROUPS.items():
                unique = sorted(name for name in names if counts[name] == 1
                                and (name in goal_categories[key] or group == "frypan"))
                if unique:
                    tasks[group].setdefault((ep["suite"], ep["task"]), {
                        "category": unique[0], "original_goal_source": unique[0] in goal_categories[key]})
    if set(tasks) != set(GROUPS):
        raise ValueError("uncovered original categories: " + str(set(GROUPS) - set(tasks)))
    controlled = {
        "grasp_safe_approach_v2": True, "grasp_approach_v1": False,
        "grasp_retry_v1": False, "wrist_refine_v1": False,
        "grasp_clearance_v1": False, "grasp_rim_v1": False,
        "skill_profile": "none", "legal_memory_manifest": None,
        "manual": "none", "card": None, "rpent_memory_index": None,
    }
    conditions = {
        **{f"current_{mode}": {"profile": "current", "mode": mode,
                                "max_chunks": 80, "overrides": {}}
           for mode in ("direct", "above_10cm", "yaw_90")},
        "current_restage": {"profile": "current", "mode": "direct", "max_chunks": 80, "overrides": {}},
        "high_short80": {"profile": "high_short", "mode": "direct", "max_chunks": 80, "overrides": controlled},
        "start_full80": {"profile": "start_full", "mode": "direct", "max_chunks": 80, "overrides": controlled},
        "high_short160": {"profile": "high_short", "mode": "direct", "max_chunks": 160, "overrides": controlled},
        "start_full160": {"profile": "start_full", "mode": "direct", "max_chunks": 160, "overrides": controlled},
    }
    cohort = []
    # Round-robin across eligible original tasks before advancing init index.
    # Every condition gets these exact same 50 scenes per category group.
    for group in GROUPS:
        candidates = [(suite, task, seed, selection)
                      for seed in range(50)
                      for (suite, task), selection in sorted(tasks[group].items())][:50]
        for suite, task, seed, selection in candidates:
            cohort.append({"group": group, **selection,
                           "episode": {"suite": suite, "task": task, "seed": seed}})
    cases = [{**case, "condition": condition,
              "name": f'{case["group"]}_{case["episode"]["suite"]}_t{case["episode"]["task"]}_s{case["episode"]["seed"]}_{condition}'}
             for case in cohort for condition in conditions]
    manifest = {
        "purpose": "original-task grasp diagnosis; not training or PRO evaluation",
        "base_config": descriptor(args.base_config), "choice_package": str(args.choice_package),
        "original_sources": sources, "groups": {g: sorted(v) for g,v in GROUPS.items()},
        "conditions": conditions, "cases": cases,
        "first_attempts_per_condition_group": 50,
        "selection": "unique visible original goal-source category; frypan is an original scene object and uses a registered full grasp-probe instruction when not a goal source",
        "frypan_full_prompt": "pick up the frypan and lift it clear of its starting surface",
        "pairing": "exact same task/init/category for all eight conditions; deterministic reset",
        "private_truth": "dual finger contact and body origins for diagnostic labels only; excluded from prompts",
        "budget": "common 10000 env steps, 80 or 160 contact chunks; chunks execute actual five-action horizon",
        "new_training_rows": 0,
    }
    for name, selected in (("full", cases), ("smoke", [c for c in cases if next(
            x for x in cohort if x["group"] == c["group"]) == {k:c[k] for k in ("group","category","episode","original_goal_source")}])):
        plan = {**manifest, "cases": selected, "cohort": name}
        path = args.output / (name + ".json")
        path.write_text(json.dumps(plan, indent=2) + "\n")
        print(json.dumps({"manifest": descriptor(path), "cases": len(selected)}))


if __name__ == "__main__":
    main()
