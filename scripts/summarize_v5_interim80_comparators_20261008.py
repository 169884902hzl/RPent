"""Summarize the exact startup-plus-array identities of an interim comparator."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from summarize_v5_interim80_once_20261008 import (
    annotate, group_report, key, pinned, read_rows, ref,
)


def historical(root, names):
    path = root / "results/harness_v5/freeze447_repaired_report_20261005/job3427/index.json"
    index = json.loads(path.read_text())
    rows, references = {}, [ref(path)]
    for name in names:
        group = index["groups"][name]
        pinned(group["manifest"])
        references.append(group["manifest"])
        for item in group["results"]:
            references.append(item)
            path = pinned(item) if "sha256" in item else Path(item["path"]).resolve(strict=True)
            for row in read_rows(path):
                identity = key(row["episode"])
                if identity in rows:
                    raise ValueError("Duplicated historical identity")
                rows[identity] = {"episode": row["episode"],
                    "official_success": row["result"].get("official_success") is True,
                    "output_dir": row["output_dir"], "ledger": ref(path), "historical_group": name}
    return rows, references


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--prep", type=Path, required=True)
    parser.add_argument("--cohort", choices=("A4-N", "RULE-N"), required=True)
    parser.add_argument("--startup-job", required=True)
    parser.add_argument("--array-job", required=True)
    parser.add_argument("--cohort-root", type=Path,
                        help="Explicit result directory containing startup_preflight and job<array>.")
    parser.add_argument("--current-a3-ledger", type=Path,
                        help="Complete once80 ledger for the current paired A3-N comparison.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    prep = args.prep.resolve(strict=True)
    manifest_path = prep / "manifest.json"
    index = json.loads(manifest_path.read_text())
    plans = [json.loads(pinned(item).read_text()) for item in index["files"]
             if Path(item["path"]).name.startswith(args.cohort + "_part")]
    episodes = [episode for plan in plans for episode in plan["episodes"]]
    expected = {key(episode) for episode in episodes}
    if len(episodes) != 80 or len(expected) != 80:
        raise ValueError("Comparator registration must contain all original80 exactly once")
    cohort = (args.cohort_root.resolve(strict=True) if args.cohort_root
              else root / "results/harness_v5/interim574_20261007" / args.cohort)
    contract_path = cohort / f"startup_preflight/job{args.startup_job}/part0/startup_contract.json"
    contract = json.loads(contract_path.read_text())
    if (contract.get("status") != "pass" or not contract.get("physical_actions")
            or contract["manifest_index_sha256"] != ref(manifest_path)["sha256"]
            or contract["launcher_sha256"] != index["launcher"]["sha256"]
            or contract["source_path"] != index["source_path"]):
        raise ValueError("Comparator startup contract does not match its source/launcher/registration")
    startup_ledger = pinned(contract["episodes"])
    ledgers = [startup_ledger, *sorted((cohort / f"job{args.array_job}").glob("part*/probe/episodes.jsonl"))]
    references = [ref(manifest_path), ref(contract_path), index["launcher"], index["batch_runner"],
                  ref(Path(__file__).with_name("summarize_v5_interim80_once_20261008.py"))]
    actual, infrastructure = {}, []
    expected_model = plans[0]["expected_model"]
    for ledger in ledgers:
        ledger_ref = ref(ledger)
        references.append(ledger_ref)
        for raw in read_rows(ledger):
            identity = key(raw["episode"])
            if identity not in expected or identity in actual:
                raise ValueError(f"Unexpected or duplicated comparator outcome: {identity}")
            row = annotate(raw, ledger_ref, "same_source_startup_plus_formal_array")
            choices = Path(raw["output_dir"]) / "choices.jsonl"
            if choices.exists():
                for event in read_rows(choices):
                    if event.get("answer", {}).get("model") != expected_model:
                        raise ValueError("Recorded decision model differs from its registered comparator")
            if row["accounting_group"] == "infrastructure":
                infrastructure.append(row)
            actual[identity] = row
    once = [actual.get(key(episode), {"episode": episode, "accounting_group": "pending",
            "accounting_category": "not_yet_terminal", "official_success": None}) for episode in episodes]
    aggregate_skills, cameras, versions = defaultdict(Counter), Counter(), Counter()
    for row in actual.values():
        for skill, values in row["trace"].get("skills", {}).items():
            aggregate_skills[skill].update(values)
        cameras.update(row["trace"].get("source_camera_measurement_counts", {}))
        versions.update(row["trace"].get("fusion_version_measurement_counts", {}))
    functional = {identity: row for identity, row in actual.items() if row["accounting_group"] == "functional"}
    pairings = {}
    baselines = {"historical_A3_46_of80": ("A3-place5-old40", "A3-place5-new41")}
    if args.cohort == "A4-N":
        baselines.update(historical_A4_persistence_old40=("A4-N",),
                         historical_A4_place5_old_and_new=("A4-place5-old40", "A4-place5-new41"))
    comparison_rows = {label: historical(root, groups) for label, groups in baselines.items()}
    if args.current_a3_ledger:
        ledger_ref = ref(args.current_a3_ledger)
        previous = {}
        for row in read_rows(args.current_a3_ledger):
            identity = key(row["episode"])
            if identity in previous or row.get("accounting_group") != "functional":
                raise ValueError("Current A3 ledger must contain each functional identity once")
            previous[identity] = {"episode": row["episode"],
                "official_success": row["result"].get("official_success") is True,
                "output_dir": row["output_dir"], "ledger": ledger_ref}
        if set(previous) != expected:
            raise ValueError("Current A3 ledger differs from the registered comparator states")
        comparison_rows["current_A3_N_same80"] = (previous, [ledger_ref])
    for label, (previous, refs) in comparison_rows.items():
        references.extend(refs)
        if not set(previous) <= expected:
            raise ValueError("Historical comparison differs from the registered comparator states")
        pairs = []
        for identity, row in functional.items():
            if identity not in previous:
                continue
            old = previous[identity]["official_success"]
            new = row["result"].get("official_success") is True
            transition = ("success" if old else "failure") + "_to_" + ("success" if new else "failure")
            pairs.append({"episode": row["episode"], "transition": transition,
                "previous": previous[identity], "current_output_dir": row["output_dir"],
                "current_category": row["accounting_category"],
                "trace": row["trace"] if old != new else None})
        pairings[label] = {"baseline_registered": len(previous),
            "baseline_successes": sum(row["official_success"] for row in previous.values()),
            "observed_pairs": len(pairs), "transitions": dict(Counter(row["transition"] for row in pairs)),
            "flips": [row for row in pairs if row["transition"] in ("success_to_failure", "failure_to_success")],
            "source_and_budget_differ_from_historical": True}
    summary = {"cohort": args.cohort, "scope": "interim; not freeze evidence",
        "primary_metric": "official physical success; correct_finish secondary",
        "internal_threshold_wording": "internal acceptance only", "total": group_report(once, 80),
        "correct_finish_secondary_count": sum(row["result"].get("correct_finish") is True for row in functional.values()),
        "native_official_success_count": sum(row["result"].get("official_success") is True
            and row["result"].get("native_terminated") is True for row in functional.values()),
        "successful_episodes_with_execution_error_receipt": [row["episode"] for row in functional.values()
            if row["result"].get("official_success") is True and row["trace"].get("failure_evidence", {}).get("execution_errors", 0)],
        "maximum_same_action_total": max((row["trace"].get("maximum_same_action_total", 0)
            for row in functional.values()), default=0),
        "by_suite": {suite: group_report([row for row in once if row["episode"]["suite"] == suite], 10)
                     for suite in sorted({episode["suite"] for episode in episodes})},
        "by_seed": {str(seed): group_report([row for row in once if row["episode"]["seed"] == seed], 40)
                    for seed in (40, 41)},
        "skills": {skill: dict(counts) for skill, counts in sorted(aggregate_skills.items())},
        "fusion_version_measurement_counts": dict(versions), "source_camera_measurement_counts": dict(cameras),
        "startup_included_once": True, "recorded_terminal_rows": len(actual),
        "infrastructure_attempts": infrastructure, "pending_identities": [row["episode"] for row in once
            if row["accounting_group"] != "functional"],
        "expected_model": expected_model, "source_snapshot": index["source_snapshot"],
        "alignment_notes": index["alignment_notes"], "pairings": pairings,
        "all_failures_retained": True, "data_enters_training": False}
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    outputs = []
    for name, payload in (("summary.json", summary), ("paired_flips.json", pairings)):
        path = out / name
        path.write_text(json.dumps(payload, indent=2) + "\n")
        outputs.append(ref(path))
    ledger = out / "once80.jsonl"
    ledger.write_text("".join(json.dumps(row) + "\n" for row in once))
    outputs.append(ref(ledger))
    manifest = {"generator": ref(__file__), "references": references, "outputs": outputs,
                "complete": summary["total"]["pending"] == 0, "same_state_selective_physical_reruns": False}
    path = out / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"manifest": ref(path), "total": summary["total"]}))


if __name__ == "__main__":
    main()
