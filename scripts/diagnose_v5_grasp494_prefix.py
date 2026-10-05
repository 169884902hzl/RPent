"""Capture fixed explicit ledger prefixes and summarize three independent axes.

No new physics or artifact discovery. Registered truth and visual verdicts stay
unchanged; missing phase evidence remains unknown rather than a guessed cause.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def wilson(successes, trials):
    if not trials:
        return None
    z = 1.959963984540054
    p = successes / trials
    scale = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / scale
    radius = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / scale
    return [centre - radius, centre + radius]


def source_prefix(ledger, output, count):
    raw = ledger.read_bytes()
    stamp = datetime.now(timezone.utc).isoformat()
    complete_end = raw.rfind(b"\n") + 1
    closed = raw[:complete_end].splitlines(keepends=True)
    if len(closed) < count:
        raise ValueError(f"need first{count} closed rows; only{len(closed)} available in{ledger}")
    prefix = b"".join(closed[:count])
    filename = output / (ledger.parent.name + "_first" + str(count) + ".jsonl")
    filename.write_bytes(prefix)
    return [json.loads(line) for line in prefix.splitlines()], {
        "original_ledger": str(ledger), "captured_at_utc": stamp,
        "original_read_bytes": len(raw), "original_read_sha256": sha_bytes(raw),
        "complete_rows_present_in_read": len(closed), "incomplete_tail_bytes": len(raw) - complete_end,
        "closed_rows_outside_fixed_prefix": len(closed) - count,
        "prefix_rows": count, "prefix_bytes": len(prefix), "prefix_sha256": sha_bytes(prefix),
        "captured_path": str(filename), "selection": "firstN complete rows in source order; no outcome filtering"}


def read_choices(row):
    path = Path(row["output_dir"]) / "choices.jsonl"
    expected = row.get("choices_sha256")
    if not expected:
        if path.exists():
            raise ValueError("recorded row omits hash for an existing choices file")
        return None, "no_choices_recorded"
    raw = path.read_bytes()
    if sha_bytes(raw) != expected:
        raise ValueError("recorded choices changed")
    choices = [json.loads(line) for line in raw.splitlines()]
    if len(choices) != 1:
        raise ValueError("first-grasp probe must contain one decision")
    return choices[0], "sha256_checked"


def classify(row, choice):
    receipt = row.get("first_receipt") or {}
    primitive = row.get("rpent_pick_result")
    vla = [motion for motion in (choice or {}).get("motion_evidence", []) if motion.get("name") == "vla_act_chunk"]
    chunks = len(row.get("contact_samples", []))
    executed = row.get("executed_vla_actions", 0)
    failure = receipt.get("failure_reason")
    if chunks or executed or any(motion.get("executed_action_count", 0) for motion in vla):
        contact = "contact_executed"
    elif primitive is not None:
        contact = "contact_returned_without_recorded_actions"
    elif failure in ("visible_handle_not_measured", "visible_rim_not_measured", "waypoint_not_reached",
                     "approach_not_reached", "wrist_pose_not_reached") and not row.get("contact_prompt"):
        contact = "contact_not_called_stage_rejected"
    else:
        contact = "contact_phase_unknown"
    truth = row.get("true_sustained_grasp")
    known = isinstance(truth, bool)
    checks = (row.get("sustained_hold") or {}).get("truth", {}).get("checks", [])
    failed_conditions = []
    if checks:
        if any(check["clearance_m"] < .03 for check in checks):
            failed_conditions.append("collision_clearance")
        if any(not check["finger_contact"] for check in checks):
            failed_conditions.append("finger_support")
        if any(check["touching_original_support"] for check in checks):
            failed_conditions.append("original_support_contact")
    if not known:
        physical = "truth_unavailable"
    elif truth:
        physical = "sustained_grasp_success"
    elif contact == "contact_not_called_stage_rejected":
        physical = "stage_rejected_before_contact"
    elif not checks:
        physical = "physical_failure_without_saved_checks"
    elif all(check["finger_contact"] for check in checks) and "collision_clearance" in failed_conditions:
        physical = "finger_supported_but_insufficient_collision_clearance"
    elif any(check["clearance_m"] >= .03 and check["finger_contact"]
             and not check["touching_original_support"] for check in checks):
        physical = "final_hold_conditions_not_sustained"
    elif any(check["clearance_m"] >= .03 for check in checks):
        physical = "clearance_without_sustained_finger_support"
    elif any(check["finger_contact"] for check in checks):
        physical = "finger_contact_without_support_clearance"
    else:
        physical = "no_final_target_lift_or_finger_support"
    visual = row.get("visual_verified") is True
    confusion = "unknown_truth" if not known else ("TP" if truth and visual else "FN" if truth else "FP" if visual else "TN")
    if primitive is None:
        stop = "no_public_contact_stop_record"
    elif primitive["chunks_used"] >= primitive["max_chunks"]:
        stop = "used_last_chunk_success" if primitive["success"] else "budget_stop"
    else:
        stop = "early_public_success" if primitive["success"] else "other_public_stop"
    stable = row.get("stable_visual_grasp") or {}
    frame_flags = Counter()
    for frame in stable.get("frames", []):
        before, after = frame.get("before"), frame.get("after")
        if not after or not after["visible"]:
            frame_flags["missing_visible_measurement"] += 1
        elif before:
            frame_flags["lower_rise_below3cm"] += after["lower"][2] - before["lower"][2] < .03
        if frame.get("measured_at_gripper") is False:
            frame_flags["outside_measured_gripper_volume"] += 1
        frame_flags["saved_frame_pass_false"] += frame.get("passes_lower_rise_and_aperture") is False
    return {"case": row["case"], "choices_sha256": row.get("choices_sha256"),
            "truth_unchanged": truth, "visual_unchanged": visual,
            "physical_primary": physical, "failed_sustained_conditions": failed_conditions,
            "verifier_confusion": confusion, "contact_phase": contact,
            "public_stop_axis": stop, "public_chunks": primitive.get("chunks_used") if primitive else None,
            "public_max_chunks": primitive.get("max_chunks") if primitive else None,
            "public_stop_success_final_truth_false": bool(primitive and primitive["success"] and truth is False),
            "contact_samples": chunks, "executed_vla_actions": executed,
            "stage_rejection_reason": failure, "visual_frame_flags": dict(frame_flags),
            "unverified_reason": stable.get("unverified_reason"),
            "trial_lift_waypoint_reached": (stable.get("trial_lift_motion") or {}).get("waypoint_reached"),
            "infrastructure_or_execution_error": bool(row.get("raised_error")) or receipt.get("verification") == "execution_error",
            "trial_lift_loss_causal_label": "not_identifiable_without_private_phase_snapshots"}


def metrics(rows, expected):
    physical = Counter(row["physical_primary"] for row in rows)
    matrix = Counter(row["verifier_confusion"] for row in rows)
    known = matrix["TP"] + matrix["TN"] + matrix["FP"] + matrix["FN"]
    success = matrix["TP"] + matrix["FN"]
    negative = matrix["TN"] + matrix["FP"]
    contact = Counter(row["contact_phase"] for row in rows)
    stop = Counter(row["public_stop_axis"] for row in rows)
    stop_cross = Counter((row["public_stop_axis"], str(row["truth_unchanged"])) for row in rows)
    return {"planned_full_arm": expected, "recorded_fixed_prefix": len(rows), "known_truth": known,
            "true_success": success, "true_success_rate": success / known if known else None,
            "wilson_95CI": wilson(success, known), "physical_primary_counts": dict(physical),
            "confusion": dict(matrix), "agreement": (matrix["TP"] + matrix["TN"]) / known if known else None,
            "false_positive": {"numerator": matrix["FP"], "denominator": negative,
                               "rate": matrix["FP"] / negative if negative else None},
            "false_negative": {"numerator": matrix["FN"], "denominator": success,
                               "rate": matrix["FN"] / success if success else None},
            "contact_phase_counts": dict(contact), "public_stop_counts": dict(stop),
            "public_stop_vs_physical_truth": [{"stop": kind, "truth": value, "count": count}
                for (kind, value), count in sorted(stop_cross.items())],
            "infrastructure_or_execution_error_rows": sum(row["infrastructure_or_execution_error"] for row in rows),
            "unique_original_init_states": len({(row["case"]["episode"]["suite"], row["case"]["episode"]["task"],
                                                   row["case"]["episode"]["seed"]) for row in rows}),
            "qualifies_for_confirmation": False, "completion": "fixed exploratory prefix; full arm incomplete"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", action="append", type=Path, required=True)
    parser.add_argument("--prefix-rows", type=int, default=50)
    parser.add_argument("--expected-per-arm", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.prefix_rows < 1 or args.prefix_rows >= args.expected_per_arm:
        raise ValueError("fixed exploratory prefix must be positive and shorter than a full arm")
    preparation, report_dir = args.output / "preparation", args.output / "report"
    preparation.mkdir(parents=True)
    report_dir.mkdir()
    rows, sources, seen = [], [], set()
    checks = Counter()
    for ledger in args.ledger:
        captured, source = source_prefix(ledger, preparation, args.prefix_rows)
        sources.append(source)
        for row in captured:
            name = row["case"]["name"]
            if name in seen:
                raise ValueError("duplicate registered trial")
            seen.add(name)
            choice, check = read_choices(row)
            checks[check] += 1
            rows.append(classify(row, choice))
    by_arm = defaultdict(list)
    for row in rows:
        by_arm[(row["case"]["group"], row["case"]["condition"])].append(row)
    report = {"scope": "fixed firstN exploratory prefixes; CPU-only three-axis diagnosis",
              "created_at_utc": datetime.now(timezone.utc).isoformat(), "script_sha256": sha_bytes(Path(__file__).read_bytes()),
              "prefix_rows_per_ledger": args.prefix_rows, "recorded": len(rows), "sources": sources,
              "choices_checks": dict(checks), "by_class_condition": [{"class": group, "condition": condition,
                  **metrics(members, args.expected_per_arm)} for (group, condition), members in sorted(by_arm.items())],
              "qualifies_for_confirmation": False, "original_ledgers_modified": False,
              "new_physics_trials": 0, "new_model_calls": 0, "new_training_rows": 0,
              "limits": ["Public skill budget stop is independent of final physical truth.",
                         "Skipped contact is not evidence of low-level policy failure.",
                         "Phase snapshots are absent; trial-lift-induced loss cannot be causally labeled.",
                         "Unknown/infrastructure rows are preserved and do not become model failures.",
                         "This fixed first50 prefix cannot replace complete100/arm results or confirmation."]}
    (report_dir / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    (report_dir / "trials.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    print(json.dumps({"recorded": len(rows), "by_class_condition": report["by_class_condition"],
                      "sources": sources, "choices_checks": dict(checks),
                      "summary_sha256": sha_bytes((report_dir / "summary.json").read_bytes()),
                      "trials_sha256": sha_bytes((report_dir / "trials.jsonl").read_bytes())}))


if __name__ == "__main__":
    main()
