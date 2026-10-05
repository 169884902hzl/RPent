"""Freeze and summarize closed prefixes of explicitly listed subtask ledgers."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registration = json.loads(args.manifest.read_text())
    plan_path = Path(registration["plan"]["path"])
    plan_bytes = plan_path.read_bytes()
    if digest(plan_bytes) != registration["plan"]["sha256"]:
        raise ValueError("registered exploration manifest changed")
    plan = json.loads(plan_bytes)
    expected = {c["name"]: c for c in plan["cases"]}
    args.output.mkdir(parents=True, exist_ok=False)
    sources, rows, seen, records = [], [], set(), []
    grouped = defaultdict(list)
    for index, ledger in enumerate(registration["ledgers"]):
        path = Path(ledger)
        raw = path.read_bytes() if path.exists() else b""
        boundary = raw.rfind(b"\n") + 1
        prefix, tail = raw[:boundary], raw[boundary:]
        snapshot = args.output / f"part{index}_closed.jsonl"
        snapshot.write_bytes(prefix)
        items = [json.loads(line) for line in prefix.splitlines() if line.strip()]
        sources.append({"part": index, "path": str(path), "exists": path.exists(),
            "read_at_utc": datetime.now(timezone.utc).isoformat(),
            "read_bytes": len(raw), "read_sha256": digest(raw),
            "closed_snapshot": str(snapshot), "closed_sha256": digest(prefix),
            "closed_rows": len(items), "unclosed_tail_bytes": len(tail),
            "unclosed_tail_sha256": digest(tail) if tail else None})
        for row in items:
            case = row["case"]
            if case != expected.get(case["name"]) or case["name"] in seen:
                raise ValueError("unregistered or duplicate closed trial")
            seen.add(case["name"])
            choices = Path(row["output_dir"]) / "choices.jsonl"
            if digest(choices.read_bytes()) != row["choices_sha256"]:
                raise ValueError("closed trial choices SHA mismatch")
            attempt = row.get("first_attempt", {})
            receipt = attempt.get("receipt", {})
            grasp = row.get("private_grasp_phase", {})
            truth = attempt.get("private_after", {}).get("satisfied")
            public = receipt.get("place_verified")
            errors = bool(row.get("raised_error") or receipt.get("error")
                or receipt.get("verification") == "execution_error")
            during = grasp.get("true_sustained_grasp_during_skill")
            end = grasp.get("true_sustained_grasp_at_end")
            if errors:
                failure = "execution_or_infrastructure_error"
            elif truth is True:
                failure = "target_satisfied"
            elif truth is None or during is None:
                failure = "private_measurement_unknown"
            elif not during:
                failure = "no_sustained_grasp_during_subtask"
            elif end:
                failure = "held_at_end_target_not_satisfied"
            else:
                failure = "sustained_grasp_then_released_target_not_satisfied"
            record = {"case": case["name"], "class": case["object_category"],
                "condition": case["condition"], "episode": case["episode"],
                "state_sha256": case.get("state_sha256"), "sustained_during": during,
                "sustained_at_end": end, "target_truth": truth, "public_place_verified": public,
                "failure": failure, "receipt_stop": receipt.get("stop"),
                "actual_actions": attempt.get("executed_actions", 0),
                "chunks": receipt.get("chunks"), "wall_s": row.get("wall_s"),
                "choices": str(choices), "choices_sha256": row["choices_sha256"]}
            records.append(record)
            grouped[(case["object_category"], case["condition"])].append(record)
            rows.append(row)
    arms = []
    for (group, condition), members in sorted(grouped.items()):
        confusion = Counter()
        states = Counter((r["episode"]["suite"], r["episode"]["task"], r["episode"]["seed"]) for r in members)
        for row in members:
            truth, public = row["target_truth"], row["public_place_verified"]
            if not isinstance(truth, bool):
                confusion["unknown_truth"] += 1
            elif not isinstance(public, bool):
                confusion["unknown_public"] += 1
            else:
                confusion["TP" if truth and public else "FN" if truth else "FP" if public else "TN"] += 1
        arms.append({"class": group, "condition": condition, "recorded": len(members),
            "planned": sum(c["object_category"] == group and c["condition"] == condition for c in expected.values()),
            "sustained_during": dict(Counter(str(r["sustained_during"]) for r in members)),
            "sustained_at_end": dict(Counter(str(r["sustained_at_end"]) for r in members)),
            "target_truth": dict(Counter(str(r["target_truth"]) for r in members)),
            "placement_verifier_confusion": dict(confusion),
            "failure_counts": dict(Counter(r["failure"] for r in members)),
            "public_stop_counts": dict(Counter(str(r["receipt_stop"]) for r in members)),
            "unique_original_states": len(states), "repeated_original_state_rows": len(members) - len(states),
            "maximum_state_repetitions": max(states.values(), default=0)})
    source = Path(registration["source"])
    report = {"scope": "immutable mid-run closed prefixes; complete subtask exploration, not independent first-grasp confirmation",
        "job": registration["job"], "plan": registration["plan"], "registration_sha256": digest(args.manifest.read_bytes()),
        "script_sha256": digest(Path(__file__).read_bytes()), "source_snapshot": str(source),
        "source_sha256": {name: digest((source / name).read_bytes()) for name in registration["source_files"]},
        "snapshot_finished_utc": datetime.now(timezone.utc).isoformat(), "sources": sources,
        "recorded": len(rows), "planned": len(expected), "complete": seen == expected.keys(),
        "choices_sha_checked": len(rows), "choices_sha_mismatches": 0, "arms": arms, "records": records,
        "qualification_authorized": False, "new_training_rows": 0, "new_physics_trials": 0,
        "limits": ["50 registered original scenes repeated twice per arm; neither 100 unique states nor a confirmation batch.",
            "Sustained grasp during a full transfer and final target success are separate; release does not erase earlier grasp success.",
            "Public receipt has place_verified, so TP/TN/FP/FN compare placement with the private target predicate, not a first-grasp verifier.",
            "Saved grasp frame witnesses cannot be compared to final released status as though they were final held-object predictions.",
            "Only closed newline-delimited records counted. Missing, empty, and unclosed tails are disclosed and not labeled failures."]}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# 3670 closed-prefix intermediate statistics", "", f"Closed {len(rows)}/{len(expected)}. No confirmation/qualification claim. Eight ledgers were explicitly listed; immutable closed snapshots retained.", "",
        "| Class/arm | Closed / planned | Sustained during | Sustained at end | Final target | Place TP/TN/FP/FN/unknown | Unique / repeat states |",
        "|---|---|---|---|---|---|---|"]
    for arm in arms:
        c = arm["placement_verifier_confusion"]
        unknown = c.get("unknown_truth", 0) + c.get("unknown_public", 0)
        lines.append(f"| {arm['class']}/{arm['condition']} | {arm['recorded']}/{arm['planned']} | {arm['sustained_during']} | {arm['sustained_at_end']} | {arm['target_truth']} | {c.get('TP',0)}/{c.get('TN',0)}/{c.get('FP',0)}/{c.get('FN',0)}/{unknown} | {arm['unique_original_states']}/{arm['repeated_original_state_rows']} |")
    lines += ["", "Confusion is placement verification versus final private target. This complete-subtask protocol does not supply a comparable first-grasp verdict. Grasp-during and grasp-at-end stay separate.", "", "Failure categories:"]
    for arm in arms:
        lines.append(f"- {arm['class']}/{arm['condition']}: {arm['failure_counts']}; stop={arm['public_stop_counts']}")
    lines += ["", f"Report SHA256: {digest((args.output/'report.json').read_bytes())}"]
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"recorded": len(rows), "planned": len(expected), "arms": arms,
        "report_sha256": digest((args.output / "report.json").read_bytes())}))


if __name__ == "__main__":
    main()
