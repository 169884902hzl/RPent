# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Prepare a physical collection probe from explicitly registered targets."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", type=Path, required=True)
    parser.add_argument("--qualification", type=Path, required=True)
    parser.add_argument("--collection-config", type=Path, required=True)
    parser.add_argument("--budget-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registered = json.loads(args.variants.read_text())
    qualification = json.loads(args.qualification.read_text())
    config = json.loads(args.collection_config.read_text())
    budget_plan = json.loads(args.budget_plan.read_text())
    budget = budget_plan["budget"]
    assert registered["PRO_inputs_used"] is False
    assert config["exclusions"]["PRO_training_texts_used"] is False
    assert config["exclusions"]["human102_or_sealed_files_read"] is False
    eligible = {(row["suite"], row["task"]) for row in qualification["by_task"]
                if row["attempted"] == 5 and row["correct_finish"] >= 4}
    selected = [row for row in registered["variants"]
                if row["variant_kind"] == "counterfactual_goal"]
    assert len(selected) == 16
    assert budget_plan["cap_prompt_tokens"] == 3072
    inputs = {str(path): sha(path) for path in
              (args.variants, args.qualification, args.collection_config, args.budget_plan)}
    plans, identities = [], set()
    args.output.mkdir(parents=True, exist_ok=False)
    for index, row in enumerate(selected):
        assert (row["suite"], row["task"]) in eligible
        spec_path = Path(row["spec"])
        assert sha(spec_path) == row["sha256"]
        spec = json.loads(spec_path.read_text())
        assert spec["PRO_inputs_used"] is False
        assert len(set(spec["rewrites"])) == len(spec["rewrites"]) == 30
        assert sha(spec["variant_bddl"]) == spec["variant_bddl_sha256"]
        identity = (row["suite"], row["task"], spec["variant_bddl_sha256"], 10)
        assert identity not in identities
        identities.add(identity)
        episode = {"suite": row["suite"], "task": row["task"], "seed": 10,
                   "counterfactual_spec": str(spec_path)}
        plan = {"purpose": "registered original-scene counterfactual physical probe; not evaluation",
                "libero_type": "standard", "episodes": [episode], "budget": budget,
                "cap_prompt_tokens": 3072,
                "variant_kind": "counterfactual_goal", "spec_sha256": row["sha256"]}
        path = args.output / f"part_{index}.json"
        path.write_text(json.dumps(plan, indent=2) + "\n")
        plans.append({"path": str(path), "sha256": sha(path), "episode": episode,
                      "goal": spec["goal"], "rewrites": len(spec["rewrites"]),
                      "spec_sha256": row["sha256"]})
    config["purpose"] = "registered counterfactual probes; only correct-finish episodes admitted"
    config["eligible_tasks"] = [list(key) for key in sorted({identity[:2] for identity in identities})]
    config_path = args.output / "collection_config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    report = {"purpose": "physical collection preparation; no new labels yet", "plans": plans,
              "input_sha256": inputs, "collection_config": str(config_path),
              "collection_config_sha256": sha(config_path), "training_init_indices": [10],
              "counterfactual_targets": len(plans), "unchanged_original_goals_skipped": 2,
              "duplicate_variant_scene_init": 0, "PRO_inputs_used": False,
              "new_training_rows": 0, "physical_admission": "correct_finish plus branch validation only",
              "generator_sha256": sha(__file__)}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"plans": len(plans), "manifest_sha256": sha(args.output / "manifest.json")}))


if __name__ == "__main__":
    main()
