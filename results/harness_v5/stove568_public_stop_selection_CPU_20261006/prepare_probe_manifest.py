"""Pin observation-only original stages; no invalid visual stop threshold."""

import hashlib
import json
from pathlib import Path


def identity(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    packet = Path(__file__).resolve().parent
    root = Path("/public/home/sunyihan/rpent_libero_eval")
    parent_path = root / "results/harness_v5/stove564_off_physical_development_CPU_20261006/off20_probe_manifest.json"
    parent = json.loads(parent_path.read_text())
    if identity(parent_path)["sha256"] != "a82da4b18a83db73b9cb26458ba9aceed8b5729f1092d3467baf6d0f496184e2":
        raise ValueError("parent literal selection identity changed")
    calibration = packet / "red_selection/public_stop_calibration.json"
    report = packet / "red_selection/red_fraction_report.json"
    plan = {"version": "original-stove-public-red-recovery/1-dev", "owned_packet_root": str(packet),
        "source_root": parent["source_root"], "parent_manifest": identity(parent_path),
        "cases": [c["original_case"] for c in parent["cells"] if c["method"] == "literal_off"],
        "public_stop_calibration": identity(calibration), "selection_report": identity(report),
        "fixed_on_chunks": 160, "fixed_off_chunks": 160, "off_prompt": "turn off the stove",
        "public_stop_enabled": False, "public_stop_reason": "red_fraction cannot distinguish true_off from neither; observer only",
        "shards": 5, "array": "0-4%8", "node_binding": None,
        "owned_files": [identity(packet / name) for name in ("public_red_observer.py", "probe_public_red_recovery.py",
            "run_public_red_recovery.sbatch", "test_public_stop_probe.py", "prepare_probe_manifest.py")],
        "planned_contact_skills": 10, "planned_contact_chunks": 1600, "planned_contact_controls": 8000,
        "planned_private_chunk_rows": 1610, "planned_public_off_chunk_observations": 800,
        "capture_stages": ["before_setup", "after_setup", "before_off", "after_contact", "after_release", "after_retreat"],
        "truth_after_execution_only": True, "failed_on_retained": True, "new_training_rows": 0,
        "scope": "Five original selection states, no confirmation; observer is not a verified finish endpoint",
        "implementation_ready": True, "physical_run_verified": False,
        "planned_output_root": str(root / "results/harness_v5/stove568_public_red_recovery_original_20261006")}
    path = packet / "public_red_recovery_manifest.json"
    path.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps(identity(path)))


if __name__ == "__main__":
    main()
