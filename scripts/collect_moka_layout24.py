"""Summarize the explicitly registered, retained 24-layout transfer trials."""

import argparse
import hashlib
import json
import math
import statistics
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
    rows, inputs, pending = [], [], []
    for entry in registry["ledgers"]:
        path = Path(entry["path"])
        if not path.is_absolute():
            raise ValueError("explicit absolute ledger path required")
        if not path.is_file():
            pending.append(entry)
            continue
        raw = path.read_bytes()
        inputs.append(reference(path))
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
            final = row.get("private_original_task_status_after", {}).get("done")
            if type(truth) is not bool or truth is not final:
                raise ValueError("missing or inconsistent private final transfer label")
            if public is not None and type(public) is not bool:
                raise ValueError("public verdict must be boolean or unknown")
            scope = row.get("server_chunk_execution") or {}
            controls = int(scope.get("executed_controls", 0))
            if controls <= 0 or controls != scope.get("requested_controls"):
                raise ValueError("trial lacks complete physical execution accounting")
            if row.get("case_had_infrastructure_failure"):
                raise ValueError("infrastructure attempt must be reported separately")
            rows.append({"case_name": case["name"], "state_sha256": case["state_sha256"],
                         "geometry_fingerprint": case["geometry_fingerprint"],
                         "job_id": entry["job_id"], "ledger": reference(path),
                         "simulation_final_transfer": truth, "public_place_verified": public,
                         "chunks": row["chunks"], "contact_controls": controls,
                         "wall_s": row["wall_s"],
                         "ever_success_then_final_false": bool(scope.get("raw_native_success_controls", 0)) and not truth})
    rows.sort(key=lambda row: row["case_name"])
    if len({row["case_name"] for row in rows}) != len(rows):
        raise ValueError("completed confirmation trial repeated")
    n = len(rows)
    success = sum(row["simulation_final_transfer"] for row in rows)
    known = [row for row in rows if row["public_place_verified"] is not None]
    agreement = sum(row["simulation_final_transfer"] == row["public_place_verified"] for row in known)
    fp = sum(row["public_place_verified"] is True and not row["simulation_final_transfer"] for row in rows)
    fn = sum(row["public_place_verified"] is False and row["simulation_final_transfer"] for row in rows)
    summary = {"planned": 24, "completed": n, "remaining": 24 - n,
               "transfer_success": success, "transfer_rate": success / n if n else None,
               "transfer_wilson95": wilson(success, n),
               "public_known": len(known), "public_unknown": n - len(known),
               "agreement_known": agreement, "agreement_known_wilson95": wilson(agreement, len(known)),
               "agreement_all_trials": agreement / n if n else None,
               "false_positive": fp, "false_negative": fn,
               "ever_success_then_final_false": sum(row["ever_success_then_final_false"] for row in rows),
               "contact_controls": sum(row["contact_controls"] for row in rows),
               "median_wall_s": statistics.median(row["wall_s"] for row in rows) if rows else None}
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema": "approved_moka_layout24_transfer/1", "registry": reference(registry_path),
              "plan": registry["plan"], "inputs": inputs, "pending_ledgers": pending,
              "rows": rows, "summary": summary, "training_allowed": False,
              "hundred_state_qualification": False,
              "limitations": ["24 preregistered layouts are reported separately from official initial states.",
                              "No IID claim; 100-state confirmation remains incomplete.",
                              "The diagnostic grasp choice and grasp-verifier placeholders are not transfer outcomes.",
                              "All completed physical failures are retained and not retried."]}
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
