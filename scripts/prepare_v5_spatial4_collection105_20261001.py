# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Register the newly qualified original drawer-to-plate training task."""

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
    expert = [r for r in summary["episodes"] if r["episode"]["suite"] == "libero_spatial"
              and r["episode"]["task"] == 4]
    assert len(expert) == 5
    assert {r["episode"]["seed"] for r in expert} == set(range(5))
    assert sum(bool(r["result"]["correct_finish"]) for r in expert) >= 4
    prior = {tuple(r["identity"][:3])
             for r in json.loads(args.prior_episodes.read_text())}
    reserved = set()
    for path in args.reserved_plan:
        plan = json.loads(path.read_text())
        reserved.update((e["suite"], e["task"], e["seed"]) for e in plan["episodes"])
    planned = {("libero_spatial", 4, i) for i in range(10, 40)}
    assert not planned & (prior | reserved), "training init already collected or reserved"
    native = benchmark.get_benchmark_dict()["libero_spatial"]().get_task(4)
    prefixes = ("", "Please ", "For this task, ", "Carefully ", "Now ",
                "As requested, ", "For this scene, ", "In this scene, ",
                "Your task is to ", "Proceed to ")
    rewrites = [f"{prefix}{verb} the black bowl in the top drawer of the wooden cabinet "
                "and place it on the plate."
                for prefix in prefixes for verb in ("pick up", "grasp", "lift")]
    assert len(rewrites) == len(set(rewrites)) == 30
    config = json.loads(args.base_config.read_text())
    assert sha(config["wording_bank"]) == config["wording_bank_sha256"]
    bank = copy.deepcopy(json.loads(Path(config["wording_bank"]).read_text()))
    bank["tasks"]["libero_spatial/4"] = {
        "suite": "libero_spatial", "task": 4, "instruction": native.language,
        "instruction_sha256": hashlib.sha256(native.language.encode()).hexdigest(),
        "rewrites": rewrites, "origin": "Codex_original_task_only",
        "expert_summary_sha256": sha(args.expert_summary),
    }
    bank["instruction_count"] = sum(len(t["rewrites"]) for t in bank["tasks"].values())
    args.output.mkdir(parents=True, exist_ok=False)
    bank_path = args.output / "wording_bank.json"
    bank_path.write_text(json.dumps(bank, indent=2) + "\n")
    config.update(wording_bank=str(bank_path), wording_bank_sha256=sha(bank_path),
                  shared_schema=str(args.source / "shared_v5r_schema.py"),
                  eligible_tasks=[["libero_spatial", 4]], split="train",
                  collection_attempt="qualified_spatial4_source103_v1")
    assert sha(config["shared_schema"]) == config["shared_schema_sha256"]
    config_path = args.output / "collection_config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    states = benchmark.get_benchmark_dict()["libero_spatial"]().get_task_init_states(4)
    episodes = [{"suite": "libero_spatial", "task": 4, "seed": i,
                 "init_state_sha256": hashlib.sha256(
                     np.asarray(states[i]).tobytes(order="C")).hexdigest()}
                for i in range(10, 40)]
    plans = []
    for name, subset in (("smoke", episodes[:1]), ("remaining", episodes[1:])):
        path = args.output / f"{name}.json"
        path.write_text(json.dumps({"purpose": "newly qualified original drawer-to-plate training collection",
            "libero_type": "standard", "budget": {"max_decisions": 100, "max_chunks": 80,
            "max_episode_steps": 10000, "prompt_limit": 3072}, "episodes": subset}, indent=2) + "\n")
        plans.append({"part": name, "path": str(path), "sha256": sha(path), "episodes": len(subset)})
    report = {"purpose": "registered original-only collection; not full harness or SFT admission",
        "suite": "libero_spatial", "task": 4, "expert_correct5": 4,
        "expert_summary": str(args.expert_summary), "expert_summary_sha256": sha(args.expert_summary),
        "prior_episodes": str(args.prior_episodes), "prior_episodes_sha256": sha(args.prior_episodes),
        "reserved_plans": [{"path": str(p), "sha256": sha(p)} for p in args.reserved_plan],
        "collection_config": str(config_path), "collection_config_sha256": sha(config_path),
        "source": str(args.source), "plans": plans, "new_initial_states": 30,
        "training_init_indices": list(range(10, 40)), "excluded_init_indices": list(range(10)) + [40],
        "state_source": "perception", "PRO_inputs_used": False, "truth_usage": "labels_only",
        "instruction_count": 30, "generator_sha256": sha(__file__)}
    (args.output / "registration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
