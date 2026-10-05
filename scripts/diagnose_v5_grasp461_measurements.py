"""Compare saved visual measurements with sustained grasp truth, without replay."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def confusion(rows, key):
    counts = Counter()
    for row in rows:
        truth, predicted = row["truth"], row[key]
        if not isinstance(truth, bool) or not isinstance(predicted, bool):
            counts["unknown"] += 1
            continue
        counts["tp" if truth and predicted else "fn" if truth else "fp" if predicted else "tn"] += 1
    known = sum(counts[k] for k in ("tp", "tn", "fp", "fn"))
    positives, negatives = counts["tp"] + counts["fn"], counts["tn"] + counts["fp"]
    return {"counts": dict(counts), "known": known,
            "agreement": (counts["tp"] + counts["tn"]) / known if known else None,
            "false_positive_rate": counts["fp"] / negatives if negatives else None,
            "false_negative_rate": counts["fn"] / positives if positives else None}


def diagnose(row, choice):
    selected = row["selected_public_entity"]
    before = next((e for e in choice["measurements"] if e["id"] == selected), None)
    after = next((e for e in choice["post_measurements"] if e["id"] == selected), None)
    opening = choice["post_robot_measurement"]["gripper_opening"]
    checks = row.get("sustained_hold", {}).get("truth", {}).get("checks", [])
    truth = row.get("true_sustained_grasp")
    fresh = bool(before and after and after["visible"] and after["source_step"] > before["source_step"])
    centre_rise = after["xyz"][2] - before["xyz"][2] if fresh else None
    lower_rise = after["lower"][2] - before["lower"][2] if fresh else None
    runtime_predicted = row["visual_verified"]
    reason = None
    if truth is False:
        qualified = [c["clearance_m"] >= .03 and c["finger_contact"] and not c["touching_original_support"]
                     for c in checks]
        if qualified and qualified[0] and not all(qualified):
            reason = "initial_hold_then_drop_or_support_contact"
        elif any(qualified):
            reason = "hold_not_continuous_for_0_5s"
        elif any(c["finger_contact"] for c in checks):
            reason = "finger_contact_without_full_clearance"
        elif any(c["clearance_m"] >= .03 for c in checks):
            reason = "clearance_without_finger_support"
        else:
            reason = "no_final_lift_or_hold"
    mismatch = None
    if truth is True and not runtime_predicted:
        mismatch = "fresh_visual_measurement_missing" if not fresh else (
            "aperture_outside_2_70mm" if not .002 <= opening <= .07 else
            "measured_centre_rise_below_3cm" if centre_rise < .03 else "post_frame_passes_2mm_hypothesis")
    elif truth is False and runtime_predicted:
        mismatch = reason
    return {"case": row["case"], "truth": truth, "recorded_visual": runtime_predicted,
            "opening_m": opening, "before": before, "after": after,
            "fresh_visible_measurement": fresh, "centre_rise_m": centre_rise,
            "visible_surface_lower_rise_m": lower_rise,
            "post_centre_2mm": bool(fresh and .002 <= opening <= .07 and centre_rise >= .03),
            "post_centre_5mm": bool(fresh and .005 <= opening <= .07 and centre_rise >= .03),
            "post_lower_2mm": bool(fresh and .002 <= opening <= .07 and lower_rise >= .03),
            "physical_failure": reason, "verifier_mismatch": mismatch,
            "min_private_clearance_m": min((c["clearance_m"] for c in checks), default=None),
            "hold_checks": len(checks), "execution_error": row["first_receipt"].get("verification") == "execution_error"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows, sources = [], []
    seen = set()
    for ledger in args.ledger:
        sources.append({"path": str(ledger), "sha256": sha(ledger)})
        for line_number, line in enumerate(ledger.read_text().splitlines(), 1):
            raw = json.loads(line)
            if raw["case"]["episode"]["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
                raise ValueError("not an original-task diagnostic")
            choice_path = Path(raw["output_dir"]) / "choices.jsonl"
            if choice_path in seen or sha(choice_path) != raw["choices_sha256"]:
                raise ValueError("duplicate or changed saved physical trace")
            seen.add(choice_path)
            choices = list(map(json.loads, choice_path.read_text().splitlines()))
            if len(choices) != 1:
                raise ValueError("requires one registered first-grasp decision")
            row = diagnose(raw, choices[0])
            row["source"] = {"ledger": str(ledger), "line": line_number,
                             "choice": str(choice_path), "sha256": raw["choices_sha256"]}
            rows.append(row)
    tests = ("recorded_visual", "post_centre_2mm", "post_centre_5mm", "post_lower_2mm")
    report = {"scope": "CPU retrospective saved-frame diagnostic, not a new physical validation or qualification",
              "script_sha256": sha(Path(__file__)), "sources": sources,
              "records": len(rows), "execution_errors": sum(r["execution_error"] for r in rows),
              "new_physics_steps": 0, "new_training_rows": 0,
              "failure_counts": dict(Counter(r["physical_failure"] for r in rows if r["physical_failure"])),
              "verifier_mismatch_counts": dict(Counter(r["verifier_mismatch"] for r in rows if r["verifier_mismatch"])),
              "post_frame_caveat": "Post-frame recomputations are hypotheses, not the receipt-time decision. Visible-surface lower bound is not full-object truth; no stable second visual frame was recorded.",
              "comparisons": {k: confusion(rows, k) for k in tests},
              "by_class": {group: {k: confusion([r for r in rows if r["case"]["group"] == group], k) for k in tests}
                           for group in sorted({r["case"]["group"] for r in rows})},
              "rows": rows}
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("records", "failure_counts", "verifier_mismatch_counts", "comparisons")}))
    print(json.dumps({"output": str(args.output), "sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
