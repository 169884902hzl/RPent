"""Record case names without changing the original Slurm submission receipt."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original_sha = sha256(args.submission)
    submission = json.loads(args.submission.read_text())
    preflight = json.loads(args.preflight.read_text())
    jobs = []
    for registered in submission["jobs"]:
        env = registered["submission_env"]
        manifest_path = Path(env["PLACE_TRACE_MANIFEST"])
        manifest_sha = sha256(manifest_path)
        if manifest_sha != env["PLACE_TRACE_MANIFEST_SHA"]:
            raise ValueError(f"registered manifest changed: {manifest_path}")
        manifest = json.loads(manifest_path.read_text())
        if len(manifest["cases"]) != 1:
            raise ValueError(f"expected one registered case: {manifest_path}")
        case = manifest["cases"][0]
        case_number = int(manifest_path.name.split("_", 1)[0].removeprefix("case"))
        job = str(registered["job_id"])
        jobs.append(
            {
                "case_number": case_number,
                "case_name": case["name"],
                "episode": case["episode"],
                "condition": case["condition"],
                "state_sha256": case["state_sha256"],
                "job_id": job,
                "manifest": {"path": str(manifest_path), "sha256": manifest_sha},
                "submission_env": env,
                "output_dir": f"{env['PLACE_TRACE_BASE']}/job{job}",
                "episodes_file": f"{env['PLACE_TRACE_BASE']}/job{job}/episodes.jsonl",
                "training_allowed": False,
                "qualification_authorized": False,
            }
        )
    if sorted(row["case_number"] for row in jobs) != list(range(1, 8)):
        raise ValueError("submission must contain exactly cases 1 through 7")
    result = {
        "schema": "place-trace-remaining7-submission-mapping/2",
        "original_submission": {"path": str(args.submission), "sha256": original_sha},
        "preflight": {"path": str(args.preflight), "sha256": sha256(args.preflight)},
        "source_commit": "0eff8550d2c9cb73f778423d5945c1562c62898d",
        "case_source": "SHA-checked one-case manifests, not missing submission case field",
        "original_submission_changed": False,
        "new_gpu_submissions": 0,
        "preflight_schema": preflight.get("schema", preflight.get("version")),
        "jobs": jobs,
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output.exists() and args.output.read_text() != encoded:
        raise ValueError(f"immutable mapping already differs: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded)
    if sha256(args.submission) != original_sha:
        raise ValueError("original submission changed during mapping")
    print(json.dumps({"output": str(args.output), "sha256": sha256(args.output), "jobs": len(jobs)}))


if __name__ == "__main__":
    main()
