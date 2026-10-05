"""Register an original-task stove measurement experiment without PRO input."""

import argparse
import hashlib
import json
from pathlib import Path


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-manifest", type=Path, required=True)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--remote-root", type=Path, default=Path("/public/home/sunyihan/rpent_libero_eval"))
    args = parser.parse_args()
    original = json.loads(args.original_manifest.read_text())
    task = next(task for task in original["original_task_catalog"]
                if task["suite"] == "libero_goal" and task["task"] == 7)
    if task["asset_family"] != "LIBERO-original" or task["instruction"] != "turn on the stove":
        raise ValueError("registered original stove task identity changed")
    base = json.loads(args.base_config.read_text())
    if base["libero_type"] != "standard":
        raise ValueError("standard original LIBERO only")
    if hashlib.sha256(task["instruction"].encode()).hexdigest() != task["instruction_sha256"]:
        raise ValueError("registered original instruction changed")
    args.output.mkdir(parents=True, exist_ok=False)
    config = args.output / "base_config_stove521.json"
    config.write_bytes(args.base_config.read_bytes())
    remote = args.remote_root / "results/harness_v5/stove521_endpoint_original_20261005/preparation"
    cases = [{"name": f"libero_goal_t7_s{seed}", "episode": {"suite": "libero_goal", "task": 7, "seed": seed},
              "state_sha256": task["state_sha256"][seed], "bddl": task["bddl"], "init_file": task["init_file"],
              "original_instruction": task["instruction"], "object_symbol_for_labels_only": "flat_stove_1"}
             for seed in range(10)]
    plan = {
        "version": "original-stove-control-measurement/1-dev",
        "purpose": "measure actual control geometry after real on/off contact skills; development only",
        "parent_manifest": identity(args.original_manifest),
        "original_task_catalog_file": original["original_task_catalog_file"],
        "base_config": {"path": str(remote / config.name), "sha256": identity(config)["sha256"]},
        "budget": {"max_chunks_per_skill": 160, "actions_per_chunk": 5, "max_episode_steps": 10000},
        "phases": [{"name": "initial", "mode": None, "prompt": None},
                   {"name": "on", "mode": "turn_on", "prompt": "turn on the stove"},
                   {"name": "off", "mode": "turn_off", "prompt": "turn off the stove"}],
        "capture_views": ["agentview", "wrist"],
        "control_queries": ["stove knob", "stove switch handle"], "sam_min_score": .2,
        "recovery": "public release then existing retreat, followed by a fresh capture",
        "execution": "existing V5Executor.vla_act, chunk_budget; no truth-controlled retry, stop or pose",
        "private_labels": "requested turnon/turnoff predicates and qpos read-only at each saved observation",
        "public_state": "measured neutral entities only; private labels never supplied to controller",
        "planned_episodes": 10, "planned_contact_skills": 20,
        "shards": 4, "array": "0-3%8", "node_binding": None,
        "reserved_confirmation_states_consumed": False, "selection": "explicit original Goal task7 init0–9",
        "qualification_authorized": False, "new_training_rows": 0, "cases": cases,
        "required_stove_module_sha256": "b9dddb2da250b5897fc5a35eb387cd03a05c1a56f9ab81e7fb12168d35ab0d9a",
    }
    manifest = args.output / "stove_control.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    registration = {"manifest": identity(manifest), "base_config": identity(config),
                    "source": "final snapshot supplied with SKILL_SOURCE environment variable",
                    "producer_files": {name: identity(Path(__file__).with_name(name)) for name in (
                        "probe_v5_stove521_endpoint.py", "run_v5_stove521_endpoint.sbatch")},
                    "planned_episodes": 10, "planned_contact_skills": 20,
                    "shards": [[case["name"] for case in cases[index::4]] for index in range(4)],
                    "array": plan["array"], "node_binding": None, "new_training_rows": 0,
                    "qualification_authorized": False}
    (args.output / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    print(json.dumps(registration, indent=2))


if __name__ == "__main__":
    main()
