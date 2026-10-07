"""Outcome-blind MAX metadata selection after an immutable preregistration."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import subprocess

PACKET = Path(__file__).resolve().parent
REPO = PACKET.parents[2]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    prereg_path = PACKET / "sampling_preregistration.json"
    prereg_raw = prereg_path.read_bytes()
    prereg = json.loads(prereg_raw)
    source = REPO / prereg["source_file"]
    upstream = REPO / "external_readonly/libero_max_audit_20261007"
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=upstream, text=True).strip()
    if actual != prereg["source_commit"]:
        raise ValueError("Preregistered upstream source changed")
    original_raw = source.read_bytes()
    original = json.loads(original_raw)
    cases = original["cases"]
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate public case IDs")
    selected = []
    for event in prereg["events"]:
        eligible = [c for c in cases if c["scenario"]["change_type"] == event]
        rank = lambda c: (sha(f"{prereg['registered_seed']}|{c['case_id']}".encode()), c["case_id"])
        if len(eligible) < prereg["pairs_per_event"]:
            raise ValueError(f"Insufficient metadata cases for {event}")
        selected.extend(sorted(eligible, key=rank)[:prereg["pairs_per_event"]])
    output = PACKET / "isolated_eval"
    output.mkdir(exist_ok=True)
    payload = {**original, "benchmark_id": "libero-max-lite-development160-seed20261007",
               "protocol": {**original["protocol"], "profile": "development160_from_lite800",
                            "selection_contract": "20 cases per event, outcome-blind SHA256(20261007|case_id) rank; calibration configurations run separately"},
               "cases": selected}
    files = []
    for name, rows in [("sample160.json", selected),
                       ("sample160_plus.json", [c for c in selected if c.get('substrate_variant', {}).get('benchmark') != 'LIBERO-PRO']),
                       ("sample160_pro.json", [c for c in selected if c.get('substrate_variant', {}).get('benchmark') == 'LIBERO-PRO'])]:
        path = output / name
        raw = (json.dumps({**payload, "cases": rows}, indent=2, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        files.append({"path": str(path.relative_to(PACKET)), "sha256": sha(raw), "pairs": len(rows)})
    metadata = [{"case_id": c["case_id"], "change_type": c["scenario"]["change_type"],
                 "task_suite_name": c["task_suite_name"], "task_index": c["task_index"],
                 "init_state_index": c["init_state_index"], "policy_seed": c["policy_seed"],
                 "source": "pro" if c.get("substrate_variant", {}).get("benchmark") == "LIBERO-PRO" else "plus"}
                for c in selected]
    metadata_path = output / "selected_metadata_only.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    report = {"schema": "max579-selection-report/1", "preregistration_sha256": sha(prereg_raw),
              "source_manifest_sha256": sha(original_raw), "source_commit": actual,
              "population_pairs": len(cases), "selected_pairs": len(selected),
              "event_counts": dict(Counter(c["scenario"]["change_type"] for c in selected)),
              "source_counts": dict(Counter(c["source"] for c in metadata)),
              "suite_counts": dict(Counter(c["task_suite_name"] for c in selected)),
              "files": files, "selection_reads_only": ["case_id", "scenario.change_type"],
              "outcome_files_opened": False, "no_score_condition": True,
              "use": "isolated_evaluation_only_not_training_or_manual_or_memory"}
    (PACKET / "selection_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("selected_pairs", "event_counts", "source_counts", "source_manifest_sha256")}))


if __name__ == "__main__":
    main()
