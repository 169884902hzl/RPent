"""Write explicit handoff and artifact identity for completed selection4235."""

import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    directory = Path(__file__).resolve().parent
    root = directory.parents[4]
    remote_root = "/public/home/sunyihan/rpent_libero_eval"
    remote_directory = remote_root + "/" + str(directory.relative_to(root))
    report = json.loads((directory / "report.json").read_text())
    audit = json.loads((directory / "paired_control_and_measurement_audit.json").read_text())
    public = json.loads((directory / "public_file_integrity.json").read_text())
    assert audit["report_sha256"] == sha(directory / "report.json")
    assert public["all_sha_match"] and public["recorded_ref_count"] == 90
    assert public["refs_sha256"] == sha(directory / "public_measurement_refs.json")
    manifest_ref = report["manifests"][0]
    manifest_path = root / manifest_ref["path"].removeprefix(remote_root + "/")
    assert sha(manifest_path) == manifest_ref["sha256"]
    plan = json.loads(manifest_path.read_text())
    raw = report["ledgers"] + report["infrastructure_ledgers"]
    for ref in raw:
        path = root / ref["path"].removeprefix(remote_root + "/")
        assert sha(path) == ref["sha256"]
    slurm = []
    for line in (directory / "slurm_completed_UTC.tsv").read_text().splitlines():
        job, state, exit_code, end = line.split("|")
        if "." not in job:
            assert state == "COMPLETED" and exit_code == "0:0"
            slurm.append({"job_id": job, "state": state, "exit_code": exit_code, "end_UTC": end})
    assert len(slurm) == 5
    write_json(directory / "complete_evidence.json", {
        "job_id": 4235, "source": report["source"], "original_manifest": manifest_ref,
        "slurm": slurm, "last_end_UTC": max(item["end_UTC"] for item in slurm),
        "registered_cases": 15, "unique_raw_states": 5,
        "method_results": audit["groups"], "paired_comparisons": audit["paired_comparisons"],
        "public_measurement_files": {"recorded_refs": 90, "unique_paths": public["unique_path_count"],
                                     "all_sha_match": True},
        "VLA_controls_requested": 12000, "VLA_controls_executed": 12000,
        "native_success_stops_chunk": False, "external_truncation": False,
        "private_truth_used_for_control": False,
        "source_or_manifest_modified": False, "qualification_authorized": False,
        "new_physical_trials": 0, "new_training_rows": 0, "raw_ledgers_staged": False})
    names = ["report.json", "case_diagnostics.jsonl", "by_type_method.tsv", "analyze_complete4235.py",
             "paired_control_and_measurement_audit.json", "public_measurement_refs.json",
             "public_file_integrity.json", "slurm_completed_UTC.tsv", "summary.md",
             "complete_evidence.json", "finalize_complete4235.py"]
    files = [{"path": remote_directory + "/" + name, "sha256": sha(directory / name),
              "size_bytes": (directory / name).stat().st_size} for name in names]
    write_json(directory / "artifact_manifest.json", {
        "job_id": 4235, "files": files, "raw_refs": raw,
        "original_manifest": manifest_ref, "source_files": plan["source_snapshot"]["files"],
        "source_commit_full": "d8b1d980603e6e0e8f7e14f9541c01f7686c7673",
        "qualification_authorized": False, "new_training_rows": 0, "new_physical_trials": 0})
    write_json(directory / "handoff.json", {
        "status": "completed original paired selection audit", "job_id": 4235,
        "output_directory": remote_directory,
        "physical_directory": remote_root + "/results/harness_v5/drawer557_paired_selection_CPU_20261006/physical_same5/job4235",
        "source": report["source"], "original_manifest": manifest_ref,
        "artifact_manifest": {"path": remote_directory + "/artifact_manifest.json",
                              "sha256": sha(directory / "artifact_manifest.json")},
        "paired_audit": {"path": remote_directory + "/paired_control_and_measurement_audit.json",
                         "sha256": sha(directory / "paired_control_and_measurement_audit.json")},
        "evidence": {"path": remote_directory + "/complete_evidence.json",
                     "sha256": sha(directory / "complete_evidence.json")},
        "result": {"native_original160": "5/5", "stage_original160": "2/5",
                   "stage_reordered160": "0/5", "runtime_verified_true": 0,
                   "runtime_FN": 4, "runtime_null_private_true": 3,
                   "VLA_requested_executed": "12000/12000"},
        "next_problem": "public moving-face endpoint association after opening; selection supports native pose + literal original instruction, but independent confirmation remains required",
        "GPU_submitted_by_this_CPU_audit": False, "source_or_manifest_modified": False,
        "qualification_authorized": False, "new_physical_trials": 0, "new_training_rows": 0})
    print(json.dumps({"directory": str(directory), "handoff_sha256": sha(directory / "handoff.json"),
                      "manifest_sha256": sha(directory / "artifact_manifest.json"),
                      "complete_evidence_sha256": sha(directory / "complete_evidence.json")}))


if __name__ == "__main__":
    main()
