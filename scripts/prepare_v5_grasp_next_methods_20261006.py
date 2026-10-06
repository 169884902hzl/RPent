# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Prepare explicit original-state pan verification and paired moka methods."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path

CHOICE_FILES = ("tokenizer_config.json", "tokenizer.json", "merges.txt", "vocab.json",
                "schema_config.json", "parallel_schema.py")


def identity(path):
    path = path.resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def state_case(row, group, category, condition, index, repetition):
    ep = row["episode"]
    return {**copy.deepcopy(row), "group": group, "category": category,
            "original_goal_source": True,
            "source": "official_original_LIBERO90", "official_init_index": ep["seed"],
            "state_hash_encoding": "C contiguous little endian float64",
            "instruction": row["original_instruction"], "condition": condition,
            "trial_index": index, "initial_state_repetition": repetition,
            "requires_current_visible_unique_binding": True,
            "name": f'{group}_{ep["suite"]}_t{ep["task"]}_s{ep["seed"]}_r{repetition}_{condition}'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pan-parent", type=Path, required=True)
    parser.add_argument("--moka-parent", type=Path, required=True)
    parser.add_argument("--access-pools", type=Path, required=True)
    parser.add_argument("--robot-calibration", type=Path, required=True)
    parser.add_argument("--exclude-manifest", type=Path, action="append", required=True)
    parser.add_argument("--libero-config-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("use a new output directory")
    pan = json.loads(args.pan_parent.read_text())
    moka = json.loads(args.moka_parent.read_text())
    pools = json.loads(args.access_pools.read_text())
    calibration = json.loads(args.robot_calibration.read_text())
    if calibration.get("runtime_object_truth_used") is not False:
        raise ValueError("sensor calibration must not contain runtime object truth")
    excluded, exclusions = set(), []
    for path in args.exclude_manifest:
        exclusions.append(identity(path))
        plan = json.loads(path.read_text())
        excluded.update(case["state_sha256"] for case in plan["cases"] if case.get("state_sha256"))
    os.environ["LIBERO_TYPE"] = "standard"
    os.environ["LIBERO_CONFIG_PATH"] = str(args.libero_config_path.resolve(strict=True))
    import numpy as np
    from libero.libero.envs.bddl_utils import robosuite_parse_problem
    from rlinf.envs.libero.utils import benchmark

    suite = benchmark.get_benchmark("libero_90")()
    states, metadata = {}, {}

    def fresh_rows(group, *, only_task=None):
        selected, seen = [], set()
        for row in sorted(pools[group], key=lambda r: (r["episode"]["seed"], r["episode"]["task"])):
            ep = row["episode"]
            if ep["suite"] != "libero_90" or (only_task is not None and ep["task"] != only_task):
                continue
            if row.get("visited") or row.get("reserved_by_explicit_prior_plan"):
                continue
            digest = row["state_sha256"]
            if digest in excluded or digest in seen:
                continue
            for key in ("bddl", "init_file"):
                if identity(Path(row[key]["path"]))["sha256"] != row[key]["sha256"]:
                    raise ValueError("registered original asset changed")
            if ep["task"] not in states:
                task = suite.get_task(ep["task"])
                if task.problem_folder != "libero_90":
                    raise ValueError("non-original task folder")
                states[ep["task"]] = suite.get_task_init_states(ep["task"])
                metadata[ep["task"]] = robosuite_parse_problem(row["bddl"]["path"])
            state = np.asarray(states[ep["task"]][ep["seed"]], dtype="<f8", order="C")
            if hashlib.sha256(state.tobytes()).hexdigest() != digest:
                raise ValueError("registered official state changed")
            problem = metadata[ep["task"]]
            goal_symbol = "moka_pot_1" if group == "moka_pot" else "chefmate_8_frypan_1"
            if not any(len(g) >= 2 and g[1] == goal_symbol for g in problem["goal_state"]):
                continue
            instruction = " ".join(problem["language_instruction"])
            if instruction != row["original_instruction"]:
                raise ValueError("registered original BDDL sentence changed")
            row = copy.deepcopy(row)
            row["private_original_goal_predicates"] = problem["goal_state"]
            selected.append(row)
            seen.add(digest)
        return selected

    pan_rows = fresh_rows("frypan")[:100]
    moka_rows = fresh_rows("moka_pot", only_task=19)
    if not pan_rows or not moka_rows:
        raise ValueError("no unused explicit original states remain")

    retry_policy = {"same_state_retries": 1, "maximum_infrastructure_failure_rate": .02,
                    "rate_denominator": "all registered cases in this manifest",
                    "physical_failures_retried": False, "failure_ledger": "infrastructure_attempts.jsonl"}
    outputs = {}
    for label, source in (("pan_wrist_new_states", pan), ("moka_methods_selection", moka)):
        plan = copy.deepcopy(source)
        base = identity(Path(plan["base_config"]["path"]))
        if base["sha256"] != plan["base_config"]["sha256"]:
            raise ValueError("registered base config changed")
        plan.update(base_config=base, choice_package_files=[identity(Path(plan["choice_package"]) / name)
                    for name in CHOICE_FILES], qualification_authorized=False, new_training_rows=0,
                    access_pool=identity(args.access_pools), explicit_state_exclusions=exclusions,
                    infrastructure_retry_policy=retry_policy,
                    selection="Explicit original-state metadata order; no outcome filtering or state replacement",
                    private_goal_input_policy="Predicates in private case provenance and status evidence only; policy gets the original public sentence")
        if label == "pan_wrist_new_states":
            condition = copy.deepcopy(next(iter(source["conditions"].values())))
            if condition.get("contact_verification") != "stable_lower_gripper_wrist":
                raise ValueError("pan confirmation must retain the registered wrist two-frame verifier")
            condition["contact_verification"] = "stable_independent_views_bound_handle"
            condition["overrides"].update(dual_view_fusion_v1=True, grasp_independent_views_v1=True,
                                           grasp_measurement_calibration=calibration)
            plan.update(groups=["frypan"], cohort="independent_new_original_states_pan_wrist_verifier",
                        conditions={"pan_wrist_confirmation": condition},
                        cases=[state_case(r, "frypan", "frypan", "pan_wrist_confirmation", i, 0)
                               for i, r in enumerate(pan_rows)],
                        confirmation_gap={"requested_unique_states": 100, "available_unique_states": len(pan_rows),
                                          "missing_unique_states": max(0, 100 - len(pan_rows))},
                        public_verifier_new_intervention="Independent current views, target-bound visible handle acquisition, calibrated finger frame, measured original support clearance and two fresh captures after 10 public hold steps; old lift/opening thresholds remain registered",
                        robot_calibration_file=identity(args.robot_calibration),
                        frozen_recipe=None, qualification=False,
                        measurement_target="Both sustained physical grasp and public verifier confusion; full six-class gate remains separate")
        else:
            base_condition = copy.deepcopy(next(iter(source["conditions"].values())))
            wrist = copy.deepcopy(base_condition)
            wrist.update(profile="high_short", contact_standoff_m=.10, contact_approach="bounds_centre")
            wrist["overrides"].update(wrist_refine_v1=True, wrist_measurement_standoff_v2=True,
                                     dual_view_fusion_v1=True, grasp_approach_v1=False)
            yaw = copy.deepcopy(base_condition)
            yaw.update(profile="high_short", contact_standoff_m=.10, contact_approach="measured_handle")
            yaw["overrides"].update(dual_view_fusion_v1=True, grasp_approach_v1=True,
                                   handle_free_yaw_v2=False, wrist_position_hold_v1=True)
            full = copy.deepcopy(base_condition)
            full.update(profile="start_full", contact_execution="original_subtask", contact_stop="chunk_budget")
            full["overrides"].update(native_grasp_stop_v1=True, dual_view_fusion_v1=True)
            full.pop("contact_prompt_binding", None)
            full.pop("full_prompt_binding", None)
            conditions = {"moka_wrist_refine": wrist, "moka_fused_handle_yaw": yaw,
                          "moka_original_complete_subtask": full}
            cases = []
            for index in range(100):
                row = moka_rows[index % len(moka_rows)]
                repetition = index // len(moka_rows)
                for name in conditions:
                    cases.append(state_case(row, "moka_pot", "moka pot", name, index, repetition))
            plan.update(groups=["moka_pot"], cohort="original_moka_task19_method_selection_correlated_resets",
                        conditions=conditions, cases=cases,
                        selection_gap={"requested_independent_states_per_method": 100,
                                       "available_independent_states": len(moka_rows),
                                       "missing_independent_states": max(0, 100 - len(moka_rows)),
                                       "registered_reset_trials_per_method": 100,
                                       "repeated_reset_trials_per_method": max(0, 100 - len(moka_rows))},
                        repetition_policy="Repeated diagnostic resets retain repetition identity and are correlated; not independent confirmation",
                        first_attempts_per_condition_group=100,
                        frozen_recipe=None, qualification=False,
                        private_goal_metrics="official_subtask_success/private_original_task_status before-after only for complete task; sustained grasp is separate",
                        original_subtask_provenance={"task": 19, "sentence": moka_rows[0]["original_instruction"],
                            "bddl": moka_rows[0]["bddl"], "private_predicates": moka_rows[0]["private_original_goal_predicates"]})
        outputs[label] = plan
    args.output.mkdir(parents=True, exist_ok=False)
    records = {}
    for label, plan in outputs.items():
        path = args.output / (label + ".json")
        path.write_text(json.dumps(plan, indent=2) + "\n")
        records[label] = {**identity(path), "cases": len(plan["cases"]),
                          "gap": plan.get("confirmation_gap", plan.get("selection_gap"))}
    registration = {"producer": identity(Path(__file__)), "manifests": records,
                    "new_training_rows": 0, "qualification_authorized": False,
                    "no_physics_executed": True}
    (args.output / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    print(json.dumps(registration, indent=2))


if __name__ == "__main__":
    main()
