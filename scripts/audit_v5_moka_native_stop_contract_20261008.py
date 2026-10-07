"""Read-only native-stop diagnosis from explicitly indexed completed ledgers."""

import argparse
import hashlib
import json
from pathlib import Path


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--registry-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if identity(args.registry)["sha256"] != args.registry_sha256:
        raise ValueError("Explicit registry changed")
    registry = json.loads(args.registry.read_text())
    if registry["training_allowed"] is not False:
        raise ValueError("Confirmation results must remain excluded from training")
    records, inputs = [], []
    for ref in registry["ledgers"]:
        if ref["job_id"] != "4499_0" and ref["job_id"] != "4528_0" and not ref["job_id"].startswith("4502_"):
            continue
        path = Path(ref["path"])
        if not path.is_absolute():
            raise ValueError("Ledger path must be absolute")
        inputs.append({"job_id": ref["job_id"], **identity(path)})
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            row = json.loads(line)
            server = row.get("server_chunk_execution") or {}
            records.append({"case": row["case"]["name"], "job_id": ref["job_id"],
                "ledger_line": line_no, "raw_state_sha256": row["case"]["state_sha256"],
                "native_success_controls": server.get("raw_native_success_controls"),
                "native_success_stops_chunk": server.get("native_success_stops_chunk"),
                "requested_controls": server.get("requested_controls"),
                "executed_controls": server.get("executed_controls"),
                "final_transfer_truth": row.get("official_subtask_success"),
                "native_goal_truth_before": (row.get("private_original_task_status_before") or {}).get("done"),
                "native_goal_truth_after": (row.get("private_original_task_status_after") or {}).get("done"),
                "chunks": row.get("chunks"), "public_stop_reason": row.get("first_receipt", {}).get("stop"),
                "failure_reason": row.get("first_receipt", {}).get("failure_reason"),
                "private_labels_control_execution": False,
                "scope": "read-only postexecution diagnosis; no source or confirmation outcome changes"})
    if len({r["case"] for r in records}) != len(records):
        raise ValueError("Duplicate confirmation attempts must not be silently combined")
    cohorts = {}
    for name, rows in (("old24", [r for r in records if r["case"] != "moka_layout_580125"]),
                       ("old24_plus_first_new", records)):
        count = lambda predicate: sum(bool(predicate(r)) for r in rows)
        cohorts[name] = {"registered_records": len(rows),
            "final_transfer_true": count(lambda r: r["final_transfer_truth"] is True),
            "final_transfer_false": count(lambda r: r["final_transfer_truth"] is False),
            "final_transfer_unknown": count(lambda r: r["final_transfer_truth"] is None),
            "native_success_seen_and_final_false": count(lambda r: (r["native_success_controls"] or 0) > 0 and r["final_transfer_truth"] is False),
            "final_false_without_native_success_seen": count(lambda r: r["final_transfer_truth"] is False and r["native_success_controls"] == 0),
            "native_success_seen_and_final_true": count(lambda r: (r["native_success_controls"] or 0) > 0 and r["final_transfer_truth"] is True)}
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output / "records.json"
    output.write_text(json.dumps(records, indent=2) + "\n")
    report = {"schema": "moka-native-stop-readonly-diagnosis/1", "registry": identity(args.registry),
        "inputs": inputs, "records": identity(output), "cohorts": cohorts,
        "truth_source": "saved execution server raw-native-success counters and final private transfer label",
        "native_stop_contract": "owned diagnostic executes complete five-action chunks; complete_skill masks native latch at client",
        "runtime_difference": "benchmark native success may terminate; this owned single-skill diagnostic continues until public endpoint or fixed block budget",
        "necessity_for_same_goal_transfer": "full chunk accounting is diagnostic convention; reverse-goal isolation is not required for task19 full transfer",
        "stepwise_native_prefix_available": False,
        "diagnostic_does_not_prove_native_stop_would_improve_success": True,
        "confirmation_rerun": False, "runtime_changed": False,
        "threshold_changed": False, "training_allowed": False,
        "producer": identity(Path(__file__))}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"cohorts": cohorts, "manifest": identity(args.output / "manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
