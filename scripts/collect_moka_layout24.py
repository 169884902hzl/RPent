"""Summarize the explicitly registered, retained 24-layout transfer trials."""

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path


def reference(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    p, den = k / n, 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [center - half, center + half]


def collect(registry_path, output):
    registry = json.loads(registry_path.read_text())
    plan_path = Path(registry["plan"]["path"])
    if reference(plan_path) != registry["plan"]:
        raise ValueError("registered plan changed")
    plan = json.loads(plan_path.read_text())
    registered = {case["name"]: case for case in plan["cases"]}
    if len(registered) != 24:
        raise ValueError("only the 24 approved layouts may be summarized")
    rows, inputs, pending, infrastructure_attempts = [], [], [], []
    for entry in registry["ledgers"]:
        path = Path(entry["path"])
        if not path.is_absolute():
            raise ValueError("explicit absolute ledger path required")
        if not path.is_file():
            pending.append(entry)
            continue
        raw = path.read_bytes()
        ledger_reference = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
        inputs.append(ledger_reference)
        for line in raw.decode().splitlines():
            row = json.loads(line)
            case = row["case"]
            if case["name"] not in registered:
                raise ValueError("unregistered trial")
            expected = registered[case["name"]]
            if (case["state_sha256"] != expected["state_sha256"]
                    or case["geometry_fingerprint"] != expected["geometry_fingerprint"]):
                raise ValueError("trial state differs from registered layout")
            truth = row.get("official_subtask_success")
            public = row.get("public_placement_verdict")
            final = (row.get("private_original_task_status_after") or {}).get("done")
            if truth is not None and type(truth) is not bool:
                raise ValueError("private final transfer label must be boolean or unknown")
            if final is not None and (type(final) is not bool or truth is not final):
                raise ValueError("inconsistent private final transfer label")
            if public is not None and type(public) is not bool:
                raise ValueError("public verdict must be boolean or unknown")
            scope = row.get("server_chunk_execution") or {}
            controls = int(scope.get("executed_controls", 0))
            receipt = row.get("first_receipt") or {}
            if row.get("case_had_infrastructure_failure"):
                infrastructure_attempts.append({"case_name": case["name"],
                                                "job_id": entry["job_id"],
                                                "ledger": ledger_reference,
                                                "attempt_index": row.get("attempt_index"),
                                                "error": row.get("error"),
                                                "contact_controls": controls})
                continue
            if controls:
                if controls != scope.get("requested_controls"):
                    raise ValueError("trial lacks complete physical execution accounting")
                outcome = "transfer_success" if truth is True else (
                    "transfer_failed" if truth is False else "transfer_label_unknown")
            elif (receipt.get("executed") is False
                  and row.get("executed_vla_actions", 0) == 0
                  and row.get("executed_public_motion_actions", 0) == 0):
                # A completed perception/binding failure is a retained attempt,
                # not a startup error or an invented negative private label.
                outcome = "no_execution"
            else:
                raise ValueError("trial lacks physical execution or a recorded no-execution receipt")
            rows.append({"case_name": case["name"], "state_sha256": case["state_sha256"],
                         "geometry_fingerprint": case["geometry_fingerprint"],
                         "job_id": entry["job_id"], "ledger": ledger_reference,
                         "simulation_final_transfer": truth, "public_place_verified": public,
                         "official_native_success": row.get("result", {}).get("official_success"),
                         "outcome": outcome, "failure_reason": receipt.get("failure_reason"),
                         "chunks": row["chunks"], "contact_controls": controls,
                         "wall_s": row["wall_s"],
                         "ever_success_then_final_false": bool(scope.get("raw_native_success_controls", 0)) and truth is False})
    rows.sort(key=lambda row: row["case_name"])
    if len({row["case_name"] for row in rows}) != len(rows):
        raise ValueError("completed confirmation trial repeated")
    n = len(rows)
    success = sum(row["simulation_final_transfer"] is True for row in rows)
    truth_known = [row for row in rows if row["simulation_final_transfer"] is not None]
    known = [row for row in truth_known if row["public_place_verified"] is not None]
    agreement = sum(row["simulation_final_transfer"] == row["public_place_verified"] for row in known)
    fp = sum(row["public_place_verified"] is True and row["simulation_final_transfer"] is False for row in rows)
    fn = sum(row["public_place_verified"] is False and row["simulation_final_transfer"] is True for row in rows)
    summary = {"planned": 24, "completed": n, "remaining": 24 - n,
               "transfer_success": success, "transfer_rate": success / n if n else None,
               "transfer_wilson95": wilson(success, n),
               "private_truth_known": len(truth_known), "private_truth_unknown": n - len(truth_known),
               "public_known": sum(row["public_place_verified"] is not None for row in rows),
               "public_unknown": sum(row["public_place_verified"] is None for row in rows),
               "paired_labels_known": len(known),
               "agreement_known": agreement, "agreement_known_wilson95": wilson(agreement, len(known)),
               "agreement_known_rate": agreement / len(known) if known else None,
               "agreement_all_trials": agreement / n if n else None,
               "false_positive": fp, "false_negative": fn,
               "outcomes": dict(Counter(row["outcome"] for row in rows)),
               "failure_reasons": dict(Counter(row["failure_reason"] for row in rows if row["failure_reason"])),
               "official_native_success": sum(row["official_native_success"] is True for row in rows),
               "infrastructure_attempts": len(infrastructure_attempts),
               "ever_success_then_final_false": sum(row["ever_success_then_final_false"] for row in rows),
               "contact_controls": sum(row["contact_controls"] for row in rows),
               "median_wall_s": statistics.median(row["wall_s"] for row in rows) if rows else None}
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema": "approved_moka_layout24_transfer/2", "registry": reference(registry_path),
              "plan": registry["plan"], "inputs": inputs, "pending_ledgers": pending,
              "rows": rows, "summary": summary, "training_allowed": False,
              "infrastructure_attempts": infrastructure_attempts,
              "hundred_state_qualification": False,
              "limitations": ["24 preregistered layouts are reported separately from official initial states.",
                              "No IID claim; 100-state confirmation remains incomplete.",
                              "The diagnostic grasp choice and grasp-verifier placeholders are not transfer outcomes.",
                              "All completed failures, including no execution, are retained in the attempt denominator and not retried.",
                              "Unknown private labels remain null and are excluded from verifier agreement, not converted to false.",
                              "Infrastructure attempts are listed separately from the confirmation denominator."]}
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps({"report": reference(report_path), "registry": reference(registry_path),
                                         "inputs": inputs, "training_allowed": False}, indent=2) + "\n")
    return {"manifest": reference(manifest_path), "summary": summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(collect(args.registry.resolve(strict=True), args.output.resolve())))
