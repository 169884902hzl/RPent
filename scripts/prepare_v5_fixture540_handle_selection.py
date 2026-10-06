"""Register a separate measured-handle method selection from a pinned pool."""

import argparse
from collections import Counter
import copy
import json
from pathlib import Path

from scripts.prepare_v5_skill535_articulate_place_confirmation import identity, load_pinned


TYPES = ("drawer_open", "drawer_close", "microwave_open", "microwave_close",
         "stove_turn_on", "stove_turn_off")
GEOMETRY_FLAGS = (
    "fixture_handle_geometry_v3", "fixture_drawer_clouds_v2", "fixture_endpoint_geometry_v3",
    "microwave_door_cloud_v6", "door_point_recall_v7", "door_plane_consensus_v1",
    "fixture_part_visibility_v2", "fixture_part_prompt_v1", "selected_fixture_target_v1",
    "articulate_verification_v2", "articulate_view_retreat_v1",
    "microwave_recall_geometry_v3", "microwave_instance_geometry_v4",
    "stove_rgbd_verification_v1", "appliance_support_crop_v5",
    "instruction_queries_v1", "wrist_recall_v1",
)


def build_selection(parent, parent_file, per_type, producer):
    if parent.get("cohort") != "selection" or parent.get("qualification_authorized") is not False:
        raise ValueError("a pinned method-selection parent is required")
    if per_type < 1:
        raise ValueError("per-type must be positive")
    condition = copy.deepcopy(parent["conditions"]["current160"])
    condition.update(executor="current", contact_approach="measured_fixture_handle",
                     contact_standoff_m=.15, contact_prompt_source="registered_original_subtask",
                     observation_pose_v1=True)
    condition.setdefault("overrides", {}).update({flag: True for flag in GEOMETRY_FLAGS})
    condition["overrides"]["dual_view_fusion_v1"] = True
    rows = []
    for label in TYPES:
        candidates = [row for row in parent["cases"]
                      if row["type"] == label and row["condition"] == "current160"]
        if len(candidates) < per_type:
            raise ValueError(f"parent has fewer than {per_type} cases for {label}")
        for row in candidates[:per_type]:
            row = copy.deepcopy(row)
            if row["kind"] != "articulate" or not row.get("subtask_prompt"):
                raise ValueError("registered original articulation prompt is required")
            row["condition"] = "measured_fixture_handle160"
            row["name"] = row["name"].removesuffix("_current160") + "_measured_fixture_handle160"
            rows.append(row)
    plan = copy.deepcopy(parent)
    plan.update(version="original-libero90-fixture540-handle-selection/1", cases=rows,
                purpose="measured RGB-D handle preapproach method selection; no qualification or training",
                parent_manifest=parent_file, producer=producer,
                conditions={"measured_fixture_handle160": condition},
                confirmation="selection only; disjoint original states required for qualification",
                pairing="registered first states from the same parent task/init pool; original arms unchanged",
                preregistered_requests_by_type_arm=dict(Counter(
                    f"{row['type']}/{row['condition']}" for row in rows)))
    reservations = plan.setdefault("access_reservations", {})
    reservations.setdefault("inputs", []).append({**parent_file, "role": "parent_selection"})
    reservations["selected_unique_state_sha"] = len({r["state_sha256"] for r in rows})
    plan.setdefault("metrics", {}).update(
        articulate_success="private requested joint endpoint after first attempt; before/after and already-satisfied strata reported separately",
        newly_achieved_endpoint="requested=false before, opposite=true before, requested=true after; no label-dependent control or replacement",
        full_task_solved="context only; never substitute original full-task solved() for single-skill joint success",
        qualification="none; this smoke/selection cannot admit a skill recipe",
    )
    plan["measured_handle_scope"] = {
        "sources": ["agentview_RGB-D", "wrist_RGB-D"],
        "missing_handle": "unmeasured; no simulated handle or successful-label routing",
        "protocol": "measure handle and front direction; safe preapproach; wrist refinement; original subtask contact",
        "stove_knob_method": "current RGB-D panel/knob measurement; actual support and direction must be checked by the development smoke",
    }
    return plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--parent-manifest-sha256", required=True)
    parser.add_argument("--per-type", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"output must be new: {output}")
    parent, parent_file = load_pinned(args.parent_manifest, args.parent_manifest_sha256)
    plan = build_selection(parent, parent_file, args.per_type, identity(Path(__file__)))
    output.mkdir(parents=True, exist_ok=False)
    manifest = output / "fixtures_measured_handle_selection.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    registration = {"manifest": identity(manifest), "producer": plan["producer"],
                    "cohort": "selection", "cases": len(plan["cases"]),
                    "qualification_authorized": False, "new_training_rows": 0,
                    "counts": plan["preregistered_requests_by_type_arm"]}
    (output / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    print(json.dumps(registration, indent=2))


if __name__ == "__main__":
    main()
