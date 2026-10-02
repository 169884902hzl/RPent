# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Register original mug tasks from a complete, explicit ten-episode probe."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wording(task):
    """Codex-authored paraphrases preserve both original object assignments."""
    first = "the white mug on the left plate" if task == 4 else "the white mug on the plate"
    second = ("the yellow and white mug on the right plate" if task == 4
              else "the chocolate pudding to the right of the plate")
    prefixes = ("", "Please ", "For this task, ", "Carefully ",
                "First, ", "Now ", "As requested, ", "For this scene, ")
    return [f"{prefix}{a} {first} and {b} {second}."
            for prefix in prefixes for a in ("put", "place") for b in ("put", "place")][:30]


def main():
    from libero.libero import benchmark

    p = argparse.ArgumentParser()
    p.add_argument("--expert-ledger", type=Path, required=True)
    p.add_argument("--prior-episodes", type=Path, required=True)
    p.add_argument("--base-config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    records = [json.loads(line) for line in args.expert_ledger.read_text().splitlines()]
    expected = {("libero_10", t, i) for t in (4, 6) for i in range(5)}
    identities = [(r["episode"]["suite"], r["episode"]["task"], r["episode"]["seed"])
                  for r in records]
    assert len(records) == len(set(identities)) == 10 and set(identities) == expected
    prior = {tuple(r["identity"][:3]) for r in json.loads(args.prior_episodes.read_text())}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "expert_ledger.jsonl").write_bytes(args.expert_ledger.read_bytes())
    config = json.loads(args.base_config.read_text())
    assert sha(config["wording_bank"]) == config["wording_bank_sha256"]
    bank = copy.deepcopy(json.loads(Path(config["wording_bank"]).read_text()))
    budget = {"max_decisions": 100, "max_chunks": 80, "max_episode_steps": 10000,
              "prompt_limit": 3072}
    parts, smokes, qualifications = [], [], []
    for task in (4, 6):
        rows = [r for r in records if r["episode"]["task"] == task]
        correct = sum(bool(r["result"].get("correct_finish")) for r in rows)
        qualifications.append({"suite": "libero_10", "task": task, "correct_finish": correct,
                               "attempted": 5, "qualified": correct >= 4})
        if correct < 4:
            continue
        native = benchmark.get_benchmark_dict()["libero_10"]().get_task(task)
        variants = wording(task)
        assert len(set(variants)) == 30
        bank["tasks"][f"libero_10/{task}"] = {
            "suite": "libero_10", "task": task, "instruction": native.language,
            "instruction_sha256": hashlib.sha256(native.language.encode()).hexdigest(),
            "rewrites": variants, "origin": "Codex_original_task_only",
            "expert_ledger_sha256": sha(args.expert_ledger),
        }
        states = benchmark.get_benchmark_dict()["libero_10"]().get_task_init_states(task)
        episodes = []
        for init in range(10, 40):
            assert ("libero_10", task, init) not in prior
            episodes.append({"suite": "libero_10", "task": task, "seed": init,
                             "init_state_sha256": hashlib.sha256(
                                 np.asarray(states[init]).tobytes(order="C")).hexdigest()})
        smokes.append(episodes[0])
        path = args.output / f"part_{len(parts)}.json"
        path.write_text(json.dumps({"purpose": "newly qualified original mug training collection",
                                    "libero_type": "standard", "budget": budget,
                                    "episodes": episodes[1:]}, indent=2) + "\n")
        parts.append({"path": str(path), "sha256": sha(path), "episodes": 29, "task": task})
    if not parts:
        raise ValueError("neither original mug task reached four of five correct finishes")
    bank_path = args.output / "wording_bank.json"
    bank["instruction_count"] = sum(len(t["rewrites"]) for t in bank["tasks"].values())
    bank_path.write_text(json.dumps(bank, indent=2) + "\n")
    config.update(wording_bank=str(bank_path), wording_bank_sha256=sha(bank_path), split="train",
                  eligible_tasks=[["libero_10", t["task"]] for t in parts])
    config_path = args.output / "collection_config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    smoke_path = args.output / "smoke.json"
    smoke_path.write_text(json.dumps({"purpose": "new source physical-branch collection smoke",
                                      "libero_type": "standard", "budget": budget,
                                      "episodes": smokes}, indent=2) + "\n")
    report = {"purpose": "registered original-only collection; not full harness qualification",
              "qualifications": qualifications, "parts": parts,
              "smoke": {"path": str(smoke_path), "sha256": sha(smoke_path)},
              "collection_config": {"path": str(config_path), "sha256": sha(config_path)},
              "source_ledger": {"path": str(args.expert_ledger), "sha256": sha(args.expert_ledger)},
              "prior_episodes": {"path": str(args.prior_episodes), "sha256": sha(args.prior_episodes)},
              "new_initial_states": 30 * len(parts), "reserved_episode_overlap": 0,
              "training_init_indices": list(range(10, 40)), "excluded_init_indices": list(range(10)) + [40],
              "state_source": "perception", "PRO_inputs_used": False,
              "truth_usage": "labels_only", "generator_sha256": sha(__file__)}
    (args.output / "registration.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
