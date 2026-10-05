"""Register unseen original LIBERO states for a later grasp confirmation.

This CPU-only preparation reads explicit original benchmark tasks. It neither
executes a skill nor assigns a grasp success label. LIBERO-90 is an explicitly
declared distribution extension where the original 40 tasks lack 100 unseen
official states. State hashes exclude every state in the fixed 3550 manifest.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path


SOURCE_SHA = "9dca2edd661ccba0d6e69efb595c8951ba9eccb16c74584e48e1007adfb175d0"
GROUPS = {
    "bowl": {"bowl", "ramekin"},
    "bottle": {"ketchup", "salad dressing", "barbecue sauce", "wine bottle"},
    "box": {"cream cheese", "butter", "chocolate pudding", "cookie box"},
    "frypan": {"frypan"},
    "moka_pot": {"moka pot"},
    "mug": {"porcelain mug", "red coffee mug", "white yellow mug"},
}
TASKS = {
    "bowl": [("libero_10", 3), *[("libero_goal", i) for i in (1, 3, 4, 8)]],
    "bottle": [("libero_goal", 2), ("libero_goal", 9),
               *[("libero_object", i) for i in (2, 3, 4)]],
    "box": [("libero_10", 1), ("libero_10", 6), ("libero_10", 7),
            ("libero_goal", 6), *[("libero_object", i) for i in (1, 6, 8)]],
    "frypan": [("libero_90", i) for i in (18, 21, 40, 41, 42, 45)],
    "moka_pot": [("libero_90", i) for i in (18, 19, 20, 21)],
    "mug": [("libero_90", i) for i in (65, 66, 67, 68)],
}


def file_record(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--libero-config-path", type=Path, required=True)
    parser.add_argument("--expected-asset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = args.libero_config_path / "config.yaml"
    if not config.is_file():
        raise ValueError("explicit existing LIBERO config required; do not initialize one")
    if file_record(args.source_manifest)["sha256"] != SOURCE_SHA:
        raise ValueError("fixed 3550 source manifest differs")
    os.environ["LIBERO_TYPE"] = "standard"
    os.environ["LIBERO_CONFIG_PATH"] = str(args.libero_config_path)

    import numpy as np
    from libero.libero import get_libero_path
    from libero.libero.envs.bddl_utils import robosuite_parse_problem
    from rlinf.envs.libero.utils import benchmark
    from robots.libero.v5_oracle_policy import _kind

    roots = {name: Path(get_libero_path(name)).absolute() for name in
             ("bddl_files", "init_states", "assets")}
    expected = args.expected_asset_root.resolve()
    if any(not roots[name].resolve().is_relative_to(expected) for name in
           ("bddl_files", "init_states")):
        raise ValueError("configured original assets differ from the registered runtime root")
    source = json.loads(args.source_manifest.read_text())
    allowed = {"libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}
    old_tuples = {(r["episode"]["suite"], r["episode"]["task"], r["episode"]["seed"])
                  for r in source["cases"]}
    if {suite for suite, _, _ in old_tuples} - (allowed - {"libero_90"}):
        raise ValueError("source is not the fixed original-task cohort")
    suites = {s: benchmark.get_benchmark(s)() for s in sorted(allowed)}
    state_cache, task_cache = {}, {}

    def states(suite, task):
        if (suite, task) not in state_cache:
            state_cache[suite, task] = np.asarray(suites[suite].get_task_init_states(task))
        return state_cache[suite, task]

    def state_sha(state):
        return hashlib.sha256(np.asarray(state, dtype="<f8", order="C").tobytes()).hexdigest()

    old_hashes = {state_sha(states(s, t)[i]) for s, t, i in old_tuples}

    def metadata(suite, task_id):
        if (suite, task_id) in task_cache:
            return task_cache[suite, task_id]
        task = suites[suite].get_task(task_id)
        bddl = roots["bddl_files"] / task.problem_folder / task.bddl_file
        init = roots["init_states"] / task.problem_folder / task.init_states_file
        # These paths come from the explicitly listed original benchmark tasks.
        if task.problem_folder not in allowed:
            raise ValueError("non-original task folder")
        problem = robosuite_parse_problem(str(bddl))
        names = Counter(_kind(obj) for symbols in problem["objects"].values() for obj in symbols)
        goals = {_kind(goal[1]) for goal in problem["goal_state"]
                 if len(goal) == 3 and goal[0] in ("on", "in")}
        value = {"suite": suite, "task": task_id,
                 "benchmark_language": task.language,
                 "bddl_language": " ".join(problem["language_instruction"]),
                 "bddl": file_record(bddl), "init_file": file_record(init),
                 "official_init_count": len(states(suite, task_id)),
                 "categories": dict(names), "goal_categories": sorted(goals)}
        task_cache[suite, task_id] = value
        return value

    selected, by_group = [], {}
    for group, tasks in TASKS.items():
        pool, seen = [], set()
        for init_id in range(10, 40):
            for suite, task_id in tasks:
                key = (suite, task_id, init_id)
                info = metadata(suite, task_id)
                state = states(suite, task_id)[init_id]
                digest = state_sha(state)
                if key in old_tuples or digest in old_hashes or digest in seen:
                    continue
                names = sorted(name for name, n in info["categories"].items()
                               if n == 1 and name in GROUPS[group])
                goals = [name for name in names if name in info["goal_categories"]]
                if not names:
                    continue
                chosen = (goals or names)[0]
                seen.add(digest)
                pool.append({"group": group, "category": chosen,
                    "original_goal_source": chosen in info["goal_categories"],
                    "episode": {"suite": suite, "task": task_id, "seed": init_id},
                    "official_init_index": init_id, "state_sha256": digest,
                    "state_shape": list(state.shape), "state_hash_encoding": "C contiguous little endian float64",
                    "init_file": info["init_file"], "bddl": info["bddl"],
                    "instruction": info["benchmark_language"], "bddl_language": info["bddl_language"],
                    "requires_current_visible_unique_binding": True,
                    "source": "official_original_LIBERO90" if suite == "libero_90" else "official_original_LIBERO40"})
        if len(pool) < 100:
            raise ValueError(f"{group}: only {len(pool)} unseen official states")
        cases = [{**r, "name": f'{group}_{r["episode"]["suite"]}_t{r["episode"]["task"]}_s{r["episode"]["seed"]}_confirmation'}
                 for r in pool[:100]]
        selected.extend(cases)
        counts = Counter((r["episode"]["suite"], r["episode"]["task"]) for r in cases)
        by_group[group] = {"selected": len(cases), "available_in_explicit_pool": len(pool),
                           "unique_state_hashes": len({r["state_sha256"] for r in cases}),
                           "task_counts": [{"suite": s, "task": t, "rows": n}
                                           for (s, t), n in sorted(counts.items())],
                           "non_goal_scene_grasp_probes": sum(not r["original_goal_source"] for r in cases),
                           "old_tuple_overlap": 0, "old_state_hash_overlap": 0}
    if len(selected) != 600 or any(r["state_sha256"] in old_hashes for r in selected):
        raise AssertionError("confirmation uniqueness/leakage check failed")
    plan = {"purpose": "CPU candidate registration; no physics execution, no success labels",
            "source_manifest": file_record(args.source_manifest),
            "config": file_record(config), "benchmark_python_namespace": benchmark.__name__,
            "asset_roots": {k: str(v) for k, v in roots.items()},
            "resolved_asset_roots": {k: str(v.resolve()) for k, v in roots.items()},
            "initial_state_policy": "official indices10-39 only; exact tuple and raw state SHA disjoint from all fixed3550 cases",
            "distribution_extension": "frypan, moka_pot and mug confirmation use original LIBERO90; not the original40-task distribution",
            "selection_rule": "explicit original task list; round robin ascending official init10-39; prefer unique goal-source category, otherwise unique original scene category",
            "qualification": "none; freeze skill-card recipe before executing this confirmation; judge95% overall/90% class/95% agreement on confirmation only",
            "prior_cases": len(source["cases"]), "prior_unique_scene_tuples": len(old_tuples),
            "prior_unique_raw_state_hashes": len(old_hashes), "per_group": by_group,
            "new_training_rows": 0, "new_physical_trials": 0, "cases": selected}
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = args.output / "candidate_pool.json"
    manifest.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    task_info = args.output / "original_task_sources.json"
    task_info.write_text(json.dumps(list(task_cache.values()), ensure_ascii=False, indent=2) + "\n")
    lines = ["# 原版独立确认池（CPU登记）", "", "已选六类各100个官方原版状态；未执行物理试次，未授予资格。",
             "与3550全部435个唯一场景的tuple及原始state SHA均零重合。init仅10–39。",
             "平底锅、摩卡壶与杯类明确扩展到原版LIBERO-90；不能声称这三类来自原版40任务未用状态。", "",
             "|类别|确认候选数|显式任务池可用数|唯一state|非原目标抓取探针|", "|---|---:|---:|---:|---:|"]
    lines.extend(f'|{g}|{v["selected"]}|{v["available_in_explicit_pool"]}|{v["unique_state_hashes"]}|{v["non_goal_scene_grasp_probes"]}|'
                 for g, v in by_group.items())
    lines.extend(["", "运行资产与3550一致：标准benchmark的Python命名空间为libero.libero，原版目录由runtime_config指向liberopro安装下的原版套件。",
                  "未读取任何PRO套件文本；文件读取只来自显式任务映射。", "",
                  "独立确认前须先固定技能卡方式、提示词与验证器。当前只是准备可用状态清单，不能后验选成功样本。",
                  "候选是否在当前视角唯一可见尚待物理启动核对；该缺测必须保留为未验证/基础设施记录，不能静默替换。", "",
                  f'candidate_pool.json SHA256: {file_record(manifest)["sha256"]}',
                  f'original_task_sources.json SHA256: {file_record(task_info)["sha256"]}'])
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"manifest": file_record(manifest), "report": file_record(args.output / "REPORT.md"),
                      "per_group": by_group}, ensure_ascii=False))


if __name__ == "__main__":
    main()
