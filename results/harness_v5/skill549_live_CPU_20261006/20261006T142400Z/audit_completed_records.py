"""Read only explicitly pinned completed reports and their captured ledgers."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


REMOTE_ROOT = "/public/home/sunyihan/rpent_libero_eval"
PINS = {
    4177: "36df04a494593b5842dabc05b6a35ba70484e0c96f23fa8ec289d416341d110e",
    4178: "6bb8dddbf4aacd6df9f10b4633582cece4bb000667d325a2e2aca7ed875cf365",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(root, remote):
    return root / Path(remote).relative_to(REMOTE_ROOT)


def stage_controls(stage):
    motions = (stage or {}).get("motion_evidence", [])
    chunks = [m for m in motions if m.get("name") == "vla_act_chunk"]
    return {
        "vla_chunks": len(chunks),
        "vla_requested": sum(m.get("requested_action_count", 0) for m in chunks),
        "vla_executed": sum(m.get("executed_action_count", 0) for m in chunks),
        "vla_short_chunks": sum(m.get("executed_action_count", 0) < m.get("requested_action_count", 0)
                                for m in chunks),
        "non_vla_executed": sum(m.get("executed_action_count", m.get("steps_used", 0))
                                for m in motions if m.get("name") != "vla_act_chunk"),
    }


def latched(snapshot):
    value = (snapshot or {}).get("counters", {}).get("success_once")
    return any(value) if isinstance(value, list) else value is True


def projected_stage(stage):
    if not stage:
        return None
    receipt = stage.get("receipt", {})
    contact = stage.get("contact_evidence", {})
    approach = receipt.get("fixture_handle_approach") or contact.get("approach") or {}
    chunks = [m for m in stage.get("motion_evidence", []) if m.get("name") == "vla_act_chunk"]
    return {
        "selected": stage.get("selected"),
        "controls": stage_controls(stage),
        "private_before": stage.get("private_before"),
        "private_after": stage.get("private_after"),
        "private_setup_hold_legacy": stage.get("private_true_sustained_grasp"),
        "private_setup_hold_v2": stage.get("private_hold_truth_v2", {}).get("success"),
        "public_verification": receipt.get("verification"),
        "public_verdict": receipt.get("place_verified", receipt.get("articulate_verified")),
        "public_reason": receipt.get("failure_reason") or receipt.get("reason"),
        "stop_condition": receipt.get("stop_condition"),
        "recorded_contact_actions": contact.get("executed_vla_actions"),
        "contact_ready": approach.get("ready_for_contact"),
        "contact_instruction": stage.get("contact_instruction"),
        "first_chunk_prompt": chunks[0].get("instruction") if chunks else None,
        "first_chunk_eef": chunks[0].get("final_eef_pos") if chunks else None,
        "last_chunk_eef": chunks[-1].get("final_eef_pos") if chunks else None,
        "measured_handle_before": approach.get("before", {}).get("pose"),
        "measured_handle_after": approach.get("after_wrist_refinement", {}).get("pose"),
        "contact_target_xyz": approach.get("target_xyz"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    directory = args.root / "results/harness_v5/skill549_live_CPU_20261006/20261006T142400Z"
    all_rows = []
    for job, expected in PINS.items():
        report_path = directory / f"job{job}/report.json"
        assert sha(report_path) == expected
        report = json.loads(report_path.read_text())
        groups = defaultdict(Counter)
        records, raw_files = [], []
        for ref in report["ledgers"]:
            path = local_path(args.root, ref["path"])
            assert sha(path) == ref["sha256"]
            raw_files.append({"remote_path": ref["path"], "local_path": str(path),
                              "sha256": ref["sha256"], "size_bytes": path.stat().st_size})
            for line_number, line in enumerate(path.read_text().splitlines(), 1):
                row = json.loads(line)
                case = row["case"]
                group = case["type"] + "/" + case["condition"]
                counter = groups[group]
                setup = [projected_stage(stage) for stage in row.get("setup", [])]
                first = projected_stage(row.get("first_attempt"))
                record = {"case": case["name"], "group": group, "episode": case["episode"],
                          "state_sha256": case.get("state_sha256"), "status": row["status"],
                          "captured_ledger": ref["path"], "line": line_number,
                          "native_success_before_first": latched(row.get("before_first_attempt_snapshot")),
                          "native_success_latched_final": row.get("native_original_success_latched"),
                          "setup": setup, "first": first}
                counter["cases"] += 1
                counter["native_success_before_first"] += record["native_success_before_first"]
                counter["native_success_latched_final"] += record["native_success_latched_final"] is True
                for stage_name, stages in (("setup", setup), ("first", [first] if first else [])):
                    for stage in stages:
                        for field, value in stage["controls"].items():
                            counter[stage_name + "_" + field] += value
                        counter[stage_name + "_cases_with_short_chunks"] += stage["controls"]["vla_short_chunks"] > 0
                if setup:
                    setup_truth = setup[-1]["private_setup_hold_v2"]
                    counter["setup_v2_true"] += setup_truth is True
                    counter["setup_v2_false"] += setup_truth is False
                    counter["setup_legacy_true"] += setup[-1]["private_setup_hold_legacy"] is True
                    counter["setup_legacy_false"] += setup[-1]["private_setup_hold_legacy"] is False
                    record["setup_truth_v2"] = setup_truth
                if first is None:
                    classification = row["status"]
                else:
                    before = (first["private_before"] or {}).get("satisfied")
                    after = (first["private_after"] or {}).get("satisfied")
                    controls = first["controls"]
                    if job == 4178 and controls["vla_executed"] == 0:
                        classification = first["public_reason"] or "contact_not_executed"
                    elif after is True and before is False:
                        classification = "newly_satisfied"
                    elif after is True and before is True:
                        classification = "already_satisfied_preserved"
                    elif after is False:
                        classification = "executed_endpoint_not_satisfied"
                    else:
                        classification = "executed_endpoint_unknown"
                    counter["first_physical_motion_cases"] += controls["vla_executed"] + controls["non_vla_executed"] > 0
                    counter["first_vla_contact_cases"] += controls["vla_executed"] > 0
                    counter["first_before_false"] += before is False
                    counter["first_before_true"] += before is True
                    counter["first_endpoint_true"] += after is True
                    counter["first_endpoint_false"] += after is False
                    counter["public_true"] += first["public_verdict"] is True
                    counter["public_false"] += first["public_verdict"] is False
                    counter["public_null"] += first["public_verdict"] is None
                    if setup and record["setup_truth_v2"] is True:
                        counter["true_setup_v2_first"] += 1
                        counter["true_setup_v2_endpoint_true"] += after is True
                        counter["true_setup_v2_before_false"] += before is False
                        counter["true_setup_v2_newly_satisfied"] += before is False and after is True
                record["exclusive_classification"] = classification
                counter["class:" + classification] += 1
                records.append(record)
                all_rows.append(record)
        result = {
            "scope": "completed selection/smoke records only; no replay, GPU, label change, confirmation or freeze",
            "job_id": job, "report": str(report_path), "report_sha256": expected,
            "source": report["source"], "script_sha256": sha(Path(__file__)),
            "classification_rule": "VLA contact requires recorded executed VLA controls; motor approach alone is not contact; before/after endpoint and setup truth remain separate",
            "groups": {key: dict(value) for key, value in groups.items()},
            "records": records,
            "raw_files": raw_files,
            "raw_total_size_bytes": sum(ref["size_bytes"] for ref in raw_files),
            "raw_github_policy": "raw JSONL retained on both hosts with verified SHA; not staged or archived in Git",
            "legacy_4177_limit": "SOURCE548 short chunks remain; absence of contact_vla field is unknown, not zero; SOURCE553 same40 is a future independent development rerun",
        }
        output = directory / f"job{job}/control_and_exclusive_audit.json"
        output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"job": job, "report": str(output), "sha256": sha(output),
                          "groups": result["groups"]}))


if __name__ == "__main__":
    main()
