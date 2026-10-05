"""Freeze and summarize closed prefixes of explicitly listed subtask ledgers."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def wilson95(successes, known):
    if not known:
        return None
    z = 1.959963984540054
    fraction = successes / known
    divisor = 1 + z * z / known
    centre = (fraction + z * z / (2 * known)) / divisor
    half = z * math.sqrt(fraction * (1 - fraction) / known + z * z / (4 * known * known)) / divisor
    return [max(0., centre - half), min(1., centre + half)]


def metric_counts(members, key):
    successes = sum(r[key] is True for r in members)
    failures = sum(r[key] is False for r in members)
    known = successes + failures
    return {"rows": len(members), "successes": successes, "failures": failures,
            "unknown": len(members) - known, "known_denominator": known,
            "known_success_rate": successes / known if known else None,
            "wilson95_known": wilson95(successes, known)}


def cohort_metrics(members):
    return {key: metric_counts(members, key) for key in
            ("sustained_during", "sustained_at_end", "target_truth")}


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
                "initial_state_repetition": case.get("initial_state_repetition"),
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
        first_visits = {}
        declared_initial = [r for r in members if r["initial_state_repetition"] == 0]
        for row in declared_initial:
            identity = tuple(row["episode"][key] for key in ("suite", "task", "seed"))
            first_visits.setdefault(identity, row)
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
            "maximum_state_repetitions": max(states.values(), default=0),
            "nominal_all_rows_descriptive_only": cohort_metrics(members),
            "initial_repetition0_unique_scene_first_visits": {
                "selection": "initial_state_repetition=0; first explicit ledger occurrence per suite/task/seed; no outcome selection",
                "declared_repetition0_rows": len(declared_initial),
                "unique_scene_rows": len(first_visits),
                "duplicate_repetition0_rows": len(declared_initial) - len(first_visits),
                "metadata_unknown_rows": sum(r["initial_state_repetition"] is None for r in members),
                "metrics": cohort_metrics(list(first_visits.values()))}})
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
            "Wilson intervals for nominal repeated rows are descriptive only, not independent-sample inference or qualification.",
            "Independent first visits require initial_state_repetition=0 and unique suite/task/seed; unknown labels are excluded from known denominators and reported separately.",
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
    lines += ["", "## Wilson 95% intervals", "",
        "Nominal repeated rows are descriptive only. Repetition0 retains the first explicit occurrence of each scene; unknown is separate and excluded from known-label denominators. Neither cohort establishes qualification.", "",
        "| Class/arm | Cohort | Metric | Success / known | Unknown | Wilson95% |",
        "|---|---|---|---|---|---|"]
    for arm in arms:
        cohorts = [("nominal (descriptive)", arm["nominal_all_rows_descriptive_only"]),
                   ("rep0 unique scene", arm["initial_repetition0_unique_scene_first_visits"]["metrics"])]
        for label, metrics in cohorts:
            for metric, counts in metrics.items():
                interval = counts["wilson95_known"]
                bounds = "unknown" if interval is None else f"{interval[0]*100:.2f}–{interval[1]*100:.2f}%"
                lines.append(f"| {arm['class']}/{arm['condition']} | {label} | {metric} | {counts['successes']}/{counts['known_denominator']} | {counts['unknown']} | {bounds} |")
    lines += ["", f"Report SHA256: {digest((args.output/'report.json').read_bytes())}"]
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"recorded": len(rows), "planned": len(expected), "arms": arms,
        "report_sha256": digest((args.output / "report.json").read_bytes())}))


if __name__ == "__main__":
    main()
