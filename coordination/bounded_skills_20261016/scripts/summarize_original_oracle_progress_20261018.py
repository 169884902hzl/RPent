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
    paths, incomplete, errors = [], [], []
    for index in indices:
        case = plan["cases"][index]
        ledger = results / f"job{submission['job']}_{index}/episodes.jsonl"
        rows = []
        if ledger.exists():
            lines = ledger.read_bytes().splitlines(keepends=True)
            for line in lines:
                if not line.endswith(b"\n"):
                    continue  # A writer may still be completing its final line.
                rows.append(json.loads(line))
        physical = [r for r in rows if r.get("status") == "physical_result"]
        if len(physical) > 1:
            raise ValueError(f"Repeated result for {ledger}")
        if physical:
            row = physical[0]
            if row["case"] != case or row["arm"] != "oracle_k4" or row["pi05_calls"]:
                raise ValueError(f"Unexpected case or policy in {ledger}")
            paths.append(ledger)
        else:
            incomplete.append({"index": index, "case": case["name"], "ledger": str(ledger)})
        errors.extend({"index": index, "ledger": str(ledger), "record": row}
                      for row in rows if row.get("status") != "physical_result")
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
