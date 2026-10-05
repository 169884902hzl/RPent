"""CPU-only complete-arm audit from explicitly listed first-grasp ledgers.

Does not discover artifacts, relabel physical truth, or make new model calls.
Recorded visual verdicts and sustained-hold truth remain independent axes.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    p, scale = k / n, 1 + z * z / n
    center = (p + z * z / (2 * n)) / scale
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / scale
    return [center - radius, center + radius]


def metric(records):
    matrix = Counter(r["confusion"] for r in records)
    known = matrix["TP"] + matrix["TN"] + matrix["FP"] + matrix["FN"]
    success, negative = matrix["TP"] + matrix["FN"], matrix["TN"] + matrix["FP"]
    states = Counter(tuple(r["original_init_tuple"]) for r in records)
    state_sha = Counter(r["state_sha256"] for r in records if r["state_sha256"])
    return {
        "rows": len(records), "known_truth": known,
        "truth_success": success, "truth_success_rate": success / known if known else None,
        "truth_success_wilson95": wilson(success, known),
        "visual_verified": matrix["TP"] + matrix["FP"],
        "confusion": {key: matrix[key] for key in ("TP", "TN", "FP", "FN", "unknown_truth")},
        "verifier_agreement": (matrix["TP"] + matrix["TN"]) / known if known else None,
        "verifier_agreement_wilson95": wilson(matrix["TP"] + matrix["TN"], known),
        "false_positive": {"count": matrix["FP"], "true_negative_denominator": negative,
                           "conditional_rate": matrix["FP"] / negative if negative else None,
                           "all_known_rate": matrix["FP"] / known if known else None},
        "false_negative": {"count": matrix["FN"], "true_positive_denominator": success,
                           "conditional_rate": matrix["FN"] / success if success else None,
                           "all_known_rate": matrix["FN"] / known if known else None},
        "unique_original_init_tuples": len(states),
        "repeated_original_init_rows": sum(n - 1 for n in states.values()),
        "maximum_init_tuple_repetitions": max(states.values(), default=0),
        "state_sha_rows": sum(state_sha.values()), "unique_state_sha": len(state_sha),
        "repeated_state_sha_rows": sum(n - 1 for n in state_sha.values()),
        "contact_execution_counts": dict(Counter(r["contact_execution"] for r in records)),
        "error_rows": sum(r["execution_or_infrastructure_error"] for r in records),
        "failure_reason_counts": dict(Counter(r["failure_reason"] for r in records if r["failure_reason"])),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest_raw = args.manifest.read_bytes()
    manifest = json.loads(manifest_raw)
    args.output.mkdir(parents=True, exist_ok=False)
    sources, records, arms, seen = [], [], [], set()
    for entry in manifest["ledgers"]:
        path = Path(entry["path"])
        raw = path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise ValueError(f"ledger has an incomplete tail: {path}")
        rows = [json.loads(line) for line in raw.splitlines()]
        if len(rows) != entry["expected_rows"]:
            raise ValueError(f"expected {entry['expected_rows']} complete rows in {path}, got {len(rows)}")
        ledger_source = {**entry, "sha256": sha(raw), "bytes": len(raw), "actual_rows": len(rows)}
        sources.append(ledger_source)
        arm_records = []
        for line_number, row in enumerate(rows, 1):
            case = row["case"]
            if case["name"] in seen:
                raise ValueError(f"duplicate registered trial name: {case['name']}")
            seen.add(case["name"])
            choice_path = Path(row["output_dir"]) / "choices.jsonl"
            choice_raw = choice_path.read_bytes()
            live_sha = sha(choice_raw)
            if live_sha != row["choices_sha256"]:
                raise ValueError(f"choices SHA mismatch: {choice_path}")
            choices = [json.loads(line) for line in choice_raw.splitlines()]
            if len(choices) != 1:
                raise ValueError(f"first-grasp probe has {len(choices)} choices: {choice_path}")
            truth, visual = row.get("true_sustained_grasp"), row.get("visual_verified")
            if not isinstance(visual, bool):
                raise ValueError(f"visual verdict not boolean: {choice_path}")
            confusion = "unknown_truth" if not isinstance(truth, bool) else (
                "TP" if truth and visual else "FN" if truth else "FP" if visual else "TN")
            contact_samples = len(row.get("contact_samples", []))
            contact_actions = row.get("executed_vla_actions", 0)
            motions = choices[0].get("motion_evidence", [])
            vla_motions = [m for m in motions if m.get("name") == "vla_act_chunk"]
            saved_actions = sum(m.get("executed_action_count", 0) for m in vla_motions)
            contact_execution = "executed" if contact_samples or contact_actions or saved_actions else "not_recorded"
            receipt = row.get("first_receipt") or {}
            episode = case["episode"]
            record = {
                "job": entry["job"], "arm_kind": entry["arm_kind"], "ledger": str(path),
                "ledger_line": line_number, "trial_name": case["name"],
                "class": case["group"], "condition": case["condition"],
                "original_init_tuple": [episode["suite"], episode["task"], episode["seed"]],
                "state_sha256": case.get("state_sha256"),
                "truth": truth, "visual": visual, "confusion": confusion,
                "choices": {"path": str(choice_path), "expected_sha256": row["choices_sha256"],
                            "live_sha256": live_sha, "sha256_checked": True, "bytes": len(choice_raw)},
                "contact_execution": contact_execution,
                "contact_samples": contact_samples, "executed_vla_actions": contact_actions,
                "chunks_saved_in_last_result": row.get("chunks"),
                "execution_or_infrastructure_error": bool(row.get("raised_error")) or receipt.get("verification") == "execution_error",
                "failure_reason": receipt.get("failure_reason"),
                "contact_prompt": row.get("contact_prompt"),
                "contact_max_chunks": row.get("contact_max_chunks"),
            }
            records.append(record)
            arm_records.append(record)
        kinds = {(r["class"], r["condition"]) for r in arm_records}
        if len(kinds) != 1:
            raise ValueError(f"ledger mixes conditions: {path}")
        group, condition = next(iter(kinds))
        arms.append({"job": entry["job"], "arm_kind": entry["arm_kind"], "class": group,
                     "condition": condition, **metric(arm_records)})
    class_groups = defaultdict(list)
    for r in records:
        class_groups[(r["arm_kind"], r["class"])].append(r)
    report = {
        "scope": "complete explicitly listed original-task first-grasp arms",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": {"path": str(args.manifest), "sha256": sha(manifest_raw)},
        "script": {"path": str(Path(__file__)), "sha256": sha(Path(__file__).read_bytes())},
        "sources": sources, "choices_sha_checked": len(records), "choices_sha_mismatches": 0,
        "arms": arms,
        "by_arm_kind_and_class": [{"arm_kind": kind, "class": group, **metric(rs)}
                                  for (kind, group), rs in sorted(class_groups.items())],
        "all_rows": metric(records), "records": records,
        "new_physics_trials": 0, "new_model_calls": 0, "new_training_rows": 0,
        "limits": [
            "Exploration and confirmation arms remain separate; exploration is not qualification evidence.",
            "Wilson intervals use nominal trials; repeated original states induce within-state dependence.",
            "A last-result chunks=0 does not prove no contact: contact samples and saved executed actions are checked.",
            "Full six-class confirmation and class-specific thresholds remain required; these arms alone do not freeze a harness.",
            "Recorded physical truth and visual verdicts are preserved, not reclassified or selected by outcome.",
        ],
    }
    report_path = args.output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Complete original-task grasp arms", "", "Exploration and confirmation are separate. No new physics or changed verdicts.", "",
             "| Job | Kind | Class / condition | Truth success (Wilson 95%) | Verifier agreement | FP / true negatives | FN / true positives | Unique / repeated init rows |",
             "|---|---|---|---|---|---|---|---|"]
    for r in arms:
        lo, hi = r["truth_success_wilson95"]
        fp, fn = r["false_positive"], r["false_negative"]
        lines.append(f"| {r['job']} | {r['arm_kind']} | {r['class']} / {r['condition']} | {r['truth_success']}/{r['known_truth']} ({lo:.1%}–{hi:.1%}) | {r['verifier_agreement']:.1%} | {fp['count']}/{fp['true_negative_denominator']} | {fn['count']}/{fn['true_positive_denominator']} | {r['unique_original_init_tuples']} / {r['repeated_original_init_rows']} |")
    lines.extend(["", f"Choices SHA: {len(records)}/{len(records)} matched. Full source SHA and per-row checks are in report.json.",
                  "Wilson intervals assume nominal trials; repeated-state dependence is disclosed above.",
                  "This partial confirmation set does not meet the full six-class freeze gate."])
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"report": str(report_path), "sha256": sha(report_path.read_bytes()),
                      "choices_sha_checked": len(records), "arms": arms}))


if __name__ == "__main__":
    main()
