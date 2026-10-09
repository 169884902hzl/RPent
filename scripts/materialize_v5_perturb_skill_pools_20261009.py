"""Bind preregistered layouts to original tasks and save private reset bytes.

This CPU preparation never runs a policy, opens a PRO task or scores a skill.
Invalid layouts remain in the ledger. Only prepared selection states may be
used for method development; confirmation states stay permanently held out.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

from prepare_expert_remote_resume_20261008 import dump, ref


def digest_state(state):
    import numpy as np

    return hashlib.sha256(np.asarray(state, dtype="<f8", order="C").tobytes()).hexdigest()


def coarse_category(symbol):
    value = symbol.lower()
    for key, needles in (
        ("moka pot", ("moka",)), ("frypan", ("frypan", "frying_pan")),
        ("cup", ("mug", "cup")), ("bowl", ("bowl", "ramekin")),
        ("bottle", ("bottle", "ketchup", "dressing", "bbq")),
        ("box", ("box", "cream_cheese", "butter", "pudding", "milk")),
    ):
        if any(word in value for word in needles):
            return key
    return None


def original_catalog():
    """Read only the explicitly allowed original training suites."""
    from rlinf.envs.libero.utils import benchmark
    from libero.libero import get_libero_path
    from libero.libero.envs.bddl_utils import robosuite_parse_problem
    from robots.libero.v5_runtime import category

    catalog, suites = [], {}
    for name in ("libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"):
        suite = suites[name] = benchmark.get_benchmark(name)()
        for task_id in range(suite.n_tasks):
            task = suite.get_task(task_id)
            bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
            init = Path(get_libero_path("init_states")) / task.problem_folder / task.init_states_file
            parsed = robosuite_parse_problem(str(bddl))
            objects = sorted(symbol for symbols in parsed["objects"].values() for symbol in symbols)
            goals = parsed["goal_state"]
            trials = len(suite.get_task_init_states(task_id))
            for source in objects:
                matching = [g for g in goals if len(g) == 3 and g[1] == source and g[0] in ("on", "in")]
                if coarse_category(source) is not None:
                    catalog.append({"suite": name, "task": task_id, "source": source,
                                    "coarse_category": coarse_category(source), "category": category(source),
                                    "objects": objects, "goals": matching, "all_goals": goals,
                                    "regions": parsed["regions"], "trials": trials,
                                    "instruction": task.language, "bddl": ref(bddl), "init_file": ref(init)})
            for goal in goals:
                if goal[0] not in ("open", "close", "turnon", "turnoff"):
                    continue
                symbol = goal[1]
                family = ("drawer" if "cabinet" in symbol else "microwave" if "microwave" in symbol
                          else "stove" if "stove" in symbol else None)
                if family is None:
                    continue
                mode = {"turnon": "turn_on", "turnoff": "turn_off"}.get(goal[0], goal[0])
                catalog.append({"suite": name, "task": task_id, "source": symbol,
                                "fixture_type": family + "_" + mode, "category": category(symbol),
                                "mode": mode, "objects": objects, "goals": [goal], "all_goals": goals,
                                "regions": parsed["regions"], "trials": trials,
                                "instruction": task.language, "bddl": ref(bddl), "init_file": ref(init)})
    return sorted(catalog, key=lambda r: (r["suite"], r["task"], r["source"])), suites


def eligible(catalog, skill, category):
    if skill == "articulate":
        return [r for r in catalog if r.get("fixture_type") == category]
    if skill == "place":
        return [r for r in catalog if any(g[0] == category for g in r["goals"])]
    return [r for r in catalog if r.get("coarse_category") == category
            and (skill == "grasp" or r["goals"])]


def transformed_pose(pose, delta, yaw):
    import numpy as np

    result = np.array(pose, dtype=float, copy=True)
    result[:2] += delta
    w, x, y, z = result[3:]
    c, s = math.cos(math.radians(yaw) / 2), math.sin(math.radians(yaw) / 2)
    result[3:] = c*w-s*z, c*x-s*y, c*y+s*x, c*z+s*w
    return result


def materialize(wrapper, states, scene, declared, attempt_index, output):
    import numpy as np

    rule = declared["rule"]
    state_index = attempt_index % len(states)
    state = np.asarray(states[state_index], dtype="<f8", order="C")
    wrapper.set_init_state(state)
    if not np.allclose(wrapper.get_sim_state(), state, atol=1e-8, rtol=0):
        raise ValueError("official base did not restore exactly")
    env, sim = wrapper.env, wrapper.sim
    for robot in env.robots:
        for controller in robot.part_controllers.values():
            controller.update(force=True)
            controller.reset_goal()
    before = np.array(sim.data.qpos)
    velocities = np.array(sim.data.qvel)
    free = sorted(name for name, obj in env.objects_dict.items()
                  if len(obj.joints) == 1 and np.asarray(sim.data.get_joint_qpos(obj.joints[0])).shape == (7,))
    moved = ([scene["source"]] if scene["source"] in free else free[:1])
    if rule["layout"] == "swap_two_free_objects" and len(free) >= 2:
        first = moved[0]
        second = next(name for name in free if name != first)
        a, b = (np.array(sim.data.get_joint_qpos(env.objects_dict[name].joints[0]))
                for name in (first, second))
        a[:2], b[:2] = b[:2].copy(), a[:2].copy()
        # Apply the already declared seeded transform after swapping. Without
        # it, both pools would recreate identical swaps of the same base init.
        a = transformed_pose(a, rule["xy_translation_m"], rule["world_yaw_delta_deg"])
        sim.data.set_joint_qpos(env.objects_dict[first].joints[0], a)
        sim.data.set_joint_qpos(env.objects_dict[second].joints[0], b)
        moved = [first, second]
    elif moved:
        obj = env.objects_dict[moved[0]]
        pose = transformed_pose(sim.data.get_joint_qpos(obj.joints[0]),
                                rule["xy_translation_m"], rule["world_yaw_delta_deg"])
        sim.data.set_joint_qpos(obj.joints[0], pose)
    else:
        return {"status": "invalid_layout", "reason": "no_unattached_object_to_perturb"}
    sim.forward()
    proposed = np.asarray(wrapper.get_sim_state(), dtype="<f8", order="C")
    action = np.zeros(7)
    action[-1] = -1
    for _ in range(rule["settle_steps"]):
        wrapper.step(action)
    # Neutral settling must not change the policy's initial arm posture.
    robot = env.robots[0]
    robot_pos = list(robot._ref_joint_pos_indexes)
    robot_vel = list(robot._ref_joint_vel_indexes)
    for values in robot._ref_gripper_joint_pos_indexes.values():
        robot_pos.extend(values)
    for values in robot._ref_gripper_joint_vel_indexes.values():
        robot_vel.extend(values)
    sim.data.qpos[robot_pos] = before[robot_pos]
    sim.data.qvel[robot_vel] = velocities[robot_vel]
    sim.forward()
    geometry = {name: sim.data.body_xpos[index].tolist() for name, index in env.obj_body_id.items()}
    moved_geoms = {sim.model.geom_name2id(geom) for name in moved
                   for geom in env.objects_dict[name].contact_geoms}
    penetrations = [float(c.dist) for c in sim.data.contact[:sim.data.ncon]
                    if (c.geom1 in moved_geoms or c.geom2 in moved_geoms) and c.dist < -.003]
    settled = np.asarray(wrapper.get_sim_state(), dtype="<f8", order="C")
    invalid = []
    if penetrations:
        invalid.append("penetration_over_3mm")
    if not np.isfinite(settled).all():
        invalid.append("nonfinite_state")
    if any(geometry[name][2] < .5 for name in moved):
        invalid.append("moved_object_fell_outside_table")
    wrapper.set_init_state(settled)
    restore_error = float(np.max(np.abs(np.asarray(wrapper.get_sim_state()) - settled)))
    if restore_error > 1e-8:
        invalid.append("settled_reset_mismatch")
    goals = [g for g in scene["goals"] if len(g) == 3]
    if rule["skill"] == "place":
        goals = [g for g in goals if g[0] == rule["category"]]
    goal = goals[0] if goals else None
    original_goal = goal
    alternatives = []
    if goal and rule["goal_rule"] == "rotate_eligible_on_in_target":
        # Alternative destinations must already be original goal destinations
        # in this scene. Never invent a support/container from PRO metadata.
        alternatives = sorted({g[2] for g in scene["all_goals"]
                               if len(g) == 3 and g[0] == goal[0] and g[2] not in (goal[1], goal[2])})
        if alternatives:
            goal = [goal[0], goal[1], alternatives[attempt_index % len(alternatives)]]
    record = {"episode": {"suite": scene["suite"], "task": scene["task"], "seed": state_index},
              "bddl": scene["bddl"], "init_file": scene["init_file"],
              "base_state_sha256": digest_state(state), "rawstate": settled.tolist(),
              "state_sha256": digest_state(settled), "layout_seed": rule["layout_seed"],
              "source_symbol": scene["source"], "source_category": scene["category"],
              "original_instruction": scene["instruction"], "skill_goal": goal,
              "original_skill_goal": original_goal, "goal_alternatives": alternatives,
              "changed_goal": goal != original_goal, "moved_symbols": moved,
              "rule": rule, "rule_sha256": declared["rule_sha256"],
              "permanent_training_exclusion": declared["permanent_training_exclusion"],
              "restore_error_mixed_state_units": restore_error,
              "preparation_provenance": {"proposed_state_sha256": digest_state(proposed),
                 "settled_state_sha256": digest_state(settled), "settled_geometry": geometry,
                 "geometry_fingerprint": hashlib.sha256(json.dumps(geometry,sort_keys=True).encode()).hexdigest()},
              "status": "invalid_layout" if invalid else "prepared", "invalid_reasons": invalid,
              "private_values_use": "reset preparation and diagnostic labels only",
              "skill_executed": False, "policy_outcomes_read": False, "PRO_files_read": False}
    return {**{k:v for k,v in record.items() if k != "rawstate"},
            "registered_layout_state": dump(output / (declared["name"] + ".json"), record)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--pool-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skill", choices=("grasp", "vla_subtask", "place", "articulate"))
    parser.add_argument("--category")
    parser.add_argument("--exclude-materialized", type=Path, action="append", default=[])
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        raise ValueError("LIBERO_TYPE=standard is required before imports")
    if ref(args.pool)["sha256"] != args.pool_sha256:
        raise ValueError("registered pool changed")
    plan = json.loads(args.pool.read_text())
    declared = [r for r in plan["records"] if (args.skill is None or r["rule"]["skill"] == args.skill)
                and (args.category is None or r["rule"]["category"] == args.category)]
    exclusions = set()
    exclusion_refs = []
    for path in args.exclude_materialized:
        previous = json.loads(path.read_text())
        exclusions.update(row["state_sha256"] for row in previous["rows"] if row.get("state_sha256"))
        exclusion_refs.append(ref(path))
    if plan["split"] == "confirmation" and not exclusion_refs:
        raise ValueError("confirmation preparation requires pinned selection-state exclusions")
    args.output.mkdir(parents=True, exist_ok=False)
    catalog, suites = original_catalog()
    dump(args.output / "original_catalog.json", {"records": catalog, "PRO_files_read": False})
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero.v5_reset_seed import attach_reset_seed
    wrappers, states_cache, rows, seen = {}, {}, [], set()
    try:
        with (args.output / "preparation.jsonl").open("x") as ledger:
            for item in declared:
                started = time.monotonic()
                rule = item["rule"]
                pool = eligible(catalog, rule["skill"], rule["category"])
                index = rule["layout_seed"] % 100
                row = {"name": item["name"], "rule": rule, "rule_sha256": item["rule_sha256"],
                       "permanent_training_exclusion": item["permanent_training_exclusion"]}
                try:
                    if not pool:
                        raise ValueError("no eligible original scene for this cell")
                    scene = pool[index % len(pool)]
                    key = scene["suite"], scene["task"]
                    if key not in wrappers:
                        wrapper = attach_reset_seed(ControlEnv(bddl_file_name=scene["bddl"]["path"],
                            use_camera_obs=False, has_renderer=False, has_offscreen_renderer=False,
                            camera_names=[], ignore_done=True, horizon=10000))
                        wrapper.seed(0)
                        wrapper.reset()
                        wrappers[key] = wrapper
                        states_cache[key] = suites[key[0]].get_task_init_states(key[1])
                    row.update(materialize(wrappers[key], states_cache[key], scene, item, index, args.output))
                    identity = row.get("state_sha256")
                    if identity in seen:
                        row.update(status="invalid_layout", invalid_reasons=[*row.get("invalid_reasons", []),
                                                                              "duplicate_raw_state_in_pool"])
                    if identity in exclusions:
                        row.update(status="invalid_layout", invalid_reasons=[*row.get("invalid_reasons", []),
                                                                              "selection_confirmation_state_overlap"])
                    seen.add(identity)
                except Exception as error:
                    row.update(status="preparation_error", error=repr(error))
                row["wall_s"] = time.monotonic() - started
                ledger.write(json.dumps(row, allow_nan=False) + "\n")
                ledger.flush()
                rows.append(row)
                print(json.dumps({"name": row["name"], "status": row["status"], "wall_s": row["wall_s"]}), flush=True)
    finally:
        for wrapper in wrappers.values():
            wrapper.close()
    from collections import Counter
    counts = dict(Counter(row["status"] for row in rows))
    dump(args.output / "manifest.json", {"pool": ref(args.pool), "generator": ref(Path(__file__)),
         "declared": len(declared), "counts": counts, "rows": rows,
         "skill_executions": 0, "training_allowed": False,
         "confirmation_permanently_excluded_from_training": True,
         "excluded_materialized_pools": exclusion_refs,
         "invalid_states_retained": True, "policy_outcomes_read": False, "PRO_files_read": False})
    if counts.get("preparation_error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
