"""Audit one completed original v9 smoke against its original v6 paired row."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def summarized(row, ledger, line, job):
    first = row["first_attempt"]
    scores = first["contact_evidence"]["private_fixture_scores"]
    if any(score["source"] != "simulation_diagnostic_only" or score["used_for_control"] for score in scores):
        raise ValueError("private endpoint diagnostics controlled runtime")
    contact = [score for score in scores if score["phase"] == "after_actual_chunk"]
    true_chunks = [score["chunk"]+1 for score in contact if score["label"]["satisfied"] is True]
    samples = first["verification_measurements"]["drawer_public_stop"]
    motions = first["motion_evidence"]
    blocks = [motion for motion in motions if motion["name"] == "vla_act_chunk"]
    # move_to's steps_used includes its final distance check; actions_used is
    # the number of actual controls. Release has only steps_used, all of which
    # execute controls in the saved runtime. Keep the original counter too.
    controls = sum(int(m.get("executed_action_count", m.get("actions_used", m.get("steps_used", 0)))) for m in motions)
    motion_counts = [{key: motion[key] for key in ("name", "steps_used", "actions_used",
                      "requested_action_count", "executed_action_count") if key in motion}
                     for motion in motions if motion["name"] != "vla_act_chunk"]
    public = []
    for sample in samples:
        chunk = sample["chunk"]
        evidence = sample["evidence"]
        geometric = evidence.get("geometric_endpoint_candidate", sample["verified"])
        public.append({"after_complete_chunks": chunk, "phase": sample.get("phase", "after_contact_block"),
            "public_endpoint": sample["verified"], "geometric_candidate": geometric,
            "stop_admitted": sample.get("stop_admitted", False), "reason": evidence.get("reason"),
            "source_step": sample["measurement"].get("source_step"),
            "moving_support_cameras": sample["measurement"].get("moving", {}).get("source_cameras", [])
                if sample["measurement"].get("moving") else [],
            "private_endpoint_after_same_saved_chunk_diagnostic_only": contact[chunk-1]["label"]["satisfied"]})
    phases = {phase: [score["label"]["satisfied"] for score in scores if score["phase"] == phase]
              for phase in ("after_public_stop_before_recovery", "after_fixture_release",
                            "after_measured_contact_clearance", "after_view_retreat_attempt")}
    server = row.get("server_chunk_execution", {})
    # A finite max160 policy loop is separate from native-success/private
    # scoring. Neither current native latch nor contact threshold marks close.
    receipt = first["receipt"]
    return {"job": job, "case": row["case"]["name"], "episode": row["case"]["episode"],
        "ledger": ledger, "line_1based": line, "state_sha256": row["case"]["state_sha256"],
        "status": row["status"], "infrastructure_failure": row.get("infrastructure_failure"),
        "eligible_physical_result": row.get("eligible_physical_result"),
        "completed_contact_chunks": len(blocks), "requested_contact_controls": sum(m["requested_action_count"] for m in blocks),
        "executed_contact_controls": sum(m["executed_action_count"] for m in blocks),
        "executed_controls_all_motions": controls, "recorded_first_executed_actions": first["executed_actions"],
        "recorded_counter_excess_final_distance_checks": first["executed_actions"]-controls,
        "noncontact_motion_counts": motion_counts,
        "executed_control_count_source": "saved executed_action_count, else saved actions_used; release-only steps_used executes every listed control",
        "private_ever_attained_in_contact": bool(true_chunks), "first_private_true_after_complete_chunk": true_chunks[0] if true_chunks else None,
        "last_private_true_after_complete_chunk": true_chunks[-1] if true_chunks else None,
        "private_true_postchunk_count": len(true_chunks), "private_after": first["private_after"],
        "private_phase_status": phases,
        "public_endpoint_counts": dict(Counter(str(sample["verified"]) for sample in samples)),
        "geometric_candidate_counts": dict(Counter(str(sample["geometric_candidate"]) for sample in public)),
        "public_abstain_reasons": dict(Counter(sample["reason"] or "none" for sample in public)),
        "public_admitted_stop_count": (sum(sample["stop_admitted"] is True for sample in public)
            if any("stop_admitted" in sample for sample in samples)
            else int(receipt.get("stop") == "measured_fixture_endpoint")),
        "public_stop_count_source": "saved v9 admission flags" if any("stop_admitted" in sample for sample in samples)
            else "saved legacy v6 receipt; old per-sample admission flag absent",
        "neutral_hold_controls": sum(m.get("executed_action_count", 0) for m in motions if m["name"] == "drawer_neutral_stability_hold"),
        "receipt": {key: receipt.get(key) for key in ("tool", "executed", "chunks", "stop", "verification", "articulate_verified")},
        "selected": first["selected"], "wall_s": row.get("case_wall_s", row["wall_s"]),
        "server_chunk_execution": server, "public_samples": public,
        "public_candidate_wording": "geometric endpoint candidates, not decision-model candidate selections"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--parent-ledger", type=Path, required=True)
    parser.add_argument("--parent-ledger-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if ref(args.manifest)["sha256"] != args.manifest_sha or ref(args.parent_ledger)["sha256"] != args.parent_ledger_sha:
        raise ValueError("registered manifest/original ledger changed")
    plan = json.loads(args.manifest.read_text())
    identity = plan["source_snapshot"]
    for item in [*identity["files"], identity["archive"]]:
        if ref(item["path"])["sha256"] != item["sha256"]:
            raise ValueError("immutable source changed")
    lines = args.ledger.read_text().splitlines()
    if len(lines) != 1:
        raise ValueError("expected one registered original smoke row")
    new = json.loads(lines[0])
    old_line, old = next((number, json.loads(line)) for number, line in enumerate(args.parent_ledger.read_text().splitlines(), 1)
                         if json.loads(line)["case"]["name"] == plan["cases"][0]["parent_case_name"])
    for key in ("episode", "setup", "state_sha256", "subtask_prompt", "mode", "object_symbol"):
        if new["case"][key] != old["case"][key]:
            raise ValueError("same-state request changed: " + key)
    args.output.mkdir(parents=True, exist_ok=False)
    rows = [summarized(old, ref(args.parent_ledger), old_line, 4327),
            summarized(new, ref(args.ledger), 1, 4515)]
    records = args.output / "paired_records.jsonl"
    records.write_text("".join(json.dumps(row)+"\n" for row in rows))
    summary = [{key: value for key, value in row.items() if key != "public_samples" and key != "server_chunk_execution"}
               for row in rows]
    report = {"version": "drawer4515-v9-single-original-development/1", "source_snapshot": identity,
        "manifest": ref(args.manifest), "producer": ref(__file__), "paired_records": ref(records), "results": summary,
        "runtime_changed": "opt-in v9 abstain on unqualified close-face identity, every-block public capture; close does not use neutral hold because no endpoint is admitted",
        "original_failed_result_preserved": True, "pair_count": 1, "new_training_rows": 0,
        "qualification_authorized": False,
        "conclusion": "v9 evidence may show physical endpoint completion, but public close verifier remains unmeasured and no close stop is qualified"}
    output = args.output / "report.json"
    output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"report": ref(output), "results": [{k:r[k] for k in ("job", "completed_contact_chunks",
        "private_ever_attained_in_contact", "first_private_true_after_complete_chunk", "public_endpoint_counts",
        "geometric_candidate_counts", "public_admitted_stop_count", "receipt")} for r in rows]}))


if __name__ == "__main__":
    main()
