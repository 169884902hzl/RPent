"""Retain paired regressions and the explicit single-flag prefix diagnoses."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def descriptor(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pairs = json.loads(args.pairs.read_text())["cases"]
    plan = json.loads(args.manifest.read_text())
    expected = {case["name"]: case for case in plan["cases"]}
    recorded, sources = {}, []
    for ledger in args.ledger:
        sources.append(descriptor(ledger))
        for line in ledger.read_text().splitlines():
            row = json.loads(line)
            name = row["case"]["name"]
            if row["case"] != expected.get(name) or name in recorded:
                raise ValueError("unregistered or duplicate prefix replay")
            recorded[name] = row
    if recorded.keys() != expected.keys():
        raise ValueError("single-flag prefix matrix is incomplete")
    cases, totals = [], Counter()
    for pair in pairs:
        counts = Counter()
        for event in pair["after"]["sequence"]:
            receipt = event["receipt"]
            tool = receipt["tool"]
            if tool in ("grasp", "regrasp_restage"):
                counts["grasp_attempts"] += 1
                if receipt.get("grasp_verified") is True:
                    counts["grasp_verified"] += 1
                else:
                    reason = receipt.get("stop", receipt.get("failure_reason", receipt["verification"]))
                    counts["grasp:" + reason] += 1
            else:
                counts[tool + ":" + receipt["verification"]] += 1
        totals.update(counts)
        rows = [row for row in recorded.values() if row["case"]["episode"] == pair["episode"]]
        cases.append({**pair, "observed_failure_counts": dict(counts),
                      "prefix_matrix": {row["case"]["variant"]: {
                          "diagnostic_outcome": row["diagnostic_outcome"],
                          "official_success": row["result"].get("official_success"),
                          "raised_error": row["raised_error"],
                          "recorded_decisions": row["recorded_decisions"],
                          "receipts": row["receipts"],
                          "trace": descriptor(Path(row["output_dir"]) / "choices.jsonl"),
                      } for row in rows}})
    report = {"scope": "development causal diagnosis; prefixes are not model scores",
              "paired_regressions": descriptor(args.pairs), "manifest": descriptor(args.manifest),
              "sources": sources, "prefixes": len(recorded), "regressed_episodes": len(cases),
              "observed_failure_totals": dict(totals), "cases": cases,
              "causal_conclusion": "not established by these prefixes; contact policy noise was not paired",
              "memory_cards": "absent in both live model groups",
              "freeze_eligible": False, "script": descriptor(Path(__file__))}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# A4 old40 paired regressions and single-flag prefixes", "",
             "A4 changed from 25/40 to 18/40: nine regressions and two gains.",
             "Budget exhaustion is the termination, not the physical root cause.",
             "The 72 physical prefixes do not establish a unique causal switch;",
             "the contact policy's noise was not paired. No memory cards were active.", "",
             "| Episode | Grasp verified / attempts | Observed grasp failures | Prefix native successes |",
             "|---|---:|---|---|"]
    for case in cases:
        ep, counts = case["episode"], case["observed_failure_counts"]
        failures = ", ".join(f"{k.removeprefix('grasp:')}={v}" for k, v in counts.items() if k.startswith("grasp:"))
        successes = ", ".join(k for k, v in case["prefix_matrix"].items() if v["official_success"]) or "none"
        lines.append(f"| {ep['suite']} t{ep['task']} init{ep['seed']} | {counts.get('grasp_verified', 0)}/{counts.get('grasp_attempts', 0)} | {failures} | {successes} |")
    lines.extend(["", "Raw paired sequences and every replay receipt remain in report.json.",
                  "Next decision depends on the original-task paired grasp experiment,",
                  "followed by complete new41 and old40 A3/A4 evaluations."])
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"prefixes": len(recorded), "regressions": len(cases),
                      "totals": dict(totals), "report": descriptor(args.output / "report.json")}))


if __name__ == "__main__":
    main()
