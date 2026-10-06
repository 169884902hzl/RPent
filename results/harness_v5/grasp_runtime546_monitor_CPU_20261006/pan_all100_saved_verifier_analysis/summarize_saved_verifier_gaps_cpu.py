"""Summarize saved pan100 verifier gaps without changing their verdicts."""

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUTS = {
    "original33_gap_rows.json": "05d160f10c08cf4bce7adce72341c4f752d1707e2b51a3114770e1a61c8d9692",
    "33_gap_frames.json": "c0f3468db06390161d6510c3852b269c463fd91cddc0ced70914f16bd1770f69",
}
for name, expected in INPUTS.items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
raw = json.loads((ROOT / "original33_gap_rows.json").read_text())
rows = json.loads((ROOT / "33_gap_frames.json").read_text())
assert {r["case"]["name"] for r in raw} == {r["case"] for r in rows}
case_counts, frame_counts, opening_counts, view_counts = (Counter() for _ in range(4))
case_details = []
for row in rows:
    reasons = set()
    evidence = []
    for frame in row["frames"]:
        for view, saved in frame["views"].items():
            view_counts[view] += 1
            conditions = saved["conditions"]
            opening_counts[str(conditions["calibrated_nonempty_opening"])] += 1
            if conditions["near_measured_fingers"] is None:
                acquisition = frame["handle_acquisition"].get(view, {})
                accepted = acquisition.get("accepted_instances")
                assert accepted == 0 or accepted > 1
                reason = "current_bound_handle_missing" if accepted == 0 else "current_bound_handle_ambiguous"
            elif conditions["near_measured_fingers"] is False:
                reason = "visible_handle_outside_pad_contact_volume"
            elif conditions["measured_lower_lift"] is False:
                reason = "measured_lower_lift_or_support_failed"
            else:
                assert all(v is True for v in conditions.values())
                reason = "all_measured_conditions_pass"
            if reason != "all_measured_conditions_pass":
                reasons.add(reason)
            frame_counts[reason] += 1
            evidence.append({"step": frame["step"], "view": view, "reason": reason,
                             "conditions": conditions, "opening_reason": saved["opening_reason"]})
    assert len(reasons) == 1
    reason = next(iter(reasons))
    assert row["truth"] is True
    assert row["public"] is None if reason.startswith("current_bound_handle_") else row["public"] is False
    case_counts[reason] += 1
    case_details.append({"case": row["case"], "original_truth": row["truth"],
                         "original_public": row["public"], "diagnostic_reason": reason,
                         "saved_output_dir": row["output_dir"], "frame_evidence": evidence})
report = {
    "scope": "Saved evidence only: 9 FN and 24 unmeasured cases from completed pan100 confirmation",
    "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "inputs": INPUTS,
    "original_truth_and_public_verdicts_preserved": True,
    "gap_cases": len(rows), "case_reason_counts": dict(case_counts),
    "frame_reason_counts": dict(frame_counts), "frame_view_counts": dict(view_counts),
    "calibrated_nonempty_opening_counts": dict(opening_counts),
    "opening_failure_cases": 0,
    "interpretation": {
        "handle_missing_or_ambiguous": "24 unmeasured cases lack a current unique target-bound handle: 23 missing and 1 with two accepted candidates in both saved frames",
        "pad_volume": "8 FN cases have visible handle points outside the existing pad contact volume; this is not a whole-finger contact claim",
        "lift_support": "1 FN case fails saved measured lower-lift/support conditions",
        "opening": "All 66 saved frames pass the calibrated nonempty opening check; no opening threshold change is supported by these gaps",
    },
    "case_details": case_details,
    "new_physical_trials": 0, "new_model_calls": 0, "truth_labels_recomputed": False,
    "original_confirmation_result_replaced": False, "qualification_authorized": False,
}
(ROOT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: report[k] for k in ("gap_cases", "case_reason_counts", "frame_reason_counts", "frame_view_counts", "calibrated_nonempty_opening_counts")}))
