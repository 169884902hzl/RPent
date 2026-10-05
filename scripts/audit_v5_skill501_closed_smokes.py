"""Audit two explicitly registered original-skill smokes and closed box trials.

This CPU report preserves private diagnostic truth and public receipts. It
does not change any physical record, replay a trial, or admit training data.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from scripts.probe_v5_skill501_original import executed_actions, sha
from scripts.summarize_v5_grasp_closed_ledgers import metric
from scripts.summarize_v5_skill501_original import fixture_mode_audit, summarize


def read_ledger(path):
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError(f"incomplete ledger tail: {path}")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def skill_record(row):
    stage = row.get("first_attempt")
    receipt = stage.get("receipt", {}) if stage else {}
    before = stage.get("private_before", {}).get("satisfied") if stage else None
    after = stage.get("private_after", {}).get("satisfied") if stage else None
    actions = executed_actions(stage["motion_evidence"]) if stage else 0
    if not actions:
        category = "not_executed"
    elif before is True:
        category = "already_satisfied_preserved" if after is True else "already_satisfied_regressed" if after is False else "private_truth_unknown"
    elif before is False:
        category = "newly_satisfied" if after is True else "physical_failure" if after is False else "private_truth_unknown"
    else:
        category = "initial_private_truth_unknown"
    raw_path = Path(row["output_dir"]) / "private_skill_diagnostic.json"
    if json.loads(raw_path.read_text()) != row:
        raise ValueError(f"private diagnostic differs from ledger: {raw_path}")
    phase = row.get("private_grasp_phase", {})
    return {"case": row["case"]["name"], "kind": row["case"]["kind"], "type": row["case"]["type"],
            "condition": row["case"]["condition"], "status": row["status"], "actions": actions,
            "private_before": before, "private_after": after, "physical_class": category,
            "receipt": receipt, "raised_error": row.get("raised_error"),
            "setup": [{"selected": stage["selected"], "receipt": stage["receipt"],
                       "private_before": stage.get("private_before", {}),
                       "private_after": stage.get("private_after", {}),
                       "private_true_sustained_grasp": stage.get("private_true_sustained_grasp")}
                      for stage in row.get("setup", [])],
            "fixture_mode_audit": fixture_mode_audit(row),
            "contact_evidence": stage.get("contact_evidence", {}) if stage else {},
            "grasp_during_skill": phase.get("true_sustained_grasp_during_skill"),
            "grasp_at_end": phase.get("true_sustained_grasp_at_end"), "wall_s": row["wall_s"],
            "raw_path": str(raw_path), "raw_sha256": sha(raw_path),
            "choices_sha256": row["choices_sha256"]}


def skill_run(root, base_name, job, source_name):
    base = root / "results/harness_v5" / base_name
    manifests = [base / "preparation" / name for name in
                 ("fixtures_smoke.json", "place_smoke.json", "grasp_subtask_smoke.json")]
    ledgers = [base / f"smoke_job{job}/part{part}/episodes.jsonl" for part in range(5)]
    report = summarize(manifests, ledgers)
    if not report["complete"] or report["overall"]["recorded"] != 20:
        raise ValueError(f"job {job} is not a complete registered 20-case smoke")
    rows = [row for path in ledgers for row in read_ledger(path)]
    records = [skill_record(row) for row in rows]
    fixture_records = [row for row in records if row["kind"] == "articulate"]
    place_rows = [row for row in rows if (row.get("first_attempt") or {}).get("receipt", {}).get("tool")
                  in {"place", "vla_subtask"} and row["case"]["kind"] in {"place", "grasp_then_subtask"}]
    from scripts.summarize_v5_skill501_original import metrics
    report.update(job=job, records=records,
        fixture_physical_classes=dict(Counter(row["physical_class"] for row in fixture_records)),
        placement_receipts_only=metrics(place_rows, len(place_rows)),
        source_snapshot=str(root / source_name),
        source_sha256={name: sha(root / source_name / name) for name in
            ("scripts/probe_v5_skill501_original.py", "robots/libero/v5_runtime.py",
             "robots/libero/v5_state.py", "robots/libero/v5_verification.py",
             "robots/libero/v5_subtasks.py", "robots/libero/v5_oracle_policy.py")})
    return report


def paired_smokes(root):
    old = skill_run(root, "skill511_json_repaired_smoke_20261005", 3637,
                    "source_v5_skill511_json_repaired_20261005")
    new = skill_run(root, "skill515_public_endpoint_smoke_20261005", 3643,
                    "source_v5_skill515_public_endpoint_20261005")
    old_rows = {row["case"]: row for row in old["records"]}
    new_rows = {row["case"]: row for row in new["records"]}
    if old_rows.keys() != new_rows.keys():
        raise ValueError("smokes do not share the same registered cases")
    pairs = [{"case": name, "old": old_rows[name], "new": new_rows[name],
              "private_after_changed": old_rows[name]["private_after"] != new_rows[name]["private_after"],
              "raw_receipt_changed": old_rows[name]["receipt"] != new_rows[name]["receipt"]}
             for name in sorted(old_rows)]
    return {"scope": "complete paired original development smokes; no qualification", "old": old, "new": new,
            "pairs": pairs, "limits": [
                "Identical registered official initial states; Pi0.5 policy noise is not fixed across these jobs.",
                "Public null verdicts remain unmeasured, never filled from simulator truth.",
                "Prior-satisfied starts are distinct from newly completed skills; setup predicates use their own requested mode.",
                "One case per arm cannot satisfy independent 100-attempt confirmation gates."],
            "new_training_rows": 0, "new_physical_trials": 0, "qualification_authorized": False}


def box_confirmation(root, group="box"):
    base = root / "results/harness_v5"
    full_path = base / "grasp492_first4_confirmation_20261005/preparation/full.json"
    if group == "box":
        remaining_path = base / "grasp510_box_remaining_20261005/preparation/remaining52.json"
        old_path = base / "grasp492_first4_confirmation_20261005/full_job3619/part2/episodes.jsonl"
        new_path = base / "grasp510_box_remaining_20261005/remaining_job3636/part2/episodes.jsonl"
        old_n, new_n, old_job, new_job = 48, 52, "3619_2", "3636"
    elif group == "mug":
        remaining_path = base / "grasp512_mug_unvisited_resume_20261005/preparation/resume.json"
        old_path = base / "grasp507_mug_private_binding_retry_20261005/retry_job3631/part3/episodes.jsonl"
        new_path = base / "grasp512_mug_unvisited_resume_20261005/resume_job3642/part0/episodes.jsonl"
        old_n, new_n, old_job, new_job = 21, 79, "3631", "3642"
    else:
        raise ValueError("only closed registered box or mug continuations")
    full, remaining = json.loads(full_path.read_text()), json.loads(remaining_path.read_text())
    registry = {case["name"]: case for case in full["cases"] if case["group"] == group}
    ledger_sha = (remaining["continuation"]["original_ledger_sha256"] if group == "box" else
                  remaining["resume_private_instrument_only"]["visited_ledger"]["sha256"])
    manifest_sha = (remaining["continuation"]["original_manifest_sha256"] if group == "box" else
                    remaining["parent_manifest"]["sha256"])
    if sha(old_path) != ledger_sha:
        raise ValueError("original partial ledger changed")
    if sha(full_path) != manifest_sha:
        raise ValueError("original registered manifest changed")
    if len(registry) != 100 or len(remaining["cases"]) != new_n:
        raise ValueError("registered confirmation/continuation counts changed")
    for case in remaining["cases"]:
        if case != registry.get(case["name"]):
            raise ValueError("continuation changed a registered case")
    records, seen = [], set()
    for path, expected, job in ((old_path, old_n, old_job), (new_path, new_n, new_job)):
        rows = read_ledger(path)
        if len(rows) != expected:
            raise ValueError(f"closed ledger has {len(rows)} rows, expected {expected}: {path}")
        for line, row in enumerate(rows, 1):
            case = row["case"]
            if case != registry.get(case["name"]) or case["name"] in seen:
                raise ValueError("changed or repeated registered confirmation state")
            seen.add(case["name"])
            choice_path = Path(row["output_dir"]) / "choices.jsonl"
            if sha(choice_path) != row["choices_sha256"]:
                raise ValueError(f"choices SHA mismatch: {choice_path}")
            truth, visual = row.get("true_sustained_grasp"), row.get("visual_verified")
            if not isinstance(visual, bool):
                raise ValueError("recorded visual verdict is not boolean")
            confusion = "unknown_truth" if not isinstance(truth, bool) else (
                "TP" if truth and visual else "FN" if truth else "FP" if visual else "TN")
            contact = bool(row.get("contact_samples") or row.get("executed_vla_actions"))
            records.append({"job": job, "ledger": str(path), "ledger_line": line,
                "trial_name": case["name"], "trial_index": case["trial_index"],
                "original_init_tuple": [case["episode"][key] for key in ("suite", "task", "seed")],
                "state_sha256": case["state_sha256"], "truth": truth, "visual": visual,
                "confusion": confusion, "contact_execution": "executed" if contact else "not_recorded",
                "contact_samples": len(row.get("contact_samples", [])),
                "choices": {"path": str(choice_path), "sha256": sha(choice_path),
                            "sha256_checked": True, "bytes": choice_path.stat().st_size},
                "execution_or_infrastructure_error": bool(row.get("raised_error")),
                "raised_error": row.get("raised_error"),
                "failure_reason": row.get("first_receipt", {}).get("failure_reason")})
    if seen != registry.keys():
        raise ValueError("not all 100 preregistered confirmation trials were preserved")
    result = metric(records)
    result.update(truth_success_over_planned_lower_bound=result["truth_success"] / 100,
                  truth_success_over_planned_upper_bound=(result["truth_success"] + 100 - result["known_truth"]) / 100)
    return {"scope": f"{group} confirmation partial known truth; original unknown not replayed", "planned": 100,
            "original_known": metric([record for record in records if record["job"] == old_job and record["truth"] is not None]),
            "continuation": metric([record for record in records if record["job"] == new_job]),
            "overall": result, "unknown_records": [record for record in records if record["truth"] is None],
            "manifest": {"path": str(full_path), "sha256": sha(full_path)},
            "remaining_manifest": {"path": str(remaining_path), "sha256": sha(remaining_path)},
            "ledgers": [{"path": str(path), "sha256": sha(path)} for path in (old_path, new_path)],
            "records": records, "choices_sha_checked": 100, "choices_sha_mismatches": 0,
            "qualification_authorized": False, "new_physical_trials": 0, "new_training_rows": 0,
            "limits": ["One executed original trial has unknown private truth after a metrology exception; it is not relabeled a failure or replaced.",
                       "The 99 known trials are not a complete 100-trial confirmation or a full six-class qualification.",
                       "Sustained-hold truth and public verification are separate; Wilson denominator uses known truth only."]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paired, box = paired_smokes(args.root), box_confirmation(args.root)
    args.output.mkdir(parents=True, exist_ok=False)
    provenance = {"script": str(Path(__file__)), "sha256": sha(__file__), "python": sys.executable}
    for name, report in (("paired_smokes.json", paired), ("box_confirmation.json", box)):
        report["summary_source"] = provenance
        (args.output / name).write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Closed original-skill development audit", "", "No replay, qualification, freeze, or new training rows.", "",
             "| Case | 3637 physical class / predicate | 3643 physical class / predicate | 3643 public verification |", "|---|---|---|---|"]
    for pair in paired["pairs"]:
        old, new = pair["old"], pair["new"]
        receipt = new["receipt"]
        verdict = receipt.get("articulate_verified", receipt.get("place_verified", receipt.get("grasp_verified")))
        lines.append(f"| {pair['case']} | {old['physical_class']}: {old['private_before']} -> {old['private_after']} | {new['physical_class']}: {new['private_before']} -> {new['private_after']} | {verdict} ({receipt.get('verification')}) |")
    lines += ["", "Fixture classes: " + json.dumps(paired["new"]["fixture_physical_classes"], sort_keys=True) + ".",
              "Placement-only confusion: " + json.dumps(paired["new"]["placement_receipts_only"]["confusion"], sort_keys=True) + ".",
              "Public null stays unmeasured. Macro final release does not negate an earlier sustained grasp.",
              "", "Box: original 47 known + continuation 52 known + one preserved executed unknown.",
              "Known truth: " + json.dumps(box["overall"], sort_keys=True) + ".",
              "No unknown replacement and no complete-confirmation claim. Per-case raw paths, original/new receipts and SHA256 are in the JSON reports."]
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"output": str(args.output), "paired_sha256": sha(args.output / "paired_smokes.json"),
                      "box_sha256": sha(args.output / "box_confirmation.json"), "box_overall": box["overall"],
                      "fixture_classes": paired["new"]["fixture_physical_classes"]}))


if __name__ == "__main__":
    main()
