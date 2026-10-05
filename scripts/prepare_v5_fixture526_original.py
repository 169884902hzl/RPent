"""Prepare a 24-request original fixture comparison without faulty open setup."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--original-catalog", type=Path, required=True)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--remote-root", type=Path, default=Path("/public/home/sunyihan/rpent_libero_eval"))
    args = parser.parse_args()
    previous = json.loads(args.parent_manifest.read_text())
    catalog = json.loads(args.original_catalog.read_text())
    if identity(args.original_catalog)["sha256"] != previous["original_task_catalog_file"]["sha256"]:
        raise ValueError("explicit original catalog changed")
    original = {(t["suite"], t["task"]): t for t in catalog}
    base = json.loads(args.base_config.read_text())
    if base["libero_type"] != "standard":
        raise ValueError("original LIBERO only")
    flags = {key: True for key in (
        "fixture_handle_geometry_v3", "fixture_drawer_clouds_v2", "fixture_endpoint_geometry_v3",
        "microwave_door_cloud_v6", "door_point_recall_v7", "door_plane_consensus_v1",
        "fixture_part_visibility_v2", "fixture_part_prompt_v1", "selected_fixture_target_v1",
        "articulate_verification_v2", "articulate_view_retreat_v1",
        "microwave_recall_geometry_v3", "microwave_instance_geometry_v4")}
    before_flags = {k: base.get(k, False) for k in flags}
    base.update(flags)
    cases = []
    specs = [
        ("drawer_open", "libero_goal", 0, "wooden_cabinet_1_middle_region", "cabinet middle drawer", "open", [],
         "open the middle drawer of the cabinet"),
        ("drawer_close", "libero_10", 3, "white_cabinet_1_bottom_region", "cabinet bottom drawer", "close", [],
         "close the bottom drawer of the cabinet"),
        ("microwave_open", "libero_10", 9, "microwave_1", "microwave", "open", [{
            "tool": "articulate", "object_symbol": "microwave_1", "object_category": "microwave", "mode": "close"}],
         "open the microwave"),
        ("microwave_close", "libero_10", 9, "microwave_1", "microwave", "close", [], "close the microwave"),
    ]
    for type_name, suite, task, symbol, category, mode, setup, prompt in specs:
        asset = original[(suite, task)]
        for seed in range(3):
            for condition in ("current160", "original_style160"):
                cases.append({"name": f"{type_name}_{suite}_t{task}_s{seed}_{condition}",
                    "episode": {"suite": suite, "task": task, "seed": seed}, "kind": "articulate",
                    "type": type_name, "mode": mode, "object_symbol": symbol, "object_category": category,
                    "subtask_prompt": prompt, "original_style_contact_prompt": prompt,
                    "prompt_origin": "original_LIBERO_subtask_vocabulary_no_PRO_input",
                    "original_instruction": asset["instruction"], "setup": setup,
                    "condition": condition, "trial_index": seed, "initial_state_repetition": 0,
                    "state_sha256": asset["state_sha256"][seed], "bddl": asset["bddl"], "init_file": asset["init_file"],
                    "first_attempt_expected_direction": {"requested_before": False, "opposite_before": True,
                        "diagnostic_labels_only": True, "not_a_truth_control_or_skip_rule": True},
                    "setup_policy": "fixed real close only before microwave open; no open-before-close setup",
                    "private_metadata_use": "diagnostic labels only, never public state/candidate/controller"})
    args.output.mkdir(parents=True, exist_ok=False)
    config = args.output / "base_config_fixture526.json"
    config.write_text(json.dumps(base, indent=2) + "\n")
    remote = args.remote_root / "results/harness_v5/fixture526_original_direction_20261005/preparation"
    conditions = {name: {**previous["conditions"][old],
        "registered_contact_prompt_override": name == "original_style160"}
        for name, old in (("current160", "current160"), ("original_style160", "vla_subtask160"))}
    plan = {**previous, "purpose": "paired actual opposite-endpoint contact comparison; separate maintained/already-satisfied/setup-contaminated cases",
        "parent_manifest": identity(args.parent_manifest), "cases": cases, "conditions": conditions,
        "base_config": {"path": str(remote / config.name), "sha256": identity(config)["sha256"]},
        "geometry_module_sha256": identity("robots/libero/v5_fixture_parts.py")["sha256"],
        "geometry_commit": "final_source_snapshot_records_commit",
        "producer": "scripts.probe_v5_fixture526_original",
        "producer_sha256": identity("scripts/probe_v5_fixture526_original.py")["sha256"],
        "diagnostic_server": "robots.libero.v5_fixture_probe_env",
        "diagnostic_server_sha256": identity("robots/libero/v5_fixture_probe_env.py")["sha256"],
        "chunk_scope": "fixed setup/first stage, <=160 five-control chunks, native term preserved without truncating each chunk, external truncation stops immediately",
        "changed_configuration": {"before": before_flags, "after": flags},
        "state_repetition": "3 fixed original init per type; 2 paired methods, fresh physical reset per method",
        "selection": "original Goal0, Long3/9 init0-2; original90 confirmation pool remains unvisited",
        "preregistered_requests_by_type_arm": dict(Counter(f"{c['type']}/{c['condition']}" for c in cases)),
        "metrics": {"first_attempt_denominator": "all 24 requests, preserve setup/binding/perception failures",
            "new_endpoint_success": "requested=false and opposite=true before skill, requested=true after",
            "already_satisfied": "preserved and destroyed reported separately, not new endpoint success",
            "setup_direction": "both requested/opposite labels at every boundary; no private label routing",
            "physical_controls": "actual trace actions, separate from requested chunks",
            "measurement": "independent moving/static current clouds; absent remains unknown"},
        "qualification_authorized": False, "new_training_rows": 0}
    manifest = args.output / "fixtures_direction.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    registration = {"manifest": identity(manifest), "base_config": identity(config),
        "requests": len(cases), "array": "0-2%8", "gpu_per_shard": 1, "node_binding": None, "dependency": None,
        "changed_configuration": plan["changed_configuration"], "first_attempt_expected_direction": cases[0]["first_attempt_expected_direction"],
        "required_geometry_sha256": plan["geometry_module_sha256"], "required_producer_sha256": plan["producer_sha256"],
        "required_diagnostic_server_sha256": plan["diagnostic_server_sha256"],
        "qualified_confirmation": False, "new_training_rows": 0}
    (args.output / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    print(json.dumps(registration, indent=2))


if __name__ == "__main__":
    main()
