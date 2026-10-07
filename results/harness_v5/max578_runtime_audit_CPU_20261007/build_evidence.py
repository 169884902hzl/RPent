"""Snapshot the explicit reviewed source list; never enumerate artifacts."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone

PACKET = Path(__file__).resolve().parent
REPO = PACKET.parents[2]
MAX_ROOT = REPO / "external_readonly/libero_max_audit_20261007"
LOCAL_FILES = [
    "robots/libero/tools.py", "robots/libero/env_server.py",
    "robots/libero/env_client.py", "robots/libero/v5_runtime.py",
    "robots/libero/v5_env_server.py", "robots/libero/v5_env_client.py",
]
MAX_FILES = [
    "docs/RUNTIME_INTEGRATION.md", "docs/BENCHMARK_SPEC.md", "pyproject.toml",
    "scripts/run_xvla_persistent_shard.py", "scripts/run_xvla_persistent_benchmark.py",
    "src/libero_max/cosmos_integration.py", "src/libero_max/libero_backend.py",
    "src/libero_max/runtime.py", "src/libero_max/pro_runtime.py",
    "src/libero_max/env_factory.py",
]
INSTALLED = {
    "libero_env.py": ("rlinf/envs/libero/libero_env.py", "ecc3343cdd6336704af3596028939147cc1269fe38a9c55ae5e3b5b2efd7d8d2"),
    "venv.py": ("rlinf/envs/libero/venv.py", "4b27212446df9ebb5e90878b7d348b0cb6df4835c086931b7e3ef1b40f640b24"),
    "camera_utils.py": ("robosuite/utils/camera_utils.py", "320d1fccc23ea09334d747093c12ec014fdad072b71308026cf1dfe48db98afb"),
}


def digest(path):
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def main():
    refs = []
    for kind, root, names in (("rpent_runtime", REPO, LOCAL_FILES), ("libero_max", MAX_ROOT, MAX_FILES)):
        for name in names:
            source = root / name
            copy = PACKET / "evidence" / kind / name
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, copy)
            refs.append({"source": str(source), "snapshot": str(copy.relative_to(PACKET)), "kind": kind, **digest(copy)})
    for filename, (relative, expected) in INSTALLED.items():
        copy = PACKET / "evidence/installed5880" / filename
        row = digest(copy)
        if row["sha256"] != expected:
            raise ValueError(f"Installed source hash changed: {relative}")
        refs.append({"source": "/public/home/sunyihan/rpent_libero_eval/.venv/lib/python3.10/site-packages/" + relative,
                     "snapshot": str(copy.relative_to(PACKET)), "kind": "installed5880", **row})
    report = {
        "schema": "max578-source-evidence/1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "upstream_repository": "https://github.com/liberomax/LIBERO-MAX",
        "upstream_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=MAX_ROOT, text=True).strip(),
        "runtime_relevant_commit": subprocess.check_output(["git", "log", "-1", "--format=%H", "--", *LOCAL_FILES], cwd=REPO, text=True).strip(),
        "cpu_only": True, "gpu_jobs_submitted": [], "case_manifests_opened": False,
        "pro_task_payloads_opened": False, "shared_runtime_modified": False,
        "evidence": refs,
    }
    (PACKET / "source_evidence.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    outputs = ["README.md", "build_evidence.py", "source_evidence.json"]
    manifest = {"schema": "max578-audit-manifest/1", "status": "CPU_READ_ONLY_AUDIT_COMPLETE",
                "outputs": [{"path": name, **digest(PACKET / name)} for name in outputs],
                "source_files": len(refs), "no_simulation_run": True,
                "blocking_contracts": ["canonical_transformed_observation", "explicit_calibration_configuration", "exact_control_prefix"]}
    (PACKET / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"manifest": str(PACKET / "manifest.json"), **digest(PACKET / "manifest.json"), "source_files": len(refs)}))


if __name__ == "__main__":
    main()
