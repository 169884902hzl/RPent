"""Register paired original stove measurements with complete five-action chunks."""

import argparse
import hashlib
import json
from pathlib import Path


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--remote-root", type=Path, default=Path("/public/home/sunyihan/rpent_libero_eval"))
    args = parser.parse_args()
    parent = json.loads(args.parent_manifest.read_text())
    if (parent["version"] != "original-stove-control-measurement/1-dev"
            or parent["planned_episodes"] != 10 or parent["shards"] != 4):
        raise ValueError("requires the explicit preserved 3666 parent protocol")
    config = json.loads(args.base_config.read_text())
    if config["libero_type"] != "standard":
        raise ValueError("original tasks only")
    args.output.mkdir(parents=True, exist_ok=False)
    base = args.output / "base_config_stove523.json"
    base.write_bytes(args.base_config.read_bytes())
    remote = args.remote_root / "results/harness_v5/stove523_fullchunks_original_20261005/preparation"
    plan = {**parent, "version": "original-stove-control-measurement/2-fullchunks-dev",
        "purpose": "repair native Goal7 turnon-induced contact chunk truncation; same original ten init development states",
        "preserved_3666_parent_manifest": identity(args.parent_manifest),
        "base_config": {"path": str(remote / base.name), "sha256": identity(base)["sha256"]},
        "diagnostic_server_module": "robots.libero.v5_stove_probe_env",
        "full_chunk_diagnostic_scope": True,
        "execution": "each on/off macro has its own registered 160x5 finite facade scope; raw original native success retained; external truncation stops immediately",
        "required_server_sha256": identity("robots/libero/v5_stove_probe_env.py")["sha256"],
        "required_probe_sha256": identity("scripts/probe_v5_stove521_endpoint.py")["sha256"],
        "required_stove_module_sha256": identity("robots/libero/v5_stove_measurement.py")["sha256"],
        "new_training_rows": 0, "qualification_authorized": False,
        "reserved_confirmation_states_consumed": False}
    from scripts.probe_v5_stove521_endpoint import validate_manifest
    validate_manifest(plan)
    manifest = args.output / "stove_control_fullchunks.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    registration = {"manifest": identity(manifest), "base_config": identity(base),
        "planned_episodes": 10, "planned_contact_skills": 20,
        "nominal_max_controls_per_skill": 800,
        "source": "final source snapshot supplied by parent through STOVE523_SOURCE",
        "shards": [[case["name"] for case in plan["cases"][index::4]] for index in range(4)],
        "array": "0-3%8", "node_binding": None, "dependency": None,
        "preserved_previous_job": 3666, "new_training_rows": 0, "qualification_authorized": False,
        "producer_files": {name: identity(name) for name in (
            "scripts/probe_v5_stove521_endpoint.py", "robots/libero/v5_stove_probe_env.py",
            "scripts/run_v5_stove523_full_chunks.sbatch")}}
    (args.output / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    print(json.dumps(registration, indent=2))


if __name__ == "__main__":
    main()
