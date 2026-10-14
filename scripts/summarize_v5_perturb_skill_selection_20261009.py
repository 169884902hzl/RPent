"""Report pending selection coverage and post-receipt private skill labels."""

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path

from scripts.summarize_v5_skill501_original import infrastructure_result, metrics, wilson


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    planned, recorded, references, infrastructure = {}, {}, [], []
    for manifest in sorted(args.root.glob("*/preparation/selection.json")):
        plan = json.loads(manifest.read_text())
        if plan["confirmation"] or plan["training_allowed"] or plan["PRO_files_read"]:
            raise ValueError("this report accepts only original perturbation selection")
        references.append(ref(manifest))
        for case in plan["cases"]:
            if case["name"] in planned:
                raise ValueError("duplicate registered case")
            planned[case["name"]] = case
    for ledger in sorted(args.root.rglob("episodes.jsonl")):
        raw = ledger.read_bytes()
        boundary = raw.rfind(b"\n") + 1
        references.append(ref(ledger))
        for line in raw[:boundary].splitlines():
            row = json.loads(line)
            name = row["case"]["name"]
            if row["case"] != planned.get(name):
                raise ValueError("unregistered or changed physical case")
            if infrastructure_result(row):
                infrastructure.append({"case": name, "ledger": ref(ledger), "status": row["status"]})
                continue
            if name in recorded:
                raise ValueError("duplicate functional outcome")
            row = copy.deepcopy(row)
            stage = row.get("first_attempt")
            if stage and row["case"]["kind"] == "grasp":
                # Keep the original v1 label in a separate summary field. Use
                # the saved sustained-hold label checking all current supports.
                stage["legacy_private_grasp_truth"] = stage.get("private_true_sustained_grasp")
                stage["private_true_sustained_grasp"] = stage.get("private_hold_truth_v2", {}).get("success")
            recorded[name] = row
    groups, registered_groups = defaultdict(list), defaultdict(list)
    for case in planned.values():
        registered_groups[(case["type"], case["condition"])].append(case)
    for row in recorded.values():
        groups[(row["case"]["type"], row["case"]["condition"])].append(row)
    by_group = {}
    for group, cases in registered_groups.items():
        rows = groups[group]
        report = metrics(rows, len(cases), cases)
        report["registered_success_lower_bound_wilson_95CI"] = wilson(
            report["true_successes"], len(cases))
        causes = Counter()
        for row in rows:
            stage = row.get("first_attempt")
            receipt = stage.get("receipt", {}) if stage else {}
            if stage is None:
                causes[row.get("binding_error") or row["status"]] += 1
            elif receipt.get("failure_reason"):
                causes[receipt["failure_reason"]] += 1
            elif (stage.get("private_true_sustained_grasp") if row["case"]["kind"] == "grasp"
                  else stage.get("private_after", {}).get("satisfied")) is False:
                causes["contact_or_endpoint_not_satisfied"] += 1
        report["failure_root_counts"] = dict(causes)
        report["actual_sim_steps"] = sum((row.get("first_attempt") or {}).get("receipt", {}).get(
            "sim_steps_used", 0) for row in rows)
        by_group["/".join(group)] = report
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    summaries = []
    for name, row in recorded.items():
        stage = row.get("first_attempt") or {}
        receipt = stage.get("receipt", {})
        summaries.append({"name": name, "category": row["case"]["type"],
                          "method": row["case"]["condition"], "status": row["status"],
                          "private_truth": (stage.get("private_true_sustained_grasp")
                              if row["case"]["kind"] == "grasp" else
                              stage.get("private_after", {}).get("satisfied")),
                          "public_verification": receipt.get("verification"),
                          "failure_reason": receipt.get("failure_reason"),
                          "sim_steps": receipt.get("sim_steps_used"),
                          "output_dir": row["output_dir"]})
    ledger = output / "attempts.jsonl"
    ledger.write_text("".join(json.dumps(row) + "\n" for row in summaries))
    report = {"planned": len(planned), "recorded": len(recorded),
              "pending": len(planned) - len(recorded), "groups": by_group,
              "infrastructure_attempts": infrastructure, "references": references,
              "summary_ledger": ref(ledger), "summary_source": ref(Path(__file__)),
              "grasp_truth_source": "saved all-current-supports/2 sustained-hold labels; legacy truth retained",
              "other_truth_source": "post-execution original private predicate or joint measurement",
              "scope": "selection, not confirmation; Wilson intervals are nominal per condition",
              "behavior_frozen": False, "training_allowed": False}
    manifest = output / "manifest.json"
    manifest.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"manifest": ref(manifest), "planned": report["planned"],
                      "recorded": report["recorded"], "pending": report["pending"],
                      "groups": {key: {k: value[k] for k in (
                          "recorded", "true_successes", "known_truth", "wilson_95CI",
                          "registered_success_lower_bound_wilson_95CI",
                          "agreement_over_known_private_truth", "confusion", "failure_root_counts")}
                          for key, value in by_group.items()}}))


if __name__ == "__main__":
    main()
