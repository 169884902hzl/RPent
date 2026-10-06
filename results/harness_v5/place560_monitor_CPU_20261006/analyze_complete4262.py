"""Project completed explicit place560 records without physical replay or relabeling."""

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path


REMOTE_ROOT = "/public/home/sunyihan/rpent_libero_eval"
MANIFEST_SHA = "327dd7044215829e46168d81f8bbb8743505a22ceab07493f76d4c1955217679"
HELPER_SHA = "b29487fba4ef8ed265d05f877ac2f44bdd59d0ad50e177a710efa7def9a5709a"
DIAGNOSIS_SHA = "1f6b5a30d79b0aa2c8df9be79ddfbad5a6feafb2d145df1f53cfba4b6f378a7a"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    denominator = 1 + z * z / n
    centre = (k / n + z * z / (2 * n)) / denominator
    half = z * math.sqrt(k / n * (1 - k / n) / n + z * z / (4 * n * n)) / denominator
    return [max(0, centre - half), min(1, centre + half)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    report = json.loads(args.report.read_text())
    assert report["complete"] and report["overall"]["recorded"] == 40
    assert report["manifests"][0]["sha256"] == MANIFEST_SHA
    helper_path = root / "results/harness_v5/skill549_live_CPU_20261006/20261006T142400Z/audit_completed_records.py"
    assert sha(helper_path) == HELPER_SHA
    helper = load_module(helper_path, "controls_completed4262")
    diagnostic_directory = root / "results/harness_v5/place558_endpoint_diagnosis_CPU_20261006"
    assert sha(diagnostic_directory / "diagnosis.json") == DIAGNOSIS_SHA
    flags_helper = load_module(diagnostic_directory / "analyze_saved4219.py", "saved_public_flags4262")
    prior = json.loads((diagnostic_directory / "diagnosis.json").read_text())
    prior_records = {record["case"]: record for record in prior["records"]}
    groups, records, raw_refs = defaultdict(Counter), [], report["ledgers"] + report["infrastructure_ledgers"]
    for ref in raw_refs:
        path = root / Path(ref["path"]).relative_to(REMOTE_ROOT)
        assert sha(path) == ref["sha256"]
    for ref in report["ledgers"]:
        path = root / Path(ref["path"]).relative_to(REMOTE_ROOT)
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            row = json.loads(line)
            case, first = row["case"], row.get("first_attempt") or {}
            group = case["type"] + "/" + case["condition"]
            count, setup = groups[group], row.get("setup", [])
            setup_last = setup[-1] if setup else {}
            strict = setup_last.get("private_hold_truth_v2", {}).get("success")
            legacy = setup_last.get("private_true_sustained_grasp")
            count["recorded"] += 1
            count["setup_v2_true"] += strict is True
            count["setup_v2_false"] += strict is False
            count["setup_v2_unknown"] += strict is None
            count["setup_legacy_true"] += legacy is True
            count["setup_legacy_true_v2_false"] += legacy is True and strict is False
            for phase, stages in (("setup", setup), ("first", [first] if first else [])):
                for stage in stages:
                    count.update({phase + "_" + key: value for key, value in helper.stage_controls(stage).items()})
            controls = helper.stage_controls(first)
            executed = controls["vla_executed"] + controls["non_vla_executed"] > 0
            before, after = (first.get("private_" + phase, {}).get("satisfied") for phase in ("before", "after"))
            receipt = first.get("receipt", {})
            verdict = receipt.get("place_verified")
            infra = row.get("infrastructure_failure") is True
            value = first.get("verification_measurements") or {}
            flags = flags_helper.verification_flags(value) if executed and value.get("kind") == "placement" else {}
            if infra:
                category = "infrastructure_unavailable"
            elif not first:
                category = row["status"]
            elif receipt.get("error") or receipt.get("verification") == "execution_error":
                category = "skill_execution_error"
            elif not executed:
                category = receipt.get("failure_reason") or receipt.get("reason") or "first_not_physically_executed"
            elif before is False and after is True:
                category = "newly_satisfied"
            elif before is True and after is True:
                category = "already_satisfied_preserved"
            elif after is False:
                category = "executed_endpoint_false"
            else:
                category = "private_endpoint_unknown"
            count["class:" + category] += 1
            count["first_physically_executed"] += executed and not infra
            count["infra_fault"] += infra
            fn_reason, null_reason = None, None
            if executed and not infra:
                count["private_before_false"] += before is False
                count["private_before_true"] += before is True
                count["private_after_true"] += after is True
                count["private_after_false"] += after is False
                count["public_true"] += verdict is True
                count["public_false"] += verdict is False
                count["public_null"] += verdict is None
                if isinstance(after, bool):
                    if verdict is None:
                        count["null_private_true" if after else "null_private_false"] += 1
                    else:
                        count["TP" if verdict and after else "FP" if verdict else "FN" if after else "TN"] += 1
                if strict is True:
                    count["true_setup_executed"] += 1
                    count["true_setup_initially_unsatisfied"] += before is False
                    count["true_setup_newly_satisfied"] += before is False and after is True
                    count["true_setup_preserved"] += before is True and after is True
                    count["true_setup_endpoint_false"] += after is False
                    count["true_setup_endpoint_unknown"] += after is None
                if verdict is False and after is True:
                    if flags.get("opening_ge_7cm") is False:
                        fn_reason = "release_history_or_empty_closed_gripper"
                    elif flags.get("vertical_centres_in_target") is False:
                        fn_reason = "cached_target_shell_z_or_vertical_bounds"
                    elif flags.get("footprint_gate") is False:
                        fn_reason = "footprint_overlap_gate"
                    else:
                        fn_reason = "other_saved_public_rejection"
                    count["FN_reason:" + fn_reason] += 1
                if verdict is None:
                    null_reason = receipt.get("verification_reason") or receipt.get("failure_reason") or "not_recorded"
                    count["null_reason:" + null_reason] += 1
                count["two_fresh_visible_frames"] += flags.get("two_visible_frames") is True and flags.get("distinct_source_step") is True
            record = {"case": case["name"], "group": group, "episode": case["episode"], "state_sha256": case["state_sha256"],
                      "ledger": ref["path"], "line": line_no, "status": row["status"], "exclusive_classification": category,
                      "legacy_setup": legacy, "all_current_support_v2_setup": strict, "private_before": before,
                      "private_after": after, "public_verdict": verdict, "first_physically_executed": executed,
                      "public_verification_measurements": value, "public_rejection_flags": flags,
                      "receipt": receipt, "held_after_metadata": first.get("held_after"),
                      "FN_reason": fn_reason, "null_reason": null_reason, "first_controls": controls,
                      "server_controls": row.get("server_chunk_execution"), "infra_fault": infra,
                      "original_trajectory": row["output_dir"] + "/choices.jsonl", "choices_sha256": row.get("choices_sha256")}
            old = prior_records.get(case["name"])
            if old:
                record["prior4219_saved_labels"] = {"private_before": old["private_before_label"], "private_after": old["private_after_label"],
                                                   "public_verdict": old["runtime_verdict_saved"], "old_categories": old["categories"]}
            server = row.get("server_chunk_execution")
            if server is not None:
                setup_controls = [helper.stage_controls(stage) for stage in setup]
                expected = sum(stage["vla_executed"] for stage in setup_controls) + controls["vla_executed"]
                assert server["executed_controls"] == server["requested_controls"] == expected
                assert not server["native_success_stops_chunk"] and not server["external_truncation"]
                assert not server["private_joint_or_predicate_used_for_control"]
            records.append(record)
    assert len(records) == 40
    overall = Counter()
    for count in groups.values():
        overall.update(count)

    def rates(count):
        success, n = count["true_setup_newly_satisfied"], count["true_setup_initially_unsatisfied"]
        return {"newly_satisfied_over_true_setup_initially_unsatisfied": success / n if n else None,
                "newly_satisfied_wilson95": wilson(success, n),
                "precision": count["TP"] / (count["TP"] + count["FP"]) if count["TP"] + count["FP"] else None,
                "precision_wilson95": wilson(count["TP"], count["TP"] + count["FP"]),
                "recall_measured": count["TP"] / (count["TP"] + count["FN"]) if count["TP"] + count["FN"] else None,
                "recall_measured_wilson95": wilson(count["TP"], count["TP"] + count["FN"]),
                "known_truth_agreement_including_null": (count["TP"] + count["TN"]) / (count["private_after_true"] + count["private_after_false"])
                    if count["private_after_true"] + count["private_after_false"] else None}

    result = {"job_id": 4262, "source": report["source"], "report_sha256": sha(args.report),
              "manifest_sha256": MANIFEST_SHA, "overall": dict(overall), "overall_rates": rates(overall),
              "groups": {group: {"counts": dict(count), "rates": rates(count)} for group, count in groups.items()},
              "records": records, "raw_refs": raw_refs, "script_sha256": sha(Path(__file__)),
              "remeasurement_scope": "SOURCE560 flag is enabled only in VLA arm; final two-frame visibility/freshness and previous-null case results are reported; trigger bool and pre-refresh missing observation were not logged, so no per-row causal attribution is asserted",
              "classification_scope": "saved evidence, original private labels and public verdicts retained; categories do not assert unrecorded physical causes",
              "qualification_authorized": False, "new_physical_trials": 0, "new_training_rows": 0}
    output = args.report.parent / "strict_setup_control_and_verifier_audit.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"audit": str(output), "sha256": sha(output), "overall": result["overall"]}))


if __name__ == "__main__":
    main()
