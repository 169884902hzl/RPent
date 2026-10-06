"""Pin owned implementation and explicit original refs, without simulation."""

import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    packet = Path(__file__).resolve().parent
    design_path = packet / "off20_development_plan.json"
    design = json.loads(design_path.read_text())
    original = json.loads(Path(design["original_sampling_manifest"]["path"]).read_text())
    plan = {**design, "version": "original-stove-off-physical-development/2-implemented",
        "design_manifest": ref(design_path), "owned_packet_root": str(packet),
        "diagnostic_server_module": "stove564_probe_env", "shards": 8, "array": "0-7%8",
        "original_task_catalog_file": original["original_task_catalog_file"],
        "capture_views": original["capture_views"], "control_queries": original["control_queries"],
        "sam_min_score": original["sam_min_score"],
        "stove_control_features_v1": original["stove_control_features_v1"],
        "control_feature_queries": original["control_feature_queries"],
        "config_overrides": {"dual_view_fusion_v1": True},
        "implementation": {"GPU_submission_ready": True, "physical_launcher_implemented": True,
            "physical_run_verified": False, "shared_runtime_functions_to_modify": [],
            "shared_verifier_functions_to_modify": []},
        "owned_files": [ref(packet / name) for name in ("probe_off20.py", "stove564_probe_env.py",
            "run_off20.sbatch", "test_off20_contract.py", "prepare_off20_implemented_manifest.py")],
        "planned_contact_skills": 40, "planned_fixed_contact_chunks": 6400,
        "planned_fixed_contact_controls": 32000, "planned_private_chunk_rows": 6440,
        "planned_measurement_captures": 100, "planned_view_captures": 200,
        "runtime_resources": []}
    root = Path("/public/home/sunyihan/rpent_libero_eval")
    for role, relative in (("interpreter", ".venv/bin/python"), ("libero_config", "runtime_config/config.yaml"),
            ("pi05_metadata", "assets/pi05/metadata.pt"), ("pi05_checkpoint", "assets/pi05/model.safetensors"),
            ("sam3_checkpoint", "assets/sam3/sam3.pt")):
        path = root / relative
        resource = {"role": role, "path": str(path), "bytes": path.stat().st_size}
        if role not in ("pi05_checkpoint", "sam3_checkpoint"):
            resource.update(ref(path))
        else:
            resource["identity_check"] = "explicit resolved file and exact byte count; large weight SHA not recomputed by eight CPU preflights"
        plan["runtime_resources"].append(resource)
    path = packet / "off20_probe_manifest.json"
    path.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps(ref(path)))


if __name__ == "__main__":
    main()
