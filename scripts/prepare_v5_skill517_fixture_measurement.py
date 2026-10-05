"""Prepare the registered 12 original fixture trials with measured geometry."""

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-manifest", type=Path, required=True)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--remote-root", type=Path,
                        default=Path("/public/home/sunyihan/rpent_libero_eval"))
    args = parser.parse_args()
    original = json.loads(args.original_manifest.read_text())
    if identity(args.base_config)["sha256"] != original["base_config"]["sha256"]:
        raise ValueError("original base config does not match the registered input")
    if len(original["cases"]) != 12 or any(case["kind"] != "articulate" for case in original["cases"]):
        raise ValueError("expected the 12 registered fixture smoke requests")
    base = json.loads(args.base_config.read_text())
    before = {key: base.get(key, False) for key in (
        "fixture_handle_geometry_v3", "fixture_drawer_clouds_v2")}
    base.update(fixture_handle_geometry_v3=True, fixture_drawer_clouds_v2=True)
    if base["libero_type"] != "standard":
        raise ValueError("original standard LIBERO only")
    args.output.mkdir(parents=True, exist_ok=False)
    config = args.output / "base_config_fixture517.json"
    config.write_text(json.dumps(base, indent=2) + "\n")
    remote_output = args.remote_root / "results/harness_v5/skill517_fixture_measurement_smoke_20261005/preparation"
    plan = copy.deepcopy(original)
    plan.update(
        purpose="registered original fixture development smoke with current handle/drawer RGB-D geometry; no qualification",
        base_config={"path": str(remote_output / config.name), "sha256": identity(config)["sha256"]},
        parent_manifest=identity(args.original_manifest),
        geometry_commit="66d5957",
        geometry_module_sha256="21fd3280708c57ab91d5cc986cbde6311f642c5fc149a9868cfa7faf26b538c8",
        changed_configuration={"before": before, "after": {key: True for key in before}},
        state_repetition="one first registered original initial state per type and arm; exactly 12 requests",
        new_training_rows=0, qualification_authorized=False,
        selection="all 12 original skill515 fixture requests retained in the same order; no outcome selection",
        preregistered_requests_by_type_arm=dict(Counter(
            f"{case['type']}/{case['condition']}" for case in plan["cases"])),
    )
    plan["metrics"]["first_attempt_denominator"] = "all 12 preregistered requests, including setup/measurement failures"
    # The previous manifest already records an explicit original catalog file.
    # The runner needs the exact case assets, not another embedded catalog copy.
    plan.pop("original_task_catalog", None)
    if plan["cases"] != original["cases"]:
        raise ValueError("registered case identities or recipes changed")
    for condition in plan["conditions"].values():
        for key in before:
            if condition.get("overrides", {}).get(key, True) is not True:
                raise ValueError("condition disables the new measured fixture geometry")
    manifest = args.output / "fixtures_smoke.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    registration = {
        "original_manifest": identity(args.original_manifest),
        "original_base_config": identity(args.base_config),
        "derived_base_config": {**identity(config), "runtime_path": str(remote_output / config.name)},
        "manifest": {**identity(manifest), "runtime_path": str(remote_output / manifest.name)},
        "cases_unchanged": True, "requests": len(plan["cases"]),
        "shards": [[case["name"] for case in plan["cases"][index::3]] for index in range(3)],
        "array": "0-2%8", "gpu_per_shard": 1, "node_binding": None,
        "source": "required SKILL_SOURCE environment variable supplied by runtime owner",
        "launcher": identity(Path(__file__).with_name("run_v5_skill517_fixture_measurement_smoke.sbatch")),
        "configuration_change": plan["changed_configuration"],
        "geometry_commit": plan["geometry_commit"], "geometry_module_sha256": plan["geometry_module_sha256"],
        "runtime_truth_use": "diagnostic labels only; public state remains measured entities and neutral IDs",
        "qualification_authorized": False, "new_training_rows": 0,
    }
    (args.output / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    print(json.dumps(registration, indent=2))


if __name__ == "__main__":
    main()
