"""Prepare one visited original-state development probe from an explicit plan.

No new evaluation state, PRO file, training row, directory scan or qualification
is introduced. The existing original90 diagnostic runner supplies private labels
after the public controller, as in the retained selection batch.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path


def prepare(source, output, *, case_name=None, enable_stop=False, max_chunks=8, source_identity_file=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    original = json.loads(source.read_text())
    cases = original["cases"]
    selected = next((case for case in cases if case["name"] == case_name), None) if case_name else cases[0]
    if selected is None or selected["episode"]["suite"] not in (
            "libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"):
        raise ValueError("one explicit original-task case is required")
    plan = copy.deepcopy(original)
    case = copy.deepcopy(selected)
    condition = copy.deepcopy(original["conditions"][case["condition"]])
    condition_name = "public_microwave_dual_temporal_stop" if enable_stop else "public_microwave_dual_temporal_capture"
    condition["max_chunks"] = max_chunks
    condition.setdefault("overrides", {}).update(
        dual_view_fusion_v1=True, fixture_endpoint_geometry_v3=True,
        microwave_temporal_capture_v1=True, microwave_temporal_stop_v1=bool(enable_stop),
        microwave_temporal_capture_every_v1=1)
    # The existing fixture-sync hook only adds post-block private metrology;
    # these values do not enter public capture, stop or skill selection.
    condition["private_fixture_sync"] = True
    case["condition"] = condition_name
    case["name"] += "_temporal_stop_dev" if enable_stop else "_temporal_capture_dev"
    plan.update(version="microwave-public-dual-temporal-wiring/1-dev", cohort="development",
                cases=[case], conditions={condition_name: condition}, runtime_default_changed=False,
                purpose="visited original one-case physical capture smoke; not qualification",
                new_training_rows=0, confirmation="none; retained prior state is development only",
                parent_manifest={"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
                startup_requirement="same snapshot/launcher: obtain an actual physical request before releasing array")
    plan["budget"] = {**plan.get("budget", {}), "max_chunks": max_chunks,
                      "note": "bounded startup/capture smoke; not a skill success comparison"}
    plan["metrics"] = {**plan.get("metrics", {}),
                       "first_attempt_denominator": "one explicitly selected visited development state; no qualification"}
    if source_identity_file is not None:
        identity_path = Path(source_identity_file).resolve(strict=True)
        identity = json.loads(identity_path.read_text())
        snapshot = Path(identity["path"])
        if not snapshot.is_absolute() or not identity.get("commit"):
            raise ValueError("source identity requires absolute snapshot and commit")
        indexed = {ref["relative_path"]: ref for ref in identity["files"]}
        required = ("robots/libero/v5_microwave_capture.py", "robots/libero/v5_microwave_door_temporal.py",
                    "robots/libero/v5_runtime.py", "scripts/probe_v5_skill501_original.py",
                    "scripts/probe_v5_microwave_public571.py", "scripts/v5_probe_preflight.py",
                    "coordination/microwave_runtime_wiring_20261007/prepare_smoke.py",
                    "coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch")
        for name in required:
            ref = indexed[name]
            if Path(ref["path"]) != snapshot / name:
                raise ValueError(f"source reference outside expected snapshot: {name}")
            if hashlib.sha256(Path(ref["path"]).read_bytes()).hexdigest() != ref["sha256"]:
                raise ValueError(f"source file hash changed: {name}")
        plan["source_snapshot"] = identity
        plan["source_identity_file"] = {"path": str(identity_path),
                                       "sha256": hashlib.sha256(identity_path.read_bytes()).hexdigest()}
        plan["producer"] = indexed[required[-2]]
        plan["producer_dependencies"] = [indexed[name] for name in required[:-2]]
        plan["adapter"] = indexed["scripts/probe_v5_microwave_public571.py"]
        plan["launcher"] = indexed[required[-1]]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    return {"path": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "case": case["name"], "stop_enabled": bool(enable_stop)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-name")
    parser.add_argument("--enable-stop", action="store_true")
    parser.add_argument("--max-chunks", type=int, default=8)
    parser.add_argument("--source-identity-file", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source_manifest, args.output, case_name=args.case_name,
                             enable_stop=args.enable_stop, max_chunks=args.max_chunks,
                             source_identity_file=args.source_identity_file), ensure_ascii=False))
