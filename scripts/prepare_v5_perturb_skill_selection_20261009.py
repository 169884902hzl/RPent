"""Prepare current/near-contact comparisons on fixed original-only layouts."""

import argparse
import copy
import json
from pathlib import Path

from prepare_expert_remote_resume_20261008 import dump, ref


def public_name(symbol):
    from robots.libero.v5_oracle_policy import _kind

    if "cabinet" in symbol:
        for region, ordinal in (("top", "top"), ("middle", "middle"), ("bottom", "bottom")):
            if region in symbol:
                return f"cabinet {ordinal} drawer"
    if "microwave" in symbol:
        return "microwave"
    if "stove" in symbol:
        return "stove"
    return _kind(symbol)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--materialized", type=Path, required=True)
    parser.add_argument("--materialized-sha256", required=True)
    parser.add_argument("--base-plan", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--choice-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if ref(args.materialized)["sha256"] != args.materialized_sha256:
        raise ValueError("materialized pool changed")
    materialized = json.loads(args.materialized.read_text())
    rows = materialized["rows"]
    if any(r["permanent_training_exclusion"] for r in rows):
        raise ValueError("selection cannot consume confirmation states")
    prepared = [row for row in rows if row["status"] == "prepared"]
    if len(prepared) < 100:
        raise ValueError("fewer than100 valid original layouts; materialize registered reserves first")
    prepared = prepared[:100]
    base_plan = json.loads(args.base_plan.read_text())
    base = {**base_plan["budget"], "libero_type": "standard", "suite": "libero_spatial",
            "task": 0, "seed": 0, "provider": "oracle", "motion_trace_v1": True}
    args.output.mkdir(parents=True, exist_ok=False)
    base_ref = dump(args.output / "base_config.json", base)
    common = {"dual_view_fusion_v1": True, "measured_action_receipts_v1": True,
              "skill_budget_v1": True, "task_completion_receipts_v1": True}
    conditions = {
        "current160": {"executor": "current", "max_chunks": 160, "overrides": common},
        "wrist_near_contact160": {"executor": "current", "max_chunks": 160,
            "overrides": {**common, "grasp_category_profiles_v1": False,
                          "grasp_safe_approach_v2": True, "grasp_approach_v1": False,
                          "wrist_refine_v1": True, "wrist_measurement_standoff_v2": True,
                          "wrist_geometry_prompt_v3": True, "grasp_lift_check_v2": True}},
    }
    # Grasp compares the existing category method with measured near-contact
    # execution. Other skills start with their current method for diagnosis.
    if rows[0]["rule"]["skill"] != "grasp":
        conditions = {"current160": conditions["current160"]}
        if rows[0]["rule"]["skill"] == "vla_subtask":
            conditions["current160"]["executor"] = "vla_subtask"
    cases = []
    for row in prepared:
        raw = json.loads(Path(row["registered_layout_state"]["path"]).read_text())
        if ref(Path(row["registered_layout_state"]["path"]))["sha256"] != row["registered_layout_state"]["sha256"]:
            raise ValueError("prepared reset changed")
        skill = row["rule"]["skill"]
        goal = row["skill_goal"]
        mode = ("direct" if skill == "grasp" else row["rule"]["category"].split("_",1)[1]
                if skill == "articulate" else goal[0])
        prompt = (row["original_instruction"] if not row["changed_goal"] else
                  f"put the {row['source_category']} {mode} the {public_name(goal[2])}")
        spec = {"episode": row["episode"], "state_sha256": row["state_sha256"],
                "registered_layout_state": row["registered_layout_state"],
                "kind": "grasp_then_subtask" if skill == "vla_subtask" else skill,
                "type": skill + "_" + row["rule"]["category"].replace(" ", "_"),
                "mode": mode, "object_symbol": row["source_symbol"],
                "object_category": public_name(row["source_symbol"]),
                "bddl": row["bddl"], "init_file": row["init_file"],
                "subtask_prompt": prompt, "original_instruction": row["original_instruction"],
                "changed_goal": row["changed_goal"], "layout_seed": row["layout_seed"],
                "confirmation": False, "training_allowed": False,
                "setup": [], "private_metadata_use": "original diagnostic binding and labels only"}
        if skill in ("vla_subtask", "place"):
            spec.update(target_symbol=goal[2], target_category=public_name(goal[2]))
        if skill == "place":
            spec["setup"] = [{"tool": "grasp", "object_symbol": row["source_symbol"],
                              "object_category": row["source_category"], "mode": "direct"}]
        for condition in conditions:
            cases.append({**copy.deepcopy(spec), "name": row["name"] + "_" + condition,
                          "condition": condition})
    source = args.source.resolve(strict=True)
    adapter = args.adapter.resolve(strict=True)
    producer_refs = [ref(Path(__file__)), ref(adapter / "scripts/probe_v5_perturb_skill_20261009.py")]
    source_meta = json.loads((source / "source_snapshot.json").read_text())
    plan = {"version": "original-perturbed-skills/1", "cohort": "selection",
            "cases": cases, "conditions": conditions, "base_config": base_ref,
            "choice_package": str(args.choice_package.resolve(strict=True)),
            "producer": ref(Path(__file__)), "producer_dependencies": producer_refs,
            "references": [ref(args.materialized), ref(args.base_plan)],
            "source_path": str(source), "adapter_path": str(adapter),
            "source_commit": source_meta["commit"], "source_snapshot": source_meta,
            "new_training_rows": 0, "qualification_authorized": False,
            "confirmation": False, "training_allowed": False,
            "layout_states": len(prepared),
            "invalid_preparations": sum(row["status"] != "prepared" for row in rows),
            "valid_unselected_reserves": sum(row["status"] == "prepared" for row in rows)-len(prepared),
            "invalid_preparations_retained": True, "PRO_files_read": False,
            "policy_outcomes_used_for_selection": False, "max_chunks": 160,
            "purpose": "perturbed original-scene skill selection; development, not qualification"}
    out = dump(args.output / "selection.json", plan)
    print(json.dumps({"manifest": out, "planned_skill_attempts": len(cases),
                      "unique_layouts": len(prepared),
                      "invalid_preparations": plan["invalid_preparations"]}))


if __name__ == "__main__":
    main()
