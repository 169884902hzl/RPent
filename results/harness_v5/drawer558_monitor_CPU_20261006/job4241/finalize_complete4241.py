"""Pin the completed 4241 CPU packet; no source, job or verdict changes."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    rel = Path("results/harness_v5/drawer558_monitor_CPU_20261006/job4241")
    directory = root / rel
    remote = "/public/home/sunyihan/rpent_libero_eval/" + str(rel)
    report = json.loads((directory / "report.json").read_text())
    audit = json.loads((directory / "control_and_endpoint_audit.json").read_text())
    integrity = json.loads((directory / "public_and_source_integrity.json").read_text())
    assert audit["report_sha256"] == sha(directory / "report.json")
    assert integrity["all_sha_match"] and integrity["public_ref_count"] == 18
    slurm = []
    for line in (directory / "slurm_completed_UTC.tsv").read_text().splitlines():
        job, state, exit_code, start, end, elapsed, node = line.split("|")
        assert state == "COMPLETED" and exit_code == "0:0"
        slurm.append(dict(job_id=job, state=state, exit_code=exit_code, start_UTC=start, end_UTC=end,
                          elapsed=elapsed, node=node))
    assert len(slurm) == 5
    evidence = {"job_id": 4241, "slurm": slurm, "last_end_UTC": max(row["end_UTC"] for row in slurm),
                "source": audit["source"], "manifest": audit["manifest"], "totals": audit["totals"],
                "private_before_false": 5, "TP": 4, "FP": 0, "FN": 0, "TN": 0,
                "null_private_false": 1, "known_truth_agreement": {"count": 4, "denominator": 5},
                "private_success_wilson95": report["overall"]["wilson_95CI"],
                "public_measurement_files": {"recorded_refs": 18, "unique_paths": 18, "all_sha_match": True},
                "infrastructure_faults": 0, "native_success_stops_chunk": False, "external_truncation": False,
                "private_truth_control": False, "qualification_authorized": False, "new_physical_trials": 0,
                "new_training_rows": 0, "source_or_manifest_modified": False,
                "source_produced_expanded_diagnostic_staged": False, "raw_ledgers_staged": False}
    write(directory / "complete_evidence.json", evidence)
    names = ["report.json", "by_type_method.tsv", "analyze_complete4241.py", "verify_integrity4241.py",
             "control_and_endpoint_audit.json", "public_measurement_refs.json", "public_and_source_integrity.json",
             "slurm_completed_UTC.tsv", "summary.md", "complete_evidence.json", "finalize_complete4241.py"]
    write(directory / "artifact_manifest.json", {"job_id": 4241,
          "files": [{"path": remote + "/" + name, "sha256": sha(directory / name),
                     "size_bytes": (directory / name).stat().st_size} for name in names],
          "original_manifest": audit["manifest"], "source": audit["source"],
          "raw_refs": report["ledgers"] + report["infrastructure_ledgers"],
          "source_produced_expanded_diagnostic": {"path": remote + "/case_diagnostics.jsonl",
                 "sha256": sha(directory / "case_diagnostics.jsonl"), "staged": False},
          "qualification_authorized": False, "new_training_rows": 0, "new_physical_trials": 0})
    write(directory / "handoff.json", {"status": "complete selection-only CPU audit", "job_id": 4241,
          "output_directory": remote, "physical_directory": "/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer558_binding_selection_CPU_20261006/physical_same5/job4241",
          "manifest": audit["manifest"], "source": audit["source"], "result": "private4/5; public4true,0false,1null; controls4000/4000",
          "artifact_manifest": {"path": remote + "/artifact_manifest.json", "sha256": sha(directory / "artifact_manifest.json")},
          "audit": {"path": remote + "/control_and_endpoint_audit.json", "sha256": sha(directory / "control_and_endpoint_audit.json")},
          "evidence": {"path": remote + "/complete_evidence.json", "sha256": sha(directory / "complete_evidence.json")},
          "limitation": "same5 selection only; init10 physical flip with identical start but first sampled action different; no policy RNG or per-chunk private joints recorded",
          "GPU_submitted_by_this_audit": False, "qualification_authorized": False, "new_training_rows": 0, "new_physical_trials": 0})
    print(json.dumps({name: sha(directory / name) for name in ["complete_evidence.json", "artifact_manifest.json", "handoff.json"]}))


if __name__ == "__main__":
    main()
