"""Preserve physical coverage and endpoint-specific historical moka failures."""

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("monitor", ROOT / "scripts/summarize_v5_grasp543_20261006.py")
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)
spec = importlib.util.spec_from_file_location("history", OUT / "historical_producer.py")
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)
cmd = json.loads((OUT / "command.json").read_text())
records = []
for index, arg in enumerate(cmd):
    if arg not in ("--grasp-ledger", "--subtask-ledger"):
        continue
    ledger = Path(cmd[index + 1])
    for number, line in enumerate(ledger.read_text().splitlines(), 1):
        row = json.loads(line)
        case = row["case"]
        if "moka" not in case["name"]:
            continue
        short = arg == "--grasp-ledger"
        receipt = (row.get("first_receipt") or {}) if short else row["first_attempt"]["receipt"]
        physical = monitor.physically_executed(dict(row, first_receipt=receipt))
        phase = row.get("private_grasp_phase", {})
        truth = row.get("true_sustained_grasp") if short else phase.get("true_sustained_grasp_during_skill")
        if not physical:
            failure = "not_physically_executed"
        elif short:
            failure = history.hold_failure(row)
        elif truth is True:
            failure = "sustained_during_skill_success"
        elif truth is None:
            failure = "unknown_sustained_during_skill"
        else:
            samples = phase.get("samples", [])
            if not samples:
                failure = "missing_recorded_control_contact_samples"
            elif not any(s["finger_contact"] for s in samples):
                failure = "no_target_finger_contact"
            elif max(s["lower_extent_m"] - phase["reference"]["lower_extent_m"] for s in samples) < .03:
                failure = "target_contact_without_3cm_lower_extent_lift"
            else:
                failure = "lift_without_registered_sustained_during_hold"
        records.append({"case": case["name"], "condition": case["condition"], "physical": physical,
                        "saved_metric_truth": truth, "metric_truth_for_first_physical": truth if physical else None,
                        "metric_scope": "posttrial_hold" if short else "sustained_during_skill",
                        "diagnostic_failure_type": failure, "receipt_executed": receipt.get("executed"),
                        "runtime_failure_reason": receipt.get("failure_reason"),
                        "infra": monitor.infrastructure_failure(dict(row, first_receipt=receipt)),
                        "ledger": str(ledger), "line": number})
assert len(records) == len({r["case"] for r in records}) == 500
groups = []
for condition in sorted({r["condition"] for r in records}):
    rows = [r for r in records if r["condition"] == condition]
    physical = [r for r in rows if r["physical"]]
    groups.append({"condition": condition, "registered": len(rows), "first_physical": len(physical),
                   "no_physics": len(rows) - len(physical),
                   "physical_success": sum(r["metric_truth_for_first_physical"] is True for r in physical),
                   "physical_failure": sum(r["metric_truth_for_first_physical"] is False for r in physical),
                   "unknown_after_physics": sum(r["metric_truth_for_first_physical"] is None for r in physical),
                   "endpoint_specific_diagnostic_types": dict(Counter(r["diagnostic_failure_type"] for r in rows)),
                   "zero_physics_saved_labels": dict(Counter(str(r["saved_metric_truth"]) for r in rows if not r["physical"])),
                   "no_physics_reasons": dict(Counter(str(r["runtime_failure_reason"]) for r in rows if not r["physical"])),
                   "infrastructure_cases": sum(r["infra"] for r in rows)})
report = {"scope": "Historical five methods physical coverage and endpoint-specific diagnostic phenotypes",
          "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          "monitor_physical_rule_sha256": hashlib.sha256((ROOT / "scripts/summarize_v5_grasp543_20261006.py").read_bytes()).hexdigest(),
          "groups": groups, "records": records, "selection_only": True, "qualification_authorized": False,
          "original_labels_preserved": True, "new_physics": 0, "new_model_calls": 0}
(OUT / "physical_coverage.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(groups, indent=2))
