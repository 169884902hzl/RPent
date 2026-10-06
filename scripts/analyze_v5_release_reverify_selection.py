"""Audit explicit place v8 ledgers, retaining physical and public verdicts."""

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path


REMOTE_ROOT = "/public/home/sunyihan/rpent_libero_eval"
MANIFEST_SHA = "d58698cef76bbbad9189238adf025a4e75c797b00bc511af06d7388db5c01a24"
SOURCE_COMMIT = "67a4d4bc67af5db89e31dd1f631c88a8eab6397b"
PRIOR4262_SHA = "9e1a06c98a7794d6a528cf14d288829fb93d4937ea26686675887dcdc301684f"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(root, remote):
    return root / Path(remote).relative_to(REMOTE_ROOT)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def physical_failure(first, setup, value):
    """Name observed endpoint geometry, never infer an unobserved motion cause."""
    if setup is not True:
        return "setup_not_true_sustained_hold"
    frame, target = value.get("second"), value.get("target")
    if not frame or not frame["visible"]:
        return "endpoint_object_not_visually_measured"
    if value.get("relation") == "on" and frame["upper"][2] < target["upper"][2]:
        return "endpoint_object_below_measured_support"
    if not all(target["lower"][i] <= frame["xyz"][i] <= target["upper"][i] for i in (0, 1)):
        return "endpoint_centre_outside_measured_target_xy"
    if first.get("receipt", {}).get("stop") == "chunk_budget":
        return "full_contact_budget_without_endpoint_other_geometry"
    return "endpoint_false_other_observed_geometry"


def analyze(root, report_path, job_id):
    report = json.loads(report_path.read_text())
    assert report["complete"] and report["overall"]["recorded"] == 40
    assert report["manifests"][0]["sha256"] == MANIFEST_SHA
    assert report["source"]["commit"] == SOURCE_COMMIT
    helpers = root / "results/harness_v5/skill549_live_CPU_20261006/20261006T142400Z/audit_completed_records.py"
    assert sha(helpers) == "b29487fba4ef8ed265d05f877ac2f44bdd59d0ad50e177a710efa7def9a5709a"
    controls_helper = load(helpers, "release_v8_controls")
    old_helper = root / "results/harness_v5/place560_monitor_CPU_20261006/analyze_complete4262.py"
    assert sha(old_helper) == "e45d11818eaa056a0ffa0fd48f2304cb3aa4ce83cb7ee408f92dc8d438c555d8"
    statistics = load(old_helper, "release_v8_statistics")
    diagnosis = root / "results/harness_v5/place558_endpoint_diagnosis_CPU_20261006/analyze_saved4219.py"
    flags_helper = load(diagnosis, "release_v8_public_flags")
    prior_path = root / "results/harness_v5/place560_monitor_CPU_20261006/20261006T1655Z/job4262/strict_setup_control_and_verifier_audit.json"
    assert sha(prior_path) == PRIOR4262_SHA
    prior = {row["case"]: row for row in json.loads(prior_path.read_text())["records"]}
    raw_refs = report["ledgers"] + report["infrastructure_ledgers"]
    for ref in raw_refs:
        assert sha(local_path(root, ref["path"])) == ref["sha256"]
    groups, records = defaultdict(Counter), []
    for ref in report["ledgers"]:
        path = local_path(root, ref["path"])
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            raw = json.loads(line)
            case, first, setup = raw["case"], raw.get("first_attempt") or {}, raw.get("setup", [])
            group = case["type"] + "/" + case["condition"]
            count = groups[group]
            setup_truth = (setup[-1] if setup else {}).get("private_hold_truth_v2", {}).get("success")
            legacy_setup = (setup[-1] if setup else {}).get("private_true_sustained_grasp")
            count["recorded"] += 1
            count["setup_v2_" + ("true" if setup_truth is True else "false" if setup_truth is False else "unknown")] += 1
            count["setup_legacy_true"] += legacy_setup is True
            count["legacy_true_v2_false"] += legacy_setup is True and setup_truth is False
            controls = controls_helper.stage_controls(first)
            setup_controls = [controls_helper.stage_controls(stage) for stage in setup]
            for prefix, stages in (("setup", setup_controls), ("first", [controls])):
                for stage in stages:
                    count.update({prefix + "_" + key: number for key, number in stage.items()})
            executed = controls["vla_executed"] + controls["non_vla_executed"] > 0
            infra = raw.get("infrastructure_failure") is True
            receipt = first.get("receipt", {})
            value = first.get("verification_measurements") or {}
            before, after = (first.get("private_" + phase, {}).get("satisfied") for phase in ("before", "after"))
            verdict = receipt.get("place_verified")
            flags = flags_helper.verification_flags(value) if value.get("kind") == "placement" else {}
            reverify = value.get("release_reverification") or {}
            release = reverify.get("release") or {}
            actual_release = bool(reverify.get("triggered") and release.get("name") == "release"
                                  and release.get("steps_used", 0) > 0)
            if not reverify and case["condition"] == "vla_subtask160" and receipt.get("error"):
                actual_release = None
            count["release_execution_unrecorded_due_to_error"] += actual_release is None
            count["v8_diagnostic_present"] += bool(reverify)
            count["release_triggered"] += reverify.get("triggered") is True
            count["release_physically_executed"] += actual_release is True
            count["release_physical_controls"] += release.get("steps_used", 0)
            count["fresh_after_release"] += reverify.get("fresh_after_release") is True
            count["public_false_to_true_after_actual_release"] += actual_release is True and verdict is True
            count["public_false_to_false_after_actual_release"] += actual_release is True and verdict is False
            count["public_false_to_null_after_actual_release"] += actual_release is True and verdict is None
            if infra:
                category = "infrastructure_unavailable"
            elif not first:
                category = raw["status"]
            elif receipt.get("error") or receipt.get("verification") == "execution_error":
                category = "skill_execution_error"
            elif not executed:
                category = receipt.get("failure_reason") or "first_not_physically_executed"
            elif before is False and after is True:
                category = "newly_satisfied"
            elif before is True and after is True:
                category = "already_satisfied_preserved"
            elif after is False:
                category = "executed_endpoint_false"
            else:
                category = "private_endpoint_unknown"
            count["class:" + category] += 1
            count["infra_fault"] += infra
            failure_reason = fn_reason = None
            if executed and not infra:
                count["first_physically_executed"] += 1
                count["private_before_false"] += before is False
                count["private_before_true"] += before is True
                count["private_after_true"] += after is True
                count["private_after_false"] += after is False
                count["public_true"] += verdict is True
                count["public_false"] += verdict is False
                count["public_null"] += verdict is None
                count["two_fresh_visible_frames"] += flags.get("two_visible_frames") is True and flags.get("distinct_source_step") is True
                if isinstance(after, bool):
                    count[("null_private_true" if after else "null_private_false") if verdict is None
                          else "TP" if verdict and after else "FP" if verdict else "FN" if after else "TN"] += 1
                if setup_truth is True:
                    count["true_setup_initially_unsatisfied"] += before is False
                    count["true_setup_newly_satisfied"] += before is False and after is True
                    count["true_setup_endpoint_false"] += after is False
                if after is False:
                    failure_reason = physical_failure(first, setup_truth, value)
                    count["physical_failure:" + failure_reason] += 1
                if after is True and verdict is False:
                    fn_reason = ("real_endpoint_gripper_closed" if flags.get("opening_ge_7cm") is False else
                                 "vertical_bounds" if flags.get("vertical_centres_in_target") is False else
                                 "footprint_overlap" if flags.get("footprint_gate") is False else "other_saved_public_rejection")
                    count["FN_reason:" + fn_reason] += 1
                if verdict is None:
                    count["null_reason:" + (receipt.get("verification_reason") or receipt.get("failure_reason") or "not_recorded")] += 1
            telemetry = reverify.get("release_history") or {}
            sensor_rows = telemetry.get("chunks", [])
            raw_chunks = [row for row in first.get("motion_evidence", []) if row.get("name") == "vla_act_chunk"]
            telemetry_matches = None
            if telemetry:
                telemetry_matches = bool(len(sensor_rows) == len(raw_chunks) and all(
                    sensors["opening_after_m"] == motion["gripper_opening"]
                    and sensors["eef_xyz"] == motion["final_eef_pos"]
                    for sensors, motion in zip(sensor_rows, raw_chunks)))
                if not telemetry_matches:
                    raise AssertionError("same-action telemetry differs from actual recorded primitive sensors")
            server = raw.get("server_chunk_execution")
            if server:
                expected = sum(item["vla_executed"] for item in setup_controls) + controls["vla_executed"]
                assert server["executed_controls"] == server["requested_controls"] == expected
                assert not server["native_success_stops_chunk"] and not server["external_truncation"]
                assert not server["private_joint_or_predicate_used_for_control"]
            old = prior[case["name"]]
            assert old["state_sha256"] == case["state_sha256"]
            records.append({"case": case["name"], "group": group, "episode": case["episode"],
                "raw_state_sha256": case["state_sha256"], "ledger": ref["path"], "line": line_no,
                "status": raw["status"], "exclusive_classification": category,
                "setup_v2": setup_truth, "setup_legacy": legacy_setup, "first_physically_executed": executed,
                "private_before": before, "private_after": after, "public_verdict": verdict,
                "actual_release_triggered": reverify.get("triggered"), "release_physically_executed": actual_release,
                "release_steps": release.get("steps_used"), "release": release,
                "fresh_after_release": reverify.get("fresh_after_release"),
                "release_history_sensor_matches_raw_motion": telemetry_matches,
                "public_verification_measurements": value, "public_rejection_flags": flags,
                "physical_failure_observation": failure_reason, "FN_reason": fn_reason,
                "receipt": receipt, "first_controls": controls, "server_controls": server,
                "prior4262_saved_labels": {key: old[key] for key in (
                    "all_current_support_v2_setup", "private_before", "private_after", "public_verdict", "exclusive_classification")},
                "trajectory": raw["output_dir"] + "/choices.jsonl", "choices_sha256": raw.get("choices_sha256"),
                "private_truth_immediately_before_release": "not_measured; endpoint truth is after full action"})
    assert len(records) == 40
    assert len({record["case"] for record in records}) == 40
    overall = sum(groups.values(), Counter())
    for key in ("TP", "FP", "FN", "TN", "public_null", "infra_fault", "release_triggered",
                "release_physically_executed", "release_execution_unrecorded_due_to_error",
                "public_false_to_true_after_actual_release", "public_false_to_false_after_actual_release",
                "public_false_to_null_after_actual_release"):
        overall[key] = overall[key]
    def rates(count):
        success, n = count["true_setup_newly_satisfied"], count["true_setup_initially_unsatisfied"]
        return {"true_setup_first_newly_satisfied_rate": success / n if n else None,
                "true_setup_first_newly_satisfied_wilson95": statistics.wilson(success, n),
                "precision": count["TP"] / (count["TP"] + count["FP"]) if count["TP"] + count["FP"] else None,
                "precision_wilson95": statistics.wilson(count["TP"], count["TP"] + count["FP"]),
                "recall_measured": count["TP"] / (count["TP"] + count["FN"]) if count["TP"] + count["FN"] else None,
                "recall_measured_wilson95": statistics.wilson(count["TP"], count["TP"] + count["FN"])}
    return {"job_id": job_id, "source": report["source"], "report_sha256": sha(report_path),
        "manifest_sha256": MANIFEST_SHA, "overall": dict(overall), "overall_rates": rates(overall),
        "groups": {group: {"counts": dict(count), "rates": rates(count)} for group, count in groups.items()},
        "records": records, "raw_refs": raw_refs, "script_sha256": sha(Path(__file__)),
        "prior4262": {"path": str(prior_path), "sha256": PRIOR4262_SHA},
        "scope": "saved public sensors and private endpoint labels; previous labels retained; no causal attribution from unpaired policy RNG; no truth measured just before release",
        "qualification_authorized": False, "new_physical_trials": 0, "new_training_rows": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--job-id", type=int, required=True)
    args = parser.parse_args()
    result = analyze(args.root.resolve(), args.report.resolve(), args.job_id)
    output = args.report.parent / "strict_setup_release_and_verifier_audit.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"audit": str(output), "sha256": sha(output), "overall": result["overall"]}))


if __name__ == "__main__":
    main()
