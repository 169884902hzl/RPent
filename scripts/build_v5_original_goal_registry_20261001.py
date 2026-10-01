"""Register original targets from explicitly declared collected episodes only."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from libero.libero import benchmark, get_libero_path
    from libero.libero.envs.bddl_utils import robosuite_parse_problem
    source = json.loads(args.manifest.read_text())
    tasks, episodes = {}, []
    for record in source["episodes"]:
        suite, task, init = record["identity"][:3]
        assert suite in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
        key = suite + "/" + str(task)
        if key not in tasks:
            native = benchmark.get_benchmark_dict()[suite]().get_task(task)
            bddl = Path(get_libero_path("bddl_files")) / native.problem_folder / native.bddl_file
            tasks[key] = {"suite": suite, "task_id": task, "original_language": native.language,
                          "bddl_path": str(bddl), "bddl_sha256": sha(bddl),
                          "original_goals_label_only": robosuite_parse_problem(str(bddl))["goal_state"]}
        raw = Path(record["output"])
        config = json.loads((raw / "config.json").read_text())
        instruction = config["instruction_override"]
        episodes.append({"suite": suite, "task_id": task, "init_state_index": init,
                         "instruction_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
                         "instruction_origin": "original_only_Codex_wording_bank",
                         "goal_origin": "original_task" if not config.get("counterfactual_spec") else "registered_original_scene_counterfactual",
                         "counterfactual_spec": config.get("counterfactual_spec"),
                         "runtime_config_path": str(raw / "config.json"), "runtime_config_sha256": sha(raw / "config.json")})
    report = {"source_manifest": str(args.manifest), "source_manifest_sha256": sha(args.manifest),
              "tasks": tasks, "episodes": episodes, "PRO_text_read": False,
              "target_overlap_policy": "Codex1 compares targets with PRO in isolation; retain overlap and report overlap/nonoverlap separately per latest user instruction",
              "PRO_isolation_side_comparison_complete": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"tasks": len(tasks), "episodes": len(episodes), "sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
