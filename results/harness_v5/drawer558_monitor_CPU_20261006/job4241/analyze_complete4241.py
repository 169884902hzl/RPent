"""Project explicit completed selection records; preserve every original verdict."""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path


REMOTE_ROOT = "/public/home/sunyihan/rpent_libero_eval"
REPORT_SHA = "3effa235698461c8339fd0237138866ef05bbd178306015b8e316eb06857432a"
MANIFEST_SHA = "2b29f8b2415ab01c29b344debd646e1f742f718584fed7a8dc2662724502faaa"
PRIOR_AUDIT_SHA = "625d89b3f7ae5a8f976c304ea5668bf9aa7ac38e6e0a43220194dc4c7c32be89"
HELPER_SHA = "b29487fba4ef8ed265d05f877ac2f44bdd59d0ad50e177a710efa7def9a5709a"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    directory = root / "results/harness_v5/drawer558_monitor_CPU_20261006/job4241"
    local = lambda path: root / Path(path).relative_to(REMOTE_ROOT)
    report_path = directory / "report.json"
    assert sha(report_path) == REPORT_SHA
    report = json.loads(report_path.read_text())
    assert report["complete"] and report["overall"]["recorded"] == 5
    manifest_ref = report["manifests"][0]
    assert manifest_ref["sha256"] == MANIFEST_SHA
    plan = json.loads(local(manifest_ref["path"]).read_text())
    assert sha(local(manifest_ref["path"])) == MANIFEST_SHA
    helper_path = root / "results/harness_v5/skill549_live_CPU_20261006/20261006T142400Z/audit_completed_records.py"
    assert sha(helper_path) == HELPER_SHA
    spec = importlib.util.spec_from_file_location("completed_controls", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    prior_directory = root / "results/harness_v5/drawer557_monitor_CPU_20261006/20261006T151308Z/job4235"
    prior_path = prior_directory / "paired_control_and_measurement_audit.json"
    assert sha(prior_path) == PRIOR_AUDIT_SHA
    prior = json.loads(prior_path.read_text())
    prior_records = {record["episode"]["seed"]: record for record in prior["records"]
                     if record["method"] == "native_original160"}
    raw_refs = report["ledgers"] + report["infrastructure_ledgers"]
    for ref in raw_refs:
        assert sha(local(ref["path"])) == ref["sha256"]
    records, public_refs, totals, flips = [], [], Counter(), []

    def public_refs_from(value, case, phase):
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
                public_refs.append({"path": value["path"], "sha256": value["sha256"],
                                    "case": case, "phase": phase})
            for child in value.values():
                public_refs_from(child, case, phase)
        elif isinstance(value, list):
            for child in value:
                public_refs_from(child, case, phase)

    for ref in report["ledgers"]:
        for line_no, line in enumerate(local(ref["path"]).read_text().splitlines(), 1):
            row = json.loads(line)
            case, stage = row["case"], row["first_attempt"]
            seed, receipt = case["episode"]["seed"], stage["receipt"]
            controls = helper.stage_controls(stage)
            server = row["server_chunk_execution"]
            assert controls["vla_chunks"] == 160
            assert controls["vla_requested"] == controls["vla_executed"] == 800
            assert controls["vla_short_chunks"] == 0
            assert server["requested_controls"] == server["executed_controls"] == 800
            assert not any(server[key] for key in ("native_success_stops_chunk", "external_truncation",
                                                 "private_joint_or_predicate_used_for_control"))
            assert stage["private_before"]["satisfied"] is False
            assert row["infrastructure_failure"] is False and row["physical_failures_retried"] is False
            chunks = [motion for motion in stage["motion_evidence"] if motion["name"] == "vla_act_chunk"]
            assert {motion["instruction"] for motion in chunks} == {case["subtask_prompt"]}
            geometry = stage["verification_measurements"]["articulation"]
            for phase in ("before", "after"):
                public_refs_from(geometry.get(phase), case["name"], phase)
            selected = receipt["object"]
            entities = {phase: next((entity for entity in stage["public_" + phase]["entities"]
                                    if entity["id"] == selected), None) for phase in ("before", "after")}
            before, after = stage["private_before"], stage["private_after"]
            verdict = receipt.get("articulate_verified")
            totals.update(controls)
            totals["private_true"] += after["satisfied"] is True
            totals["private_false"] += after["satisfied"] is False
            totals["public_true"] += verdict is True
            totals["public_false"] += verdict is False
            totals["public_null"] += verdict is None
            record = {"case": case["name"], "episode": case["episode"], "state_sha256": case["state_sha256"],
                      "captured_ledger": ref["path"], "line": line_no, "status": row["status"],
                      "private_before": before, "private_after": after, "public_verdict": verdict,
                      "public_measurement": geometry, "selected_public_entity": entities,
                      "public_measurement_epochs": {phase: (geometry.get(phase) or {}).get("source_step")
                                                    for phase in ("before", "after")},
                      "native_success_before_first": helper.latched(row["before_first_attempt_snapshot"]),
                      "native_success_latched_final": row["native_original_success_latched"],
                      "registered_prompt": case["subtask_prompt"], "controls": controls,
                      "server_chunk_execution": server, "post_contact_recovery": receipt.get("post_contact_recovery"),
                      "receipt": receipt, "infra_fault": row["infrastructure_failure"],
                      "physical_failures_retried": row["physical_failures_retried"], "wall_s": row["case_wall_s"],
                      "action_sequence_sha256": canonical_sha([motion["actions"] for motion in chunks]),
                      "choices_sha256": row["choices_sha256"], "original_trajectory": row["output_dir"] + "/choices.jsonl"}
            old = prior_records[seed]
            assert old["state_sha256"] == case["state_sha256"]
            record["paired_prior4235"] = {"private_after": old["private_after_label"], "public_verdict": old["runtime_verdict"],
                                          "measured_extension_cm": old["body_endpoint"].get("measured_extension_cm")}
            if old["private_after_label"]["satisfied"] is True and after["satisfied"] is False:
                prior_row = json.loads(local(old["captured_ledger"]).read_text().splitlines()[old["line"] - 1])
                old_stage = prior_row["first_attempt"]
                old_chunks = [motion for motion in old_stage["motion_evidence"] if motion["name"] == "vla_act_chunk"]
                action_difference = [index for index, (a, b) in enumerate(zip(old_chunks, chunks))
                                     if a["actions"] != b["actions"]]
                flips.append({"seed": seed, "state_sha256": case["state_sha256"],
                              "initial_snapshot_equal": prior_row["initial_snapshot"] == row["initial_snapshot"],
                              "before_first_snapshot_equal": prior_row["before_first_attempt_snapshot"] == row["before_first_attempt_snapshot"],
                              "public_before_equal": old_stage["public_before"] == stage["public_before"],
                              "private_before_equal": old_stage["private_before"] == before,
                              "initial_snapshot_canonical_sha256": canonical_sha(row["initial_snapshot"]),
                              "prompt_equal": {m["instruction"] for m in old_chunks} == {m["instruction"] for m in chunks},
                              "VLA_controls_both": [helper.stage_controls(old_stage), controls],
                              "different_action_chunks": len(action_difference),
                              "first_different_action_chunk_zero_based": action_difference[0] if action_difference else None,
                              "first_actions": {"4235": old_chunks[0]["actions"], "4241": chunks[0]["actions"]},
                              "private_before_after": {"4235": [old_stage["private_before"], old_stage["private_after"]],
                                                       "4241": [before, after]},
                              "server_chunks": {"4235": prior_row["server_chunk_execution"], "4241": server},
                              "post_recovery_both": [old_stage["receipt"].get("post_contact_recovery"), receipt.get("post_contact_recovery")],
                              "last_chunk_before_recovery": {"4235": {k: v for k, v in old_chunks[-1].items() if k != "actions"},
                                                             "4241": {k: v for k, v in chunks[-1].items() if k != "actions"}},
                              "non_VLA_motions": {"4235": [{k: m.get(k) for k in ("name", "target_xyz", "steps_used")}
                                                           for m in old_stage["motion_evidence"] if m["name"] != "vla_act_chunk"],
                                                  "4241": [{k: m.get(k) for k in ("name", "target_xyz", "steps_used")}
                                                           for m in stage["motion_evidence"] if m["name"] != "vla_act_chunk"]},
                              "scope": "same measured start and literal prompt, but different first sampled action sequence; no per-chunk private joint timeline or policy RNG state was recorded; binding does not explain this physical flip from the available evidence"})
            records.append(record)
    assert len(records) == 5 and len({row["state_sha256"] for row in records}) == 5
    assert totals["vla_requested"] == totals["vla_executed"] == 4000
    audit = {"job_id": 4241, "source": plan["source_snapshot"], "report_sha256": REPORT_SHA,
             "manifest": manifest_ref, "prior4235_audit": {"path": str(prior_path).replace(str(root), REMOTE_ROOT, 1), "sha256": PRIOR_AUDIT_SHA},
             "totals": dict(totals), "records": records, "paired_physical_flips": flips,
             "public_measurement_ref_count": len(public_refs), "unique_public_paths": len({r["path"] for r in public_refs}),
             "qualification_authorized": False, "source_or_manifest_modified": False,
             "new_physical_trials": 0, "new_training_rows": 0,
             "scope": "five already-visited selection states, original endpoint and public verdict retained; no confirmation, relabeling, replay, GPU use or freeze"}
    write_json(directory / "control_and_endpoint_audit.json", audit)
    write_json(directory / "public_measurement_refs.json", {"refs": public_refs})
    print(json.dumps({"audit_sha256": sha(directory / "control_and_endpoint_audit.json"), "totals": audit["totals"],
                      "physical_flips": len(flips), "public_refs": len(public_refs)}))


if __name__ == "__main__":
    main()
