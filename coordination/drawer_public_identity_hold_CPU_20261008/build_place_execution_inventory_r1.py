"""Freeze the explicit placement evidence inventory without modifying results."""

import hashlib
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent
REMOTE_CPU = "/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008"


def artifact(local: str, remote: str, expected_sha: str) -> dict:
    path = BASE / local
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha:
        raise ValueError(f"placement evidence changed: {path}")
    return {"local_copy": str(path), "path": remote, "sha256": actual}


def main() -> None:
    audit = json.loads((BASE / "runtime_identity_package_r1/actual_job4555_execution_audit.json").read_text())
    seven = json.loads((BASE / "place_trace_package_r2/complete_controls_accounted_v2.json").read_text())
    roots = json.loads((BASE / "place_trace_package_r2/public_verifier_root_causes_v1.json").read_text())
    artifacts = [
        artifact("runtime_identity_package_r1/actual_job4555_execution_audit.json", REMOTE_CPU + "/preparation_runtime_identity_r1/actual_job4555_execution_audit.json", "d03f41865f042607aa6832b2923e99e1f79982aedb78587850de35ca6fa2e6ac"),
        artifact("place_trace_package_r2/complete_controls_accounted_v2.json", REMOTE_CPU + "/preparation_r2/remaining7_launcher_preflight/complete_controls_accounted_v2.json", "b473c612a82738473066d67add910106068a61c18b00aa242a4026dc8c0c0ca6"),
        artifact("place_trace_package_r2/public_verifier_root_causes_v1.json", REMOTE_CPU + "/preparation_r2/remaining7_launcher_preflight/public_verifier_root_causes_v1.json", "730961c10f4cefec7d715ef32fe8cc24ddfa37628b8694b058e069ce0eb84f18"),
        artifact("place_trace_package_r2/monitor_completed7.json", REMOTE_CPU + "/preparation_r2/remaining7_launcher_preflight/monitor_completed7.json", "9fa45a20899990a51b8d418f5f56e73735b2e54abb9d8a76a2ad45e8e1713a63"),
        artifact("runtime_identity_package_r1/saved_public_runtime_reproduction.json", REMOTE_CPU + "/preparation_runtime_identity_r1/saved_public_runtime_reproduction.json", "91ddb0c0035145f519976a800ff3cfed624806cbd6ed6db300df060702682064"),
        artifact("runtime_identity_package_r1/same_launcher_CPU_preflight.json", REMOTE_CPU + "/preparation_runtime_identity_r1/same_launcher_CPU_preflight.json", "3c6d2814ea49f857c80d1bb2af8b1be99ed6c1ec61ec18c485d875e682e82f44"),
    ]
    handoff = BASE / "PLACE_EXECUTION_RESULTS_r1_20261008.md"
    result = {
        "schema": "place-public-execution-explicit-artifacts/1-dev",
        "handoff": {"path": str(handoff), "sha256": hashlib.sha256(handoff.read_bytes()).hexdigest()},
        "artifacts": artifacts,
        "runtime4555": {key: audit[key] for key in ("job_id", "output_dir", "episodes", "submission", "manifest", "source_commit", "source_files_sha_checked", "target_selected", "target_environment_controls", "target_public_place_verified", "private_before_satisfied", "private_after_satisfied", "case_wall_s", "runtime_path_only_public_frames", "pre_action_visible_cabinet_ids", "pre_action_visible_measured_top_ids")},
        "remaining7_source_commit": seven["source_commit"],
        "remaining7_episodes": [case["episodes"] for case in seven["cases"]],
        "remaining7_summary": roots["summary"],
        "runtime_scene_switch_global_default": False,
        "public_thresholds_changed": False,
        "old_results_changed": False,
        "qualification_authorized": False,
        "new_gpu_submissions_by_subagent": 0,
        "new_training_rows": 0,
        "analyzer": {"path": str(Path(__file__).resolve()), "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
    }
    output = BASE / "PLACE_EXECUTION_ARTIFACTS_r1_20261008.json"
    encoded = json.dumps(result, indent=2) + "\n"
    if output.exists() and output.read_text() != encoded:
        raise ValueError("immutable placement inventory already exists with different content")
    output.write_text(encoded)
    print(json.dumps({"path": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "reports": len(artifacts), "episodes": len(seven["cases"]) + 1}))


if __name__ == "__main__":
    main()
