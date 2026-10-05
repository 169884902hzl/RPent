"""Explain fixed moka prefixes using saved measured evidence; keep verdicts."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def volume(obj, eef):
    if not obj or not obj.get("visible") or eef is None:
        return None
    return bool(all(obj["lower"][i] - .04 <= eef[i] <= obj["upper"][i] + .04
                    for i in (0, 1))
                and obj["lower"][2] - .03 <= eef[2] <= obj["upper"][2] + .15)


def frame_evidence(frame):
    before, after = frame.get("before"), frame.get("after")
    main = frame.get("initial_agentview_after", after if frame.get("camera") == "agentview" else None)
    out = {key: frame.get(key) for key in (
        "camera", "gripper_opening", "passes_lower_rise_and_aperture", "measured_at_gripper", "eef_xyz")}
    out.update(after_visible=bool(after and after.get("visible")),
               after_src=after.get("src") if after else None,
               after_source_step=after.get("source_step") if after else None,
               before_source_step=before.get("source_step") if before else None,
               main_visible=bool(main and main.get("visible")),
               main_at_gripper=volume(main, frame.get("eef_xyz")))
    for label, measured in (("selected", after), ("initial_agentview", main)):
        if measured and before:
            out[label + "_lower_rise_m"] = measured["lower"][2] - before["lower"][2]
            out[label + "_centre_rise_m"] = measured["xyz"][2] - before["xyz"][2]
            out[label + "_bounds"] = {key: measured[key] for key in ("xyz", "lower", "upper")}
            out[label + "_extent_m"] = [measured["upper"][i] - measured["lower"][i] for i in range(3)]
    return out


def explain(row):
    truth, visual = row["true_sustained_grasp"], row["visual_verified"]
    assert isinstance(truth, bool) and isinstance(visual, bool)
    confusion = "TP" if truth and visual else "FN" if truth else "FP" if visual else "TN"
    stable = row.get("stable_visual_grasp") or {}
    frames = [frame_evidence(frame) for frame in stable.get("frames", [])]
    tags = []
    if confusion == "FN":
        if not frames:
            primary = "no_verification_frames:" + str(stable.get("unverified_reason"))
        elif all(not frame["after_visible"] for frame in frames):
            primary = "both_verification_frames_have_no_current_visible_measurement"
        elif any(not frame["after_visible"] for frame in frames):
            primary = "one_verification_frame_has_no_current_visible_measurement"
        elif any(frame.get("selected_lower_rise_m", 0) < .03 for frame in frames):
            primary = "fresh_visible_lower_extent_rise_below3cm"
        elif any(frame.get("measured_at_gripper") is False for frame in frames):
            primary = "fresh_visible_object_outside_registered_gripper_volume"
        else:
            primary = "other_saved_verifier_condition"
        if any(frame["main_visible"] and frame["main_at_gripper"] is False for frame in frames):
            tags.append("agentview_visible_but_gripper_volume_rejected")
        if any(frame["main_visible"] and not frame["after_visible"] for frame in frames):
            tags.append("wrist_fallback_has_no_current_visible_measurement_after_agentview_detection")
        if any(frame["after_src"] == "perception_cached" for frame in frames):
            tags.append("selected_fallback_is_cached_not_fresh")
    else:
        primary = "not_false_negative"
    checks = (row.get("sustained_hold") or {}).get("truth", {}).get("checks", [])
    actual_failures = {
        "collision_clearance": any(check["clearance_m"] < .03 for check in checks),
        "finger_support": any(not check["finger_contact"] for check in checks),
        "original_support_contact": any(check["touching_original_support"] for check in checks),
    }
    final = row.get("final_private_contact") or {}
    name = final.get("selected_symbol")
    initial = (row.get("initial_private_reference") or {}).get("objects", {}).get(name)
    body = final.get("objects", {}).get(name)
    displacement = [body["xyz"][i] - initial["xyz"][i] for i in range(3)] if body and initial else None
    return {"case": row["case"]["name"], "condition": row["case"]["condition"],
            "truth_unchanged": truth, "visual_unchanged": visual, "confusion": confusion,
            "fn_primary": primary, "fn_overlapping_tags": tags, "frames": frames,
            "saved_unverified_reason": stable.get("unverified_reason"),
            "final_hold_failed_conditions": actual_failures,
            "final_hold_min_clearance_m": (row.get("sustained_hold") or {}).get("truth", {}).get("min_clearance_m"),
            "final_body_origin_displacement_m": displacement,
            "contact_prompt": row.get("contact_prompt"),
            "public_min_gripper_opening_m": (row.get("rpent_pick_result") or {}).get("min_gripper_opening"),
            "public_final_gripper_opening_m": (row.get("rpent_pick_result") or {}).get("final_gripper_opening"),
            "stage_rejection": (row.get("first_receipt") or {}).get("failure_reason"),
            "phase_snapshots_available": bool(row.get("private_phase_snapshots")),
            "causal_limit": "Missing detections do not prove occlusion; final hold is later than visual frames."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed-summary", type=Path, required=True)
    parser.add_argument("--previous-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    summary = json.loads(args.fixed_summary.read_text())
    rows, identity = [], []
    for source in summary["sources"]:
        path = Path(source["captured_path"])
        assert digest(path) == source["prefix_sha256"]
        captured = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(captured) == 30
        rows.extend(map(explain, captured))
        identity.append({"path": str(path), "sha256": digest(path), "rows": len(captured)})
    by_arm = defaultdict(list)
    for row in rows:
        by_arm[row["condition"]].append(row)
    arms = []
    for condition, members in sorted(by_arm.items()):
        fn = [row for row in members if row["confusion"] == "FN"]
        arms.append({"condition": condition, "rows": len(members),
            "fn_primary": dict(Counter(row["fn_primary"] for row in fn)),
            "fn_overlapping_tags": dict(Counter(tag for row in fn for tag in row["fn_overlapping_tags"])),
            "all_contact_prompts": dict(Counter(row["contact_prompt"] for row in members)),
            "stage_rejection_counts": dict(Counter(row["stage_rejection"] for row in members if row["stage_rejection"])),
            "fp_final_failed_conditions": dict(Counter(key for row in members if row["confusion"] == "FP"
                                                     for key, value in row["final_hold_failed_conditions"].items() if value)),
            "fn_cases": [row["case"] for row in fn]})
    previous = json.loads(args.previous_summary.read_text())
    report = {"scope": "saved fixed first30 moka evidence only; verdicts unchanged", "inputs": identity,
              "fixed_summary": {"path": str(args.fixed_summary), "sha256": digest(args.fixed_summary)},
              "previous_summary": {"path": str(args.previous_summary), "sha256": digest(args.previous_summary)},
              "previous_full_exploration": [{"condition": arm["condition"], "recorded": arm["recorded"],
                  "true_success": arm["true_success"], "confusion": arm["confusion"]}
                  for arm in previous["by_condition"]], "arms": arms,
              "fn_improvement_claim": "Reset FN rate descriptively changed 13/50 to4/21, but prefix, policy prompt and verifier differ; no paired improvement established.",
              "public_verifier_recommendations": [
                  "Record each fresh agentview and wrist detection independently; a missing fallback must not overwrite visible prior evidence.",
                  "When both views miss a truly held object, reacquire with a measured camera/arm recovery; cached geometry does not verify lift.",
                  "Audit gripper volume in gripper orientation with measured object bounds; do not fit per-task margins to these labels.",
                  "Keep the two fresh stable frames and sustained-hold validation; do not convert missing evidence to success.",
                  "Current FN evidence is mainly missing measurements, not fresh lower-extent drift; saved images/masks are needed to attribute occlusion."],
              "new_physics_trials": 0, "new_training_rows": 0, "confirmation_eligible": False,
              "runtime_changed": False, "old_ledgers_changed": False,
              "script_sha256": digest(Path(__file__))}
    args.output.mkdir(parents=True)
    (args.output / "geometry_summary.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "geometry_trials.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    print(json.dumps({"arms": arms, "summary_sha256": digest(args.output / "geometry_summary.json"),
                      "trials_sha256": digest(args.output / "geometry_trials.jsonl")}))


if __name__ == "__main__":
    main()
