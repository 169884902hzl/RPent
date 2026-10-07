"""Separate original public verifier gates from private outcome labels."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from robots.libero.v5_state import Entity, place_verified
from robots.libero.v5_verification import strict_place_verified_v6


def ref(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(reference):
    path = Path(reference["path"])
    if ref(path)["sha256"] != reference["sha256"]:
        raise ValueError(f"registered evidence changed: {path}")
    return path


def entity(value):
    return Entity(**{key: item for key, item in value.items() if key in Entity.__dataclass_fields__}) if value else None


def footprint(obj, target):
    area = math.prod(max(obj["upper"][i] - obj["lower"][i], 1e-6) for i in (0, 1))
    overlap = math.prod(max(0., min(obj["upper"][i], target["upper"][i])
                                  - max(obj["lower"][i], target["lower"][i])) for i in (0, 1))
    return overlap / area


def wilson(successes, count):
    if not count:
        return None
    z = 1.959963984540054
    p = successes / count
    centre = (p + z * z / (2 * count)) / (1 + z * z / count)
    half = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / (1 + z * z / count)
    return [centre - half, centre + half]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--audit-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit_ref = {"path": str(args.audit), "sha256": args.audit_sha}
    audit = json.loads(checked(audit_ref).read_text())
    cases = []
    for item in audit["cases"]:
        if item["readiness"] != "completed_record_present":
            raise ValueError("root cause report requires complete registered seven-job ledger")
        row = json.loads(checked(item["episodes"]).read_text())
        first = row["first_attempt"]
        measured = first["verification_measurements"]
        before, after, target = (measured.get(key) for key in ("first", "second", "target"))
        arguments = (entity(before), entity(after), entity(target), measured["opening"], measured["eef_xyz"], measured["interval_s"])
        original_verdict = first["receipt"]["place_verified"]
        recomputed = strict_place_verified_v6(*arguments, relation=measured["relation"])
        if recomputed is not original_verdict:
            raise ValueError(f"unchanged public verifier differs from original stored verdict: {item['job_id']}")
        base_verdict = place_verified(*arguments, relation=measured["relation"])
        gates = []
        if before is None or after is None or not (before["visible"] and after["visible"]):
            gates.append("fresh_visible_two_frame_evidence_missing")
        if target is None:
            gates.append("target_measurement_missing")
        coverage = [footprint(obj, target) for obj in (before, after)] if before and after and target else []
        contact_gap = [obj["lower"][2] - target["upper"][2] for obj in (before, after)] if before and after and target else []
        if before and after and before["visible"] and after["visible"]:
            if coverage and min(coverage) < .90 and measured["relation"] == "on":
                gates.append("measured_visible_bbox_footprint_below_registered_0.90")
            if contact_gap and max(map(abs, contact_gap)) > .01 and measured["relation"] == "on":
                gates.append("measured_support_gap_above_registered_0.01m")
            if not base_verdict:
                gates.append("base_visual_release_stability_or_relation_gate_failed")
        if recomputed is True:
            gates = ["public_verified"]
        carry = []
        for attempt in item["public_attempts"]:
            for frame in attempt["public_trace"]["frames"]:
                if frame["phase"] != "after_existing_carry_segment" or frame["robot"]["held"] != first["receipt"]["object"]:
                    continue
                obj = frame["entities"].get(first["receipt"]["object"], {})
                current = obj.get("current")
                delta = obj.get("eef_minus_current_measured_midpoint_m")
                offset = frame["held_offset_m"]
                if not current or not delta or not offset or not current["visible"] or current["source_step"] != frame["source_step"]:
                    continue
                carry.append({"reference": frame["reference"], "source_step": frame["source_step"],
                              "object": current, "eef_minus_measured_midpoint_m": delta,
                              "held_offset_m": offset,
                              "offset_xy_difference_m": math.hypot(delta[0]-offset[0], delta[1]-offset[1])})
        retreat = measured.get("observation_retreat", {})
        result = {
            "job": item["job_id"], "case_number": item["case_number"], "episode": item["episode"],
            "condition": item["condition"], "episodes": item["episodes"],
            "target_selected": item["target_selected"],
            "target_logged_motion_controls": item["target_executed_controls"],
            "target_environment_controls": item.get("target_environment_controls"),
            "stored_public_verdict": original_verdict, "recomputed_public_verdict": recomputed,
            "private_before_satisfied": first["private_before"]["satisfied"],
            "private_after_satisfied": first["private_after"]["satisfied"],
            "base_visual_verdict": base_verdict, "public_failure_gates": gates,
            "first_second_footprint_coverage": coverage, "first_second_measured_contact_gap_m": contact_gap,
            "object_visible": [obj["visible"] if obj else None for obj in (before, after)],
            "object_measurement_steps": [obj["source_step"] if obj else None for obj in (before, after)],
            "object_measurements": [before, after], "target_measurement": target,
            "observation_retreat": {key: retreat.get(key) for key in (
                "triggered", "executed", "failure_reason", "error", "before_eef_xyz", "after_eef_xyz", "fresh_frames")},
            "carry_frames": carry,
            "max_carry_held_offset_xy_difference_m": max((frame["offset_xy_difference_m"] for frame in carry), default=None),
            "last_carry_to_settled_measured_xy_displacement_m": (
                math.hypot(after["xyz"][0]-carry[-1]["object"]["xyz"][0],
                           after["xyz"][1]-carry[-1]["object"]["xyz"][1]) if carry and after else None),
            "infrastructure_failure": row["infrastructure_failure"],
            "labels_or_thresholds_changed": False,
        }
        cases.append(result)
    physical = sum(case["private_after_satisfied"] is True for case in cases)
    public = Counter(str(case["stored_public_verdict"]) for case in cases)
    result = {
        "schema": "place-remaining7-original-public-verifier-root-causes/1",
        "audit": audit_ref, "analyzer": ref(__file__), "cases": cases,
        "summary": {"registered_requests": len(cases), "physical_after_true": physical,
                    "physical_after_true_wilson95": wilson(physical, len(cases)),
                    "public_verdicts": dict(public),
                    "public_failure_gates": dict(Counter(gate for case in cases for gate in case["public_failure_gates"]))},
        "sampling_limit": "Previously visited original development diagnostic states; no negative examples or independent confirmation; no precision qualification",
        "private_geometry_read": False, "private_outcome_labels_used_only_for_report": True,
        "old_results_or_thresholds_changed": False, "new_gpu_submissions": 0, "new_training_rows": 0,
        "runtime_fixture_identity_fix_qualification_pending": True,
    }
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output.exists() and args.output.read_text() != encoded:
        raise ValueError("immutable root cause report already differs")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded)
    print(json.dumps({"report": str(args.output), "sha256": ref(args.output)["sha256"], "summary": result["summary"]}))


if __name__ == "__main__":
    main()
