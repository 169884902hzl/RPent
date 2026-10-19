# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Recount one original-task oracle cohort, retaining failures and missing cases."""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main() -> None:
    """Write a source-pinned interim report from the existing episode ledgers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replacement-receipt", type=Path, action="append", default=[],
                        help="Same-source, same-manifest replacement of unstarted cancelled shards")
    args = parser.parse_args()
    args.receipt = args.receipt.resolve()
    args.output = args.output.resolve()
    submission = json.loads(args.receipt.read_text())
    manifest = Path(submission["manifest"]["path"])
    raw_manifest = manifest.read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest() != submission["manifest"]["sha256"]:
        raise ValueError("Manifest differs from the submitted cohort")
    plan = json.loads(raw_manifest)
    if plan["training"] or plan["confirmation"]:
        raise ValueError("This report is only for development feasibility")
    sys.path.insert(0, submission["snapshot"])
    from scripts.summarize_bounded_probes import feasibility

    root = args.receipt.parents[3]
    results = root / "results/bounded_skills/feasibility_20261017"
    indices = submission["indices"]
    replacements = []
    for path in args.replacement_receipt:
        replacement = json.loads(path.read_text())
        for key in ("source_commit", "snapshot", "manifest"):
            if replacement[key] != submission[key]:
                raise ValueError(f"Replacement {key} differs: {path}")
        if not set(replacement['indices']) <= set(indices):
            raise ValueError(f"Replacement has unregistered indices: {path}")
        replacements.append(replacement)
    paths, incomplete, errors = [], [], []
    for index in indices:
        case = plan["cases"][index]
        ledger = results / f"job{submission['job']}_{index}/episodes.jsonl"
        ledgers = [ledger, *(results / f"job{replacement['job']}_{index}/episodes.jsonl"
                    for replacement in replacements if index in replacement['indices'])]
        physical = []
        for candidate_ledger in ledgers:
            rows = []
            if candidate_ledger.exists():
                for line in candidate_ledger.read_bytes().splitlines(keepends=True):
                    if line.endswith(b"\n"):
                        rows.append(json.loads(line))
            physical.extend((candidate_ledger, row) for row in rows
                            if row.get("status") == "physical_result")
            errors.extend({"index": index, "ledger": str(candidate_ledger), "record": row}
                          for row in rows if row.get("status") != "physical_result")
        if len(physical) > 1:
            raise ValueError(f"Repeated result for {ledger}")
        if physical:
            physical_ledger, row = physical[0]
            if row["case"] != case or row["arm"] != "oracle_k4" or row["pi05_calls"]:
                raise ValueError(f"Unexpected case or policy in {physical_ledger}")
            paths.append(physical_ledger)
        else:
            incomplete.append({"index": index, "case": case["name"], "ledger": str(ledger),
                               "replacement_ledgers": [str(p) for p in ledgers[1:]]})
    counted = feasibility(paths)
    # This historic manifest calls alphabet-soup cans "box_transfer". Keep
    # the case identity while correcting the table's physical-object label.
    for row in counted["rows"]:
        if row["report_category"] == "box_transfer":
            row["report_category"] = "can_transfer"
    for group in counted["summary"]:
        if group["category"] == "box_transfer":
            group["registered_category"] = "box_transfer"
            group["category"] = "can_transfer"
    report = {
        "time_pacific": datetime.now(ZoneInfo("America/Los_Angeles")).isoformat(),
        "submission": str(args.receipt),
        "source_commit": submission["source_commit"],
        "snapshot": submission["snapshot"],
        "manifest": submission["manifest"],
        "replacement_submissions": [str(p.resolve()) for p in args.replacement_receipt],
        "registered": len(indices),
        "completed_physical": len(paths),
        "incomplete": incomplete,
        "execution_errors": errors,
        "cohort": counted,
        "limitations": [
            "Completed prefix only; this is not a category qualification.",
            "Failures remain in all denominators; incomplete cases are listed separately.",
            "The alphabet-soup-can cohort does not establish cream-cheese-box coverage.",
            "This report does not combine sources or reuse startup proofs as task results.",
        ],
        "training": False,
        "confirmation": False,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in (
        "time_pacific", "source_commit", "registered", "completed_physical", "execution_errors"
    )}))
    print(json.dumps(counted["summary"]))


if __name__ == "__main__":
    main()
