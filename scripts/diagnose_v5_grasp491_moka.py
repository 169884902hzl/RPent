"""CPU-only moka metrology and visual-receipt audit from explicit ledgers.

Saved simulation truth is diagnostic evidence, never a controller input.
No physics, policy calls, new labels or artifact discovery are performed.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stats(values):
    values = sorted(value for value in values if value is not None)
    return {"n": len(values), "median": statistics.median(values) if values else None,
            "p95": values[math.ceil(.95 * len(values)) - 1] if values else None,
            "min": min(values) if values else None, "max": max(values) if values else None}


def touched_geoms(sample, symbol):
    other = []
    for contact in sample["contacts"]:
        a, b = contact["geom1"] or "", contact["geom2"] or ""
        if a.startswith(symbol + "_") and not b.startswith(symbol + "_"):
            other.append(b)
        elif b.startswith(symbol + "_") and not a.startswith(symbol + "_"):
            other.append(a)
    return sorted(set(other))


def measured_target(measurements, target):
    return next((row for row in measurements if row["id"] == target), None)


def visual_summary(before, after, opening):
    available = bool(after and after["visible"])
    return {"before": before, "after": after, "opening_m": opening,
            "fresh_visible_after": available,
            "centre_rise_m": after["xyz"][2] - before["xyz"][2] if available and before else None,
            "lower_rise_m": after["lower"][2] - before["lower"][2] if available and before else None,
            "after_xy_width_m": after["upper"][0] - after["lower"][0] if available else None,
            "after_xy_depth_m": after["upper"][1] - after["lower"][1] if available else None}


def diagnose(row, choice):
    symbol = row["final_private_contact"]["selected_symbol"]
    initial = row["initial_private_reference"]["objects"]
    final = row["final_private_contact"]["objects"][symbol]
    contact_samples = row["contact_samples"]
    motions = [motion for motion in choice["motion_evidence"] if motion["name"] == "vla_act_chunk"]
    if len(motions) != len(contact_samples):
        raise ValueError("cannot pair contact and VLA chunk observations")
    target_rises, dual_chunks, finger_chunks, other_dual_lift = [], [], [], []
    release_chunks, prior_dual_lift = [], False
    for index, (sample, motion) in enumerate(zip(contact_samples, motions), 1):
        body = sample["objects"][symbol]
        rise = body["xyz"][2] - initial[symbol]["xyz"][2]
        target_rises.append(rise)
        finger = any("gripper" in geom and "finger" in geom for geom in touched_geoms(sample, symbol))
        if finger:
            finger_chunks.append(index)
        if body["dual_finger_contact"]:
            dual_chunks.append(index)
        if body["dual_finger_contact"] and rise >= .03:
            prior_dual_lift = True
        if prior_dual_lift and not finger and motion["gripper_opening"] >= .06:
            release_chunks.append(index)
        for name, obj in sample["objects"].items():
            if name != symbol and obj["dual_finger_contact"] and obj["xyz"][2] - initial[name]["xyz"][2] >= .03:
                other_dual_lift.append({"chunk": index, "symbol": name,
                                       "body_origin_rise_m": obj["xyz"][2] - initial[name]["xyz"][2]})
    hold = row["sustained_hold"]["truth"]
    checks = hold["checks"]
    all_fingers = all(check["finger_contact"] for check in checks)
    any_fingers = any(check["finger_contact"] for check in checks)
    all_clear = all(check["clearance_m"] >= .03 for check in checks)
    touches_support = any(check["touching_original_support"] for check in checks)
    duration_pass = hold["duration_s"] + 1e-8 >= hold["required_duration_s"]
    hold_tail = row["sustained_hold"]["samples"][-5:]
    stable_support_after_release = bool(release_chunks and all(
        not sample["finger_contact"] and any(geom and not geom.startswith(("gripper", "robot"))
                                            for geom in sample["other_contact_geoms"])
        for sample in hold_tail) and max(sample["lower_extent_m"] for sample in hold_tail)
        - min(sample["lower_extent_m"] for sample in hold_tail) <= .005)
    if row["true_sustained_grasp"] is True:
        primary = "success"
    elif row["true_sustained_grasp"] is not False:
        primary = "unknown_truth"
    elif stable_support_after_release:
        primary = "recorded_dual_lift_then_release_to_stable_support_proxy"
    elif not any_fingers and max(target_rises, default=0) < .03:
        primary = "no_recorded_target_lift_or_final_finger_support"
    elif all_fingers and not all_clear:
        primary = "held_target_has_insufficient_collision_clearance"
    elif not all_fingers:
        primary = "finger_support_not_sustained"
    elif touches_support:
        primary = "original_support_contact_persists"
    elif not all_clear:
        primary = "insufficient_collision_clearance"
    else:
        primary = "hold_duration_or_unresolved_truth_failure"
    target = row["selected_public_entity"]
    before = measured_target(choice["measurements"], target)
    after = measured_target(choice["post_measurements"], target)
    opening = choice["post_robot_measurement"]["gripper_opening"]
    vision = visual_summary(before, after, opening)
    confusion = ("TP" if row["visual_verified"] else "FN") if row["true_sustained_grasp"] else (
        "FP" if row["visual_verified"] else "TN")
    if confusion == "FN":
        vision_reason = "missing_selected_visual_measurement" if not vision["fresh_visible_after"] else (
            "aperture_outside_registered_range" if not .002 <= opening <= .07 else
            "visible_centre_rise_below3cm" if vision["centre_rise_m"] < .03 else "unresolved_verifier_mismatch")
    elif confusion == "FP":
        vision_reason = "visible_centre_passes_but_collision_clearance_fails" if not all_clear else (
            "visible_centre_passes_but_finger_support_fails" if not all_fingers else
            "visible_centre_passes_but_original_support_contact_persists")
    else:
        vision_reason = "agreement"
    public = row["rpent_pick_result"]
    return {"case": row["case"], "choices_sha256": row["choices_sha256"], "output_dir": row["output_dir"],
            "prompt": row["contact_prompt"], "true_sustained_grasp_unchanged": row["true_sustained_grasp"],
            "visual_verified_unchanged": row["visual_verified"], "confusion": confusion,
            "primary_metrology_category": primary, "visual_disagreement_category": vision_reason,
            "hold_checks": {"all_finger_support": all_fingers, "any_finger_support": any_fingers,
                            "all_collision_clearance_3cm": all_clear, "any_original_support_contact": touches_support,
                            "duration_pass": duration_pass, "min_clearance_m": hold["min_clearance_m"],
                            "max_clearance_m": max(check["clearance_m"] for check in checks)},
            "public_stop": {"success": public["success"], "chunks_used": public["chunks_used"],
                            "max_chunks": public["max_chunks"], "final_opening_m": public["final_gripper_opening"],
                            "success_but_final_truth_false": public["success"] and row["true_sustained_grasp"] is False,
                            "at_budget": public["chunks_used"] >= public["max_chunks"],
                            "budget_failure": public["chunks_used"] >= public["max_chunks"] and not public["success"],
                            "eef_stop_diagnostics": public["diagnostics"]},
            "target_contact": {"selected_private_symbol": symbol, "sample_count": len(contact_samples),
                               "dual_contact_chunks": dual_chunks, "any_finger_contact_chunks": finger_chunks,
                               "max_chunk_body_origin_rise_m": max(target_rises, default=0),
                               "final_body_origin_rise_m": final["xyz"][2] - initial[symbol]["xyz"][2],
                               "final_xy_displacement_m": math.dist(final["xyz"][:2], initial[symbol]["xyz"][:2]),
                               "release_after_dual_lift_chunks": release_chunks,
                               "final_touching_geoms": touched_geoms(row["final_private_contact"], symbol),
                               "other_dual_contact_and_body_rise_proxy": other_dual_lift},
            "visual_measurements": vision, "receipt_unchanged": row["first_receipt"]}


def groups(rows):
    cohorts = defaultdict(list)
    for row in rows:
        cohorts[row["case"]["condition"]].append(row)
    result = []
    for condition, trials in sorted(cohorts.items()):
        truth_true = sum(row["true_sustained_grasp_unchanged"] is True for row in trials)
        counts = Counter(row["confusion"] for row in trials)
        result.append({"condition": condition, "recorded": len(trials), "true_success": truth_true,
            "unique_original_init_states": len({tuple(row["case"]["episode"].values()) for row in trials}),
            "confusion": dict(counts), "agreement_numerator": counts["TP"] + counts["TN"],
            "false_positive_rate": {"numerator": counts["FP"], "denominator": len(trials) - truth_true},
            "false_negative_rate": {"numerator": counts["FN"], "denominator": truth_true},
            "primary_metrology_categories": dict(Counter(row["primary_metrology_category"] for row in trials)),
            "visual_disagreement_categories": dict(Counter(row["visual_disagreement_category"] for row in trials)),
            "public_stop_success_final_truth_false": sum(row["public_stop"]["success_but_final_truth_false"] for row in trials),
            "public_stop_budget_failure": sum(row["public_stop"]["budget_failure"] for row in trials),
            "failure_aperture_counts": {
                "public_stop_below2mm": sum(row["true_sustained_grasp_unchanged"] is False
                    and row["public_stop"]["final_opening_m"] < .002 for row in trials),
                "actual_final_below2mm": sum(row["true_sustained_grasp_unchanged"] is False
                    and row["visual_measurements"]["opening_m"] < .002 for row in trials),
                "actual_final_above7cm": sum(row["true_sustained_grasp_unchanged"] is False
                    and row["visual_measurements"]["opening_m"] > .07 for row in trials)},
            "failed_truth_checks": {name: sum(row["true_sustained_grasp_unchanged"] is False and bool(test(row))
                for row in trials) for name, test in {
                "collision_clearance": lambda row: not row["hold_checks"]["all_collision_clearance_3cm"],
                "finger_support": lambda row: not row["hold_checks"]["all_finger_support"],
                "original_support_contact": lambda row: row["hold_checks"]["any_original_support_contact"]}.items()},
            "failure_with_other_object_dual_contact_lift_proxy": sum(row["true_sustained_grasp_unchanged"] is False
                and bool(row["target_contact"]["other_dual_contact_and_body_rise_proxy"]) for row in trials),
            "numeric_stats": {name: stats([value(row) for row in trials]) for name, value in {
                "private_final_body_origin_rise_m": lambda row: row["target_contact"]["final_body_origin_rise_m"],
                "private_min_collision_clearance_m": lambda row: row["hold_checks"]["min_clearance_m"],
                "public_chunks": lambda row: row["public_stop"]["chunks_used"],
                "public_final_opening_m": lambda row: row["public_stop"]["final_opening_m"],
                "actual_final_opening_m": lambda row: row["visual_measurements"]["opening_m"]}.items()}})
    return result


def read_choices(row, seen):
    path = Path(row["output_dir"]) / "choices.jsonl"
    if path in seen or sha(path) != row["choices_sha256"]:
        raise ValueError("duplicate or changed choices")
    seen.add(path)
    choices = list(map(json.loads, path.read_text().splitlines()))
    if len(choices) != 1:
        raise ValueError("one-decision first-grasp probe expected")
    return choices[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", action="append", type=Path, required=True)
    parser.add_argument("--smoke-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    rows, sources, seen = [], [], set()
    for ledger in args.ledger:
        raw = ledger.read_bytes()
        if not raw.endswith(b"\n") or len(raw.splitlines()) != 100:
            raise ValueError("expected complete100-trial formal ledger")
        sources.append({"path": str(ledger), "sha256": hashlib.sha256(raw).hexdigest(), "recorded": 100})
        for line in raw.splitlines():
            row = json.loads(line)
            if row["case"]["group"] != "moka_pot" or row["true_sustained_grasp"] is None:
                raise ValueError("moka known truth only")
            rows.append(diagnose(row, read_choices(row, seen)))
    raw = args.smoke_ledger.read_bytes()
    if not raw.endswith(b"\n"):
        raise ValueError("incomplete smoke ledger")
    smoke = []
    for line in raw.splitlines():
        row = json.loads(line)
        if row["case"]["group"] != "moka_pot":
            continue
        choice = read_choices(row, seen)
        stable = row["stable_visual_grasp"]
        frames = [{"camera": frame["camera"], "passes_lower_rise_and_aperture": frame["passes_lower_rise_and_aperture"],
                   **visual_summary(frame["before"], frame["after"], frame["gripper_opening"])}
                  for frame in stable["frames"]]
        smoke.append({"case": row["case"], "choices_sha256": row["choices_sha256"], "output_dir": row["output_dir"],
            "truth_unchanged": row["true_sustained_grasp"], "visual_unchanged": row["visual_verified"],
            "version": stable["version"], "frames": frames,
            "private_min_collision_clearance_m": row["sustained_hold"]["truth"]["min_clearance_m"],
            "receipt_unchanged": row["first_receipt"]})
    paired = defaultdict(dict)
    for row in rows:
        if row["case"]["condition"] not in ("rpent_high10_short160", "rpent_high10_alias160"):
            continue
        case = row["case"]
        key = (case["episode"]["suite"], case["episode"]["task"], case["episode"]["seed"], case["initial_state_repetition"])
        paired[key][case["condition"]] = row
    pair_counts = Counter()
    for pair in paired.values():
        b, ba = pair["rpent_high10_short160"], pair["rpent_high10_alias160"]
        if b["prompt"] != ba["prompt"]:
            raise ValueError("moka B/BA unexpectedly have different contact prompts")
        pair_counts[f"B_{b['true_sustained_grasp_unchanged']}_BA_{ba['true_sustained_grasp_unchanged']}"] += 1
    report = {"scope": "CPU-only original-task saved evidence; no new physics or changed labels",
              "sources": sources, "recorded": len(rows), "formal_choices_sha256_checked": len(rows),
              "script_sha256": sha(__file__), "by_condition": groups(rows),
              "B_BA_comparison": {"same_moka_prompt": True, "moka_alias_delta": False,
                                  "paired_trials": len(paired), "paired_counts": dict(pair_counts),
                                  "different_methods": False},
              "smoke_source": {"path": str(args.smoke_ledger), "sha256": hashlib.sha256(raw).hexdigest(),
                               "whole_ledger_records": len(raw.splitlines()), "moka_choices_checked": len(smoke)},
              "two_frame_moka_smoke": smoke, "new_physics_trials": 0, "new_training_rows": 0,
              "limits": ["Finger/contact plus body-origin rise is a diagnostic proxy, not registered sustained-grasp truth.",
                         "Public pick stop and final hold are different times; later trial lift can change success.",
                         "Visible-surface bounds differ from full collision geometry; missing measurements alone do not prove occlusion.",
                         "Each100-trial cohort repeats50 official original init states twice; not an independent confirmation batch.",
                         "B/BA share the same moka prompt and approach; noise cannot be counted as a new method.",
                         "No raw mask/image audit here: unstable lower-bound cause is not proven segmentation contamination."]}
    args.output.mkdir(parents=True)
    with (args.output / "trials.jsonl").open("x") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"recorded": len(rows), "by_condition": report["by_condition"],
                      "B_BA_comparison": report["B_BA_comparison"],
                      "summary_sha256": sha(args.output / "summary.json"),
                      "trials_sha256": sha(args.output / "trials.jsonl")}))


if __name__ == "__main__":
    main()
