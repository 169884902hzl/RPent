"""Audit only explicit frozen fixture records; no simulation or control calls."""

import argparse
from collections import Counter, defaultdict
import hashlib
import inspect
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--captured-report", type=Path, required=True)
    parser.add_argument("--captured-report-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert sha(args.captured_report) == args.captured_report_sha
    report = json.loads(args.captured_report.read_text())
    from robots.libero.v5_stove_measurement import measured_stove_endpoint
    stove_source = Path(inspect.getfile(measured_stove_endpoint))
    groups, records = defaultdict(Counter), []
    for ref in report["ledgers"]:
        path = Path(ref["path"])
        assert sha(path) == ref["sha256"]
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            row = json.loads(line)
            case = row["case"]
            key = case["type"] + "/" + case["condition"]
            count = groups[key]
            count["case_records"] += 1
            count["status:" + row["status"]] += 1
            accounting = row.get("server_chunk_execution")
            stages = [*row.get("setup", []), *([row["first_attempt"]] if row.get("first_attempt") else [])]
            chunks = [motion for stage in stages for motion in stage.get("motion_evidence", [])
                      if motion.get("name") == "vla_act_chunk"]
            requested = sum(motion.get("requested_action_count", 0) for motion in chunks)
            executed = sum(motion.get("executed_action_count", 0) for motion in chunks)
            record = {"case": case["name"], "group": key, "status": row["status"],
                      "server_chunk_execution": accounting,
                      "recorded_VLA_requested_actions": requested,
                      "recorded_VLA_executed_actions": executed,
                      "captured_ledger": str(path), "line": line_number}
            if accounting is None:
                count["server_accounting_missing"] += 1
            else:
                for field in ("chunks_requested", "requested_controls", "executed_controls", "raw_native_success_controls"):
                    count["server_" + field] += accounting.get(field, 0)
                count["server_external_truncation"] += accounting.get("external_truncation") is True
                count["server_native_success_stops_chunk"] += accounting.get("native_success_stops_chunk") is True
                count["private_truth_used_for_control"] += accounting.get("private_joint_or_predicate_used_for_control") is True
                matches = (requested == accounting.get("requested_controls")
                           and executed == accounting.get("executed_controls"))
                record["server_motion_accounting_matches"] = matches
                count["server_motion_accounting_matches"] += matches
                count["server_requested_equals_executed"] += accounting.get("requested_controls") == accounting.get("executed_controls")
            stage = row.get("first_attempt")
            if stage is None:
                records.append(record)
                continue
            receipt = stage.get("receipt", {})
            before, after = stage.get("private_before", {}), stage.get("private_after", {})
            count["first_before_false"] += before.get("satisfied") is False
            count["first_newly_satisfied"] += before.get("satisfied") is False and after.get("satisfied") is True
            count["first_preserved"] += before.get("satisfied") is True and after.get("satisfied") is True
            approach = receipt.get("fixture_handle_approach") or stage.get("contact_evidence", {}).get("approach") or {}
            previous = approach.get("before", {})
            refined = approach.get("after_wrist_refinement", {})
            plan = approach.get("observation_pose")
            record.update(selected=stage["selected"], handle_before=previous,
                          handle_after_wrist=refined, observation_plan=plan,
                          actual_first_contact_actions=stage.get("contact_evidence", {}).get("executed_vla_actions"),
                          runtime_verdict=receipt.get("articulate_verified"),
                          runtime_failure_reason=receipt.get("failure_reason") or receipt.get("reason"))
            count["contact_ready"] += approach.get("ready_for_contact") is True
            if plan:
                count["observation_plan_recorded"] += 1
                count["observation_plan_reason:" + str(plan.get("reason", "planned"))] += 1
                count["observation_plan_positive_lift"] += plan.get("vertical_lift_m", 0) > 0
            if refined:
                fresh = (isinstance(refined.get("source_step"), int)
                         and refined["source_step"] > previous.get("source_step", -1))
                record["after_handle_is_new_capture"] = fresh
                count["after_handle_new_capture"] += fresh
                count["after_handle_has_wrist"] += "wrist" in refined.get("source_cameras", [])
                count["after_handle_fusion:" + str(refined.get("fusion_version"))] += 1
            cloud_records = []
            for label, measured in (("before", previous), ("after", refined)):
                for camera, view in measured.get("views", {}).items():
                    cloud = view.get("cloud")
                    if not cloud:
                        continue
                    cloud_path = Path(cloud["path"])
                    matches = cloud_path.is_file() and sha(cloud_path) == cloud["sha256"]
                    fresh_source = cloud.get("source_step") == measured.get("source_step")
                    count["explicit_handle_clouds"] += 1
                    count["explicit_handle_cloud_sha_matches"] += matches
                    count["handle_cloud_capture_step_matches"] += fresh_source
                    cloud_records.append({"phase": label, "camera": camera, **cloud,
                                          "actual_sha_matches": matches, "capture_step_matches": fresh_source})
            record["explicit_handle_cloud_audit"] = cloud_records
            stove = stage.get("verification_measurements", {}).get("stove_rgbd")
            if stove:
                verdict, evidence = measured_stove_endpoint(stove.get("before"), stove.get("after"), case["mode"],
                    second_after=stove.get("second_after"), interval_s=stove.get("measurement_interval_s"))
                record["stove_recomputed_verdict"] = verdict
                record["stove_recomputed_evidence"] = evidence
                record["stove_final_verdict_matches"] = verdict is receipt.get("articulate_verified")
                count["stove_recorded_public_inputs"] += 1
                count["stove_final_verdict_matches"] += record["stove_final_verdict_matches"]
            records.append(record)
    result = {"version": "fixture549-recorded-runtime-evidence/1",
              "scope": "explicit captured records and public measurement files only; no physics/control, private-truth control, outcome relabeling, training or qualification",
              "captured_report": str(args.captured_report), "captured_report_sha256": sha(args.captured_report),
              "source": report["source"], "stove_verifier_source": str(stove_source),
              "stove_verifier_sha256": sha(stove_source),
              "script_sha256": sha(__file__), "by_type_condition": {k: dict(v) for k, v in groups.items()},
              "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"report": str(args.output), "sha256": sha(args.output),
                      "groups": result["by_type_condition"]}))


if __name__ == "__main__":
    main()
