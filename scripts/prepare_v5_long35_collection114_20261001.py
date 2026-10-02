# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Register two qualified original tasks without reading PRO task text."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    from libero.libero import benchmark

    parser = argparse.ArgumentParser()
    parser.add_argument("--expert-summary", type=Path, required=True)
    parser.add_argument("--prior-episodes", type=Path, required=True)
    parser.add_argument("--reserved-plan", type=Path, action="append", required=True)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = json.loads(args.expert_summary.read_text())
    qualification = {}
    for task in (3, 5):
        expert = [r for r in summary["episodes"] if r["episode"]["suite"] == "libero_10"
                  and r["episode"]["task"] == task]
        assert len(expert) == 5
        assert {r["episode"]["seed"] for r in expert} == set(range(5))
        qualification[task] = sum(bool(r["result"]["correct_finish"]) for r in expert)
        assert qualification[task] >= 4
    prior = {tuple(r["identity"][:3])
             for r in json.loads(args.prior_episodes.read_text())}
    reserved = set()
    for path in args.reserved_plan:
        plan = json.loads(path.read_text())
        reserved.update((e["suite"], e["task"], e["seed"]) for e in plan["episodes"])
    planned = {("libero_10", t, i) for t in (3, 5) for i in range(10, 40)}
    assert not planned & (prior | reserved), "training init already collected or reserved"
    bench = benchmark.get_benchmark_dict()["libero_10"]()
    prefixes = ("", "Please ", "For this task, ", "In this scene, ", "Your task is to ")
    templates = {
        3: ["place the black bowl in the bottom drawer of the cabinet and close the drawer.",
            "put the black bowl into the bottom drawer of the cabinet, then close it.",
            "set the black bowl inside the bottom drawer of the cabinet and close that drawer.",
            "move the black bowl to the bottom drawer of the cabinet, then shut the drawer.",
            "pick up the black bowl and put it in the bottom drawer of the cabinet; finish by closing the drawer.",
            "open the bottom drawer of the cabinet, put the black bowl inside, and close the drawer."],
        5: ["pick up the book and place it in the back compartment of the caddy.",
            "put the black book in the back compartment of the caddy.",
            "move the book into the back compartment of the caddy.",
            "lift the black book and set it in the back compartment of the caddy.",
            "transfer the book to the back compartment of the caddy.",
            "take the black book from the table and put it in the back compartment of the caddy."],
    }
    rewrites = {task: [prefix + text for prefix in prefixes for text in templates[task]] for task in (3, 5)}
    assert all(len(texts) == len(set(texts)) == 30 for texts in rewrites.values())
    config = json.loads(args.base_config.read_text())
    assert sha(config["wording_bank"]) == config["wording_bank_sha256"]
    bank = copy.deepcopy(json.loads(Path(config["wording_bank"]).read_text()))
    for task in (3, 5):
        native = bench.get_task(task)
        bank["tasks"][f"libero_10/{task}"] = {
            "suite": "libero_10", "task": task, "instruction": native.language,
            "instruction_sha256": hashlib.sha256(native.language.encode()).hexdigest(),
            "rewrites": rewrites[task], "origin": "Codex_original_task_only",
            "expert_summary_sha256": sha(args.expert_summary),
        }
    bank["instruction_count"] = sum(len(t["rewrites"]) for t in bank["tasks"].values())
    args.output.mkdir(parents=True, exist_ok=False)
    bank_path = args.output / "wording_bank.json"
    bank_path.write_text(json.dumps(bank, indent=2) + "\n")
    config.update(wording_bank=str(bank_path), wording_bank_sha256=sha(bank_path),
                  shared_schema=str(args.source / "shared_v5r_schema.py"),
                  eligible_tasks=[["libero_10", t] for t in (3, 5)], split="train")
    assert sha(config["shared_schema"]) == config["shared_schema_sha256"]
    config_path = args.output / "collection_config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    episodes = []
    for task in (3, 5):
        states = bench.get_task_init_states(task)
        episodes.extend({"suite": "libero_10", "task": task, "seed": i,
                         "init_state_sha256": hashlib.sha256(np.asarray(states[i]).tobytes(order="C")).hexdigest()}
                        for i in range(10, 40))
    plans = []
    for name, subset in (("smoke", [e for e in episodes if e["seed"] == 10]),
                         ("remaining", [e for e in episodes if e["seed"] != 10])):
        path = args.output / f"{name}.json"
        path.write_text(json.dumps({"purpose": "qualified original Long3 drawer and Long5 book training collection",
            "libero_type": "standard", "budget": {"max_decisions": 100, "max_chunks": 80,
            "max_episode_steps": 10000, "prompt_limit": 3072}, "episodes": subset}, indent=2) + "\n")
        plans.append({"part": name, "path": str(path), "sha256": sha(path), "episodes": len(subset)})
    report = {"purpose": "registered original-only collection; not full harness or SFT admission",
        "suite": "libero_10", "tasks": [3, 5], "expert_correct5": qualification,
        "expert_summary": str(args.expert_summary), "expert_summary_sha256": sha(args.expert_summary),
        "prior_episodes": str(args.prior_episodes), "prior_episodes_sha256": sha(args.prior_episodes),
        "reserved_plans": [{"path": str(p), "sha256": sha(p)} for p in args.reserved_plan],
        "collection_config": str(config_path), "collection_config_sha256": sha(config_path),
        "source": str(args.source), "plans": plans, "new_initial_states": 60,
        "collection_version": "qualified_long3_long5_source112_v1",
        "training_init_indices": list(range(10, 40)), "excluded_init_indices": list(range(10)) + [40],
        "state_source": "perception", "PRO_inputs_used": False, "truth_usage": "labels_only",
        "instruction_count": 60, "generator_sha256": sha(__file__)}
    (args.output / "registration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
