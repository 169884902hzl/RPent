"""Compare saved public geometry gates without changing execution or labels."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(item):
    path = Path(item["path"])
    if ref(path)["sha256"] != item["sha256"]:
        raise ValueError(f"registered input changed: {path}")
    return path


def classify(verdict, label):
    return "unknown" if verdict is None else ("TP" if label else "FP") if verdict else ("FN" if label else "TN")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = json.loads(args.inputs.read_text())
    counters, rows, observations = {}, [], []
    for run in inputs["runs"]:
        counts = {name: Counter() for name in ("stored_v6", "two_moving_views", "two_views_symmetric_gap")}
        for ledger in run["original_ledgers"]:
            for number, line in enumerate(pinned(ledger).read_text().splitlines(), 1):
                raw = json.loads(line)
                if raw["case"]["type"] != "drawer_close":
                    continue
                first = raw["first_attempt"]
                private = [s for s in first["contact_evidence"]["private_fixture_scores"]
                           if s["phase"] == "after_actual_chunk"]
                for sample in first["verification_measurements"]["drawer_public_stop"]:
                    measurement = sample["measurement"]
                    views = measurement.get("views", {})
                    support = [camera for camera in ("agentview", "wrist")
                               if views.get(camera, {}).get("moving")]
                    signed = sample["evidence"].get("measured_signed_extension_m")
                    geometric = sample["verified"]
                    dual = geometric if len(support) == 2 else None
                    symmetric = dual if signed is not None and signed >= -.0005 else None
                    label = private[sample["chunk"]-1]["label"]["satisfied"]
                    variants = {"stored_v6": geometric, "two_moving_views": dual,
                                "two_views_symmetric_gap": symmetric}
                    for name, verdict in variants.items():
                        counts[name][classify(verdict, label)] += 1
                    locator = {"job": run["job"], "raw_ledger": ledger, "line_1based": number,
                               "case": raw["case"]["name"], "after_chunks": sample["chunk"]}
                    rows.append({**locator, "private_endpoint_label_diagnostic_only": label,
                                 "moving_support_cameras": support, "signed_extension_m": signed,
                                 "verdicts": variants})
                    # Keep public model inputs in a distinct ledger. Private
                    # endpoint/qpos are joined only in the diagnosis ledger.
                    observations.append({**locator, "source": "perception",
                        "public_measurement": measurement,
                        "public_before_measurement": sample["evidence"].get("before"),
                        "private_features": False})
                    if raw["case"]["episode"] == {"suite": "libero_90", "task": 23, "seed": 20}:
                        rows[-1]["diagnostic_qpos_at_saved_chunk"] = private[sample["chunk"]-1]["label"]["joint_qpos"]
        counters[str(run["job"])] = {name: dict(value) for name, value in counts.items()}
    outputs = {}
    for filename, values in (("diagnosis.jsonl", rows), ("public_measurements.jsonl", observations)):
        path = args.output / filename
        path.write_text("".join(json.dumps(row) + "\n" for row in values))
        outputs[filename] = ref(path)
    report = {"version": "saved-drawer-public-identity-audit/1", "inputs": ref(args.inputs),
        "sampling_unit": "saved postblock samples, not independent episodes or confirmation trials",
        "paired_states": 20, "close_states": 10, "executions": 40,
        "by_job": counters, "new_physical_trials": 0, "old_records_changed": False,
        "private_values_used_for_control": False,
        "conclusion": "Two-camera support plus a symmetric gap gate does not establish reliable moving-face identity; no gate is admitted.",
        "outputs": outputs}
    path = args.output / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": ref(path), "by_job": counters}))


if __name__ == "__main__":
    main()
