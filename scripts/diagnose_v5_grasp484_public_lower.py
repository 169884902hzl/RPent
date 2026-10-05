"""Compare saved visual lower bounds with sustained-grasp diagnostic truth.

This reuses closed trials. It neither executes a lift nor evaluates the pending
two-frame verifier; the single-frame alternative is explicitly retrospective.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound_entity(entities, entity_id):
    matches = [entity for entity in entities if entity["id"] == entity_id]
    if len(matches) > 1:
        raise ValueError("ambiguous saved public entity ID")
    return matches[0] if matches else None


def diagnose(row):
    choice_path = Path(row["output_dir"]) / "choices.jsonl"
    if sha(choice_path) != row["choices_sha256"]:
        raise ValueError("saved choice trace changed")
    events = list(map(json.loads, choice_path.read_text().splitlines()))
    if len(events) != 1 or not events[0]["selected"].startswith("grasp("):
        raise ValueError("expected one registered first-grasp decision")
    event = events[0]
    entity_id = row["selected_public_entity"]
    before = bound_entity(event["measurements"], entity_id)
    after = bound_entity(event["post_measurements"], entity_id)
    opening = event["post_robot_measurement"]["gripper_opening"]
    fresh = bool(before and after and after["visible"]
                 and after["source_step"] > before["source_step"])
    lower_rise = after["lower"][2] - before["lower"][2] if fresh else None
    centre_rise = after["xyz"][2] - before["xyz"][2] if fresh else None
    public_rule = bool(fresh and .002 <= opening <= .07 and lower_rise >= .03)
    truth = row["true_sustained_grasp"]
    if not isinstance(truth, bool):
        raise ValueError("closed trial lacks registered sustained-grasp truth")
    hold = row["sustained_hold"]["truth"]
    checks = hold["checks"]
    private = row["final_private_contact"]
    return {
        "case": row["case"]["name"],
        "condition": row["case"]["condition"],
        "class": row["case"]["group"],
        "true_sustained_grasp": truth,
        "original_visual_verified": row["visual_verified"],
        "retrospective_single_frame_lower_verified": public_rule,
        "public_fresh_visible": fresh,
        "public_lower_rise_m": lower_rise,
        "public_centre_rise_m": centre_rise,
        "public_gripper_opening": opening,
        "public_before": before,
        "public_after": after,
        "private_body_origin_rise_m": private["private_z_rise_m"],
        "private_final_dual_contact": private["target_dual_contact"],
        "private_hold_min_clearance_m": hold["min_clearance_m"],
        "private_hold_any_finger_contact": any(c["finger_contact"] for c in checks),
        "private_hold_any_support_contact": any(c["touching_original_support"] for c in checks),
        "private_hold_any_3cm_clearance": any(c["clearance_m"] >= .03 for c in checks),
        "private_hold_all_3cm_clearance": all(c["clearance_m"] >= .03 for c in checks),
        "original_receipt": row["first_receipt"],
        "choices_path": str(choice_path),
        "choices_sha256": row["choices_sha256"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    sources, rows, seen = [], [], set()
    for ledger in args.ledger:
        raw = ledger.read_bytes()
        if not raw.endswith(b"\n"):
            raise ValueError("ledger contains an incomplete final record")
        sources.append({"path": str(ledger), "sha256": sha(ledger)})
        for line in raw.splitlines():
            row = json.loads(line)
            name = row["case"]["name"]
            if name in seen:
                raise ValueError("duplicate registered trial")
            seen.add(name)
            rows.append(diagnose(row))
    grouped = defaultdict(lambda: {"original": Counter(), "lower_single_frame": Counter(),
                                   "original_fp_diagnostics": Counter()})
    for row in rows:
        group = grouped[(row["class"], row["condition"])]
        truth = row["true_sustained_grasp"]
        for key, predicted in (("original", row["original_visual_verified"]),
                               ("lower_single_frame", row["retrospective_single_frame_lower_verified"])):
            group[key]["tp" if truth and predicted else "fn" if truth else "fp" if predicted else "tn"] += 1
        if row["original_visual_verified"] and not truth:
            count = group["original_fp_diagnostics"]
            count["trials"] += 1
            count["private_body_origin_rise_at_least_3cm"] += row["private_body_origin_rise_m"] >= .03
            for field in ("private_final_dual_contact", "private_hold_any_finger_contact",
                          "private_hold_any_support_contact", "private_hold_any_3cm_clearance",
                          "private_hold_all_3cm_clearance", "retrospective_single_frame_lower_verified"):
                count[field] += row[field]
    report = {
        "scope": "CPU retrospective measurement diagnosis, not a new online verifier score",
        "sources": sources,
        "script_sha256": sha(Path(__file__)),
        "by_class_condition": [{"class": k[0], "condition": k[1],
                                **{name: dict(count) for name, count in value.items()}}
                               for k, value in sorted(grouped.items())],
        "rows": rows,
        "limits": ["Uses saved post-skill measurements; no extra trial lift or second frame was executed.",
                   "A visible-surface lower bound is not necessarily the lowest collision geometry.",
                   "Private geometry and contacts are diagnostic labels, never runtime inputs.",
                   "Original physical labels and receipts remain unchanged."],
        "new_physics": 0,
        "new_model_calls": 0,
        "new_training_rows": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"recorded": len(rows), "groups": report["by_class_condition"],
                      "report_sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
