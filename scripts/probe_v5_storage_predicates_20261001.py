# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare original storage-region predicates with their articulated fixtures.

This CPU diagnostic never renders, selects a skill, or writes training rows.
Joint values remain private diagnostic evidence, outside planner observations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from libero.libero import benchmark, get_libero_path
    from libero.libero.envs.bddl_utils import robosuite_parse_problem
    from libero.libero.envs.env_wrapper import ControlEnv

    from robots.libero.v5_branch_state import storage_open

    records = []
    for suite_name in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
        suite = benchmark.get_benchmark(suite_name)()
        for task_id in range(10):
            task = suite.get_task(task_id)
            bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
            goals = robosuite_parse_problem(str(bddl))["goal_state"]
            regions = list(dict.fromkeys(
                goal[2] for goal in goals
                if goal[0] == "in" and len(goal) == 3
                and any(word in goal[2] for word in ("cabinet", "drawer", "microwave"))
            ))
            if not regions:
                continue
            wrapper = ControlEnv(str(bddl), has_renderer=False,
                                 has_offscreen_renderer=False, use_camera_obs=False)
            try:
                wrapper.env.reset()
                for init in range(5):
                    wrapper.set_state(suite.get_task_init_states(task_id)[init])
                    wrapper.sim.forward()
                    for region in regions:
                        state = wrapper.env.object_states_dict[region]
                        parent = getattr(state, "parent_name", region)
                        site = wrapper.env.object_sites_dict.get(region)
                        joints = wrapper.env.get_object(parent).joints
                        qpos = {joint: float(wrapper.sim.data.qpos[
                            wrapper.sim.model.get_joint_qpos_addr(joint)
                        ]) for joint in joints}
                        row = {
                            "suite": suite_name, "task": task_id, "init": init,
                            "bddl_sha256": hashlib.sha256(bddl.read_bytes()).hexdigest(),
                            "region": region, "parent": parent,
                            "region_joints": None if site is None else site.joints,
                            "parent_joints": joints, "parent_joint_qpos": qpos,
                            "region_open": bool(wrapper.env._eval_predicate(["open", region])),
                            "parent_open": bool(wrapper.env._eval_predicate(["open", parent])),
                            "corrected_storage_open": storage_open(wrapper, region),
                        }
                        records.append(row)
                        print(json.dumps(row), flush=True)
            finally:
                wrapper.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "purpose": "original-only CPU storage predicates; no rendering, actions, or labels",
        "records": records,
        "region_parent_disagreements": sum(r["region_open"] != r["parent_open"] for r in records),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
