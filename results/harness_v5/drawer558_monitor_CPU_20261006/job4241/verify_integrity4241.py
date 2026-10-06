"""Verify only explicit report, manifest, source and public measurement references."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    directory = args.root / "results/harness_v5/drawer558_monitor_CPU_20261006/job4241"
    report = json.loads((directory / "report.json").read_text())
    manifest_ref = report["manifests"][0]
    plan = json.loads(Path(manifest_ref["path"]).read_text())
    refs = json.loads((directory / "public_measurement_refs.json").read_text())["refs"]
    checked = []
    explicit = [("manifest", manifest_ref)]
    explicit += [("source", ref) for ref in plan["source_snapshot"]["files"]]
    explicit += [("source_archive", plan["source_snapshot"]["archive"])]
    explicit += [("captured_raw", ref) for ref in report["ledgers"] + report["infrastructure_ledgers"]]
    explicit += [("original_raw", {"path": ref["path"], "sha256": ref["captured_sha256"]})
                 for ref in report["original_explicit_inputs"]]
    explicit += [("public_geometry", ref) for ref in refs]
    for role, ref in explicit:
        path = Path(ref["path"])
        actual = sha(path)
        checked.append({"role": role, "path": str(path), "expected_sha256": ref["sha256"],
                        "actual_sha256": actual, "sha_match": actual == ref["sha256"],
                        "size_bytes": path.stat().st_size})
    assert all(ref["sha_match"] for ref in checked)
    value = {"job_id": 4241, "all_sha_match": True, "public_ref_count": len(refs),
             "unique_public_paths": len({ref["path"] for ref in refs}),
             "refs_sha256": sha(directory / "public_measurement_refs.json"), "checked": checked,
             "selection_only": True, "qualification_authorized": False}
    (directory / "public_and_source_integrity.json").write_text(json.dumps(value, indent=2) + "\n")
    env = os.environ.copy()
    env["TZ"] = "UTC"
    slurm = subprocess.run(["sacct", "-j", "4241", "--format=JobID,State,ExitCode,Start,End,Elapsed,NodeList",
                            "--parsable2", "-X", "-n"], env=env, check=True, capture_output=True, text=True).stdout
    (directory / "slurm_completed_UTC.tsv").write_text(slurm)
    print(json.dumps({"checked": len(checked), "public_refs": len(refs),
                      "integrity_sha256": sha(directory / "public_and_source_integrity.json")}))


if __name__ == "__main__":
    main()
