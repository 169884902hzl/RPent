"""Register explicit original-task contact/subtask explorations, not training.

Only the original four 10-task suites are read. Private symbols and predicates
are probe/oracle metadata; the runtime renders its selected public entities
through robots.libero.v5_subtasks instead of copying these metadata strings.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_subtasks import subtask_phrase

ORIGINAL_SUITES = ("libero_spatial", "libero_object", "libero_goal", "libero_10")


def descriptor(path: Path) -> dict:
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_original_tasks() -> list[dict]:
    """Read exactly 40 original tasks and their 50 published initial states."""
    from libero.libero import get_libero_path
    from libero.libero.envs.bddl_utils import robosuite_parse_problem
    from rlinf.envs.libero.utils import benchmark
    from robots.libero.v5_oracle_policy import _kind

    tasks = []
    for name in ORIGINAL_SUITES:
        suite = benchmark.get_benchmark(name)()
        if suite.n_tasks != 10:
            raise ValueError("registered original suite no longer has ten tasks")
        for index in range(10):
            task = suite.get_task(index)
            bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
            initial = Path(get_libero_path("init_states")) / task.problem_folder / task.init_states_file
            problem = robosuite_parse_problem(str(bddl))
            states = suite.get_task_init_states(index)
            symbols = [symbol for mapping in (problem["objects"], problem["fixtures"])
                       for values in mapping.values() for symbol in values]
            symbols.extend(problem["regions"])
            tasks.append({"suite": name, "task": index, "asset_family": "LIBERO-original",
                "instruction": task.language,
                "instruction_sha256": hashlib.sha256(task.language.encode()).hexdigest(),
                "bddl": descriptor(bddl), "init_file": descriptor(initial),
                "trials": len(states), "state_sha256": [hashlib.sha256(
                    np.asarray(state, dtype="<f8", order="C").tobytes()).hexdigest() for state in states],
                "oracle_goal_predicates": problem["goal_state"],
                "symbol_categories": {symbol: _kind(symbol) for symbol in symbols}})
    return tasks


def _category(task: dict, symbol: str, mode: str) -> str:
    kind = task["symbol_categories"][symbol]
    if kind in ("cabinet", "drawer"):
        part = next((part for part in ("top", "middle", "bottom")
                     if f"_{part}_region" in symbol), None)
        if part:
            return f"cabinet {part} drawer" if mode != "on" else "cabinet top surface"
    return kind


def build_explorations(tasks: list[dict], base_config: dict, choice_package: str,
                       max_chunks: int = 160) -> dict[str, dict]:
    """Pair 100 nominal first requests per arm on the same 50 resets twice."""
    expected = {(suite, index) for suite in ORIGINAL_SUITES for index in range(10)}
    keys = [(task["suite"], task["task"]) for task in tasks]
    if set(keys) != expected or len(keys) != 40:
        raise ValueError("requires the explicit original 40-task catalog, without PRO or LIBERO-90")
    if max_chunks <= 0:
        raise ValueError("contact budget must be positive")
    for task in tasks:
        if task["asset_family"] != "LIBERO-original" or task["trials"] < 50 or len(task["state_sha256"]) < 50:
            raise ValueError("all registered original tasks need fifty published states")
    by_key = dict(zip(keys, tasks))
    controlled = {"vla_subtask_v1": True, "manual": "none", "skill_profile": "none",
                  "card": None, "legal_memory_manifest": None, "rpent_memory_index": None,
                  "deterministic_reset_v1": True, "dual_view_fusion_v1": True,
                  "fusion_depth_trim_v2": True, "measured_action_receipts_v1": True,
                  "measurement_progress_blocking_v1": True}
    common = {"version": "original-skill-exploration/1", "base_config": base_config,
        "choice_package": choice_package, "original_task_catalog": tasks,
        "purpose": "original-only paired exploration, never confirmation or training",
        "new_training_rows": 0, "runtime_default_changed": False,
        "pairing": "same original task/init/category and registered setup for every arm",
        "state_repetition": "all fifty official original states reset twice per arm; 100 nominal requests, 50 unique scenes",
        "confirmation": "no reserved confirmation states are selected or consumed",
        "runtime_input": "neutral IDs and measured entities only; private probe metadata excluded",
        "budget": {"max_chunks": max_chunks, "actions_per_chunk": 5,
                   "max_episode_steps": 10000, "max_prompt_tokens": 3072},
        "metrics": {"first_attempt_denominator": "all 100 preregistered requests, including setup/measurement failures",
                    "truth_source": "private original-task predicates and contacts for diagnostics only",
                    "subtask_completion": "separate from sustained grasp and from public measured receipt",
                    "grasp_truth": "original 0.5s sustained hold, >=3cm whole collision-geometry clearance and finger support",
                    "grasp_after_release": "a completed transfer that releases is not sustained-grasp success"}}

    def cases_for(task: dict, kind: str, label: str, source: str, mode: str,
                  conditions: dict, *, target: str | None = None,
                  setup: list[dict] | None = None, prompt_origin: str = "legal_original_subtask_template") -> list[dict]:
        source_category = _category(task, source, mode)
        target_category = _category(task, target, mode) if target else None
        cases = []
        for trial in range(100):
            seed = trial % 50
            for arm in conditions:
                case = {"name": f"{label}_{task['suite']}_t{task['task']}_s{seed}_r{trial // 50}_{arm}",
                        "episode": {"suite": task["suite"], "task": task["task"], "seed": seed},
                        "kind": kind, "type": label, "mode": mode,
                        "object_symbol": source, "object_category": source_category,
                        "subtask_prompt": subtask_phrase(source_category, mode, target_category),
                        "prompt_origin": prompt_origin, "original_instruction": task["instruction"],
                        "setup": copy.deepcopy(setup or []), "condition": arm,
                        "trial_index": trial, "initial_state_repetition": trial // 50,
                        "state_sha256": task["state_sha256"][seed],
                        "bddl": task["bddl"], "init_file": task["init_file"],
                        "private_metadata_use": "original-task oracle/probe only, never state/candidate text"}
                if target:
                    case.update(target_symbol=target, target_category=target_category)
                cases.append(case)
        return cases

    arms = {"current160": {"executor": "current", "max_chunks": max_chunks, "overrides": controlled},
            "vla_subtask160": {"executor": "vla_subtask", "max_chunks": max_chunks,
                "contact_stop": "subtask_measurement_or_budget", "grasp_early_stop": False,
                "overrides": controlled}}
    fixture_cases = []
    fixture_specs = (
        ("drawer_open", "libero_goal", 0, "wooden_cabinet_1_middle_region", "open", None),
        ("drawer_close", "libero_10", 3, "white_cabinet_1_bottom_region", "close", "open"),
        ("microwave_open", "libero_10", 9, "microwave_1", "open", None),
        ("microwave_close", "libero_10", 9, "microwave_1", "close", "open"),
        ("stove_turn_on", "libero_goal", 7, "flat_stove_1", "turn_on", None),
        ("stove_turn_off", "libero_goal", 7, "flat_stove_1", "turn_off", "turn_on"),
    )
    for label, suite, index, symbol, mode, precondition in fixture_specs:
        task = by_key[suite, index]
        setup = [] if precondition is None else [{"tool": "articulate", "object_symbol": symbol,
            "object_category": _category(task, symbol, precondition), "mode": precondition}]
        fixture_cases.extend(cases_for(task, "articulate", label, symbol, mode, arms, setup=setup))

    place_cases = []
    for label, suite, index in (("place_on", "libero_goal", 8), ("place_in", "libero_object", 1)):
        task = by_key[suite, index]
        mode = label.removeprefix("place_")
        goal = next(goal for goal in task["oracle_goal_predicates"] if len(goal) == 3 and goal[0] == mode)
        source, target = goal[1:]
        setup = [{"tool": "grasp", "object_symbol": source,
                  "object_category": _category(task, source, mode), "mode": "direct",
                  "required_public_receipt": "grasp_verified",
                  "private_diagnostic": "true_sustained_grasp_record_only"}]
        place_cases.extend(cases_for(task, "place", label, source, mode, arms, target=target, setup=setup))

    grasp_task = by_key["libero_10", 2]
    stove = next(goal[2] for goal in grasp_task["oracle_goal_predicates"] if goal[0] == "on")
    grasp_arms = {
        "handle_short160": {"executor": "current", "profile": "high_short", "mode": "direct",
            "max_chunks": max_chunks, "contact_standoff_m": .10, "contact_approach": "measured_handle",
            "handle_categories": ["frypan", "moka pot"], "contact_stop": "rpent_pick",
            "contact_prompt_binding": "selected_only", "contact_category_aliases": {"frypan": "frying pan"},
            "contact_verification": "stable_lower_gripper_wrist", "overrides": controlled},
        "handle_full_subtask160": {"executor": "vla_subtask", "profile": "high_short", "mode": "direct",
            "max_chunks": max_chunks, "contact_standoff_m": .10, "contact_approach": "measured_handle",
            "handle_categories": ["frypan", "moka pot"], "contact_stop": "subtask_measurement_or_budget",
            "grasp_early_stop": False, "overrides": controlled}}
    grasp_cases = []
    for category, label in (("frypan", "pan_handle_full"), ("moka pot", "moka_handle_full")):
        symbols = [symbol for symbol, name in grasp_task["symbol_categories"].items() if name == category]
        if len(symbols) != 1:
            raise ValueError("original handle comparison requires a unique original-scene source")
        grasp_cases.extend(cases_for(grasp_task, "grasp_then_subtask", label, symbols[0], "on", grasp_arms,
            target=stove, prompt_origin="registered_original_scene_transfer_template" if category == "frypan"
            else "original_moka_transfer_clause_rendered_with_public_categories"))
    plans = {"full": {**common, "conditions": grasp_arms, "cases": grasp_cases},
             "fixtures": {**common, "conditions": arms, "cases": fixture_cases},
             "place": {**common, "conditions": arms, "cases": place_cases,
                "setup_failures": "record not_attempted; never label an unverified setup as an executed first place"}}
    for plan in plans.values():
        plan["preregistered_requests_by_type_arm"] = dict(Counter(
            f"{case['type']}/{case['condition']}" for case in plan["cases"]))
    return plans


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--choice-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-chunks", type=int, default=160)
    args = parser.parse_args()
    if not (args.choice_package / "tokenizer_config.json").is_file():
        raise ValueError("explicit choice package lacks its tokenizer config")
    base = json.loads(args.base_config.read_text())
    if base["libero_type"] != "standard":
        raise ValueError("this exploration only accepts the original standard LIBERO environment")
    tasks = read_original_tasks()
    plans = build_explorations(tasks, descriptor(args.base_config), str(args.choice_package), args.max_chunks)
    args.output.mkdir(parents=True, exist_ok=False)
    catalog = args.output / "original_tasks.json"
    catalog.write_text(json.dumps(tasks, indent=2) + "\n")
    for name, plan in plans.items():
        plan["original_task_catalog_file"] = descriptor(catalog)
        path = args.output / f"{name}.json"
        path.write_text(json.dumps(plan, indent=2) + "\n")
        print(json.dumps({"manifest": descriptor(path), "requests": len(plan["cases"]),
                          "by_type_arm": plan["preregistered_requests_by_type_arm"]}))


if __name__ == "__main__":
    main()
