"""Immutable code-only, per-control observability overlay on source4529."""

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
BASE = ROOT / "results/harness_v5/microwave_front_hint_CPU_20261008/r1"
BASE_IDENTITY = BASE / "source_identity.json"
BASE_SHA = "33613a51662cddad39d1964c9ad1bc3689951e2c8ae3c7c8cd50e042b46166e4"
BASE_PLAN = BASE / "close_front_hint40.json"
RECIPE = "coordination/microwave_identity_tracking_CPU_20261008/prepare_dense.py"
ADAPTER = "scripts/probe_v5_microwave_public571.py"
DENSE = "scripts/probe_v5_microwave_dense_public.py"
OVERLAYS = {ADAPTER, DENSE, RECIPE}


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(record):
    path = Path(record["path"])
    if not path.is_absolute() or ref(path)["sha256"] != record["sha256"]:
        raise ValueError("pinned source/input changed: " + str(path))
    return path


def adapter_patch(raw):
    text = raw.decode()
    old = "    install_owned_adapter(probe)\n    probe.main()\n"
    new = ("    install_owned_adapter(probe)\n"
           "    from scripts.probe_v5_microwave_dense_public import run_original_probe\n"
           "    run_original_probe(probe)\n")
    if text.count(old) != 1:
        raise ValueError("exact immutable public adapter entry differs")
    text = text.replace(old, new)
    compile(text, "public_adapter_with_dense_capture.py", "exec")
    return text.encode()


def build(args):
    if not all(path.is_absolute() for path in (args.packet, args.snapshot, args.output)):
        raise ValueError("absolute packet/source/output required")
    checked({"path": str(BASE_IDENTITY), "sha256": BASE_SHA})
    original_identity = json.loads(BASE_IDENTITY.read_text())
    checked(original_identity["archive"])
    packet = json.loads(args.packet.read_text())
    if {item["relative_path"] for item in packet["overlays"]} != OVERLAYS:
        raise ValueError("only dense diagnostic and exact original adapter/recipe may change")
    if Path(packet["base_plan"]["path"]) != BASE_PLAN:
        raise ValueError("retain the explicit visited original single case")
    original = json.loads(checked(packet["base_plan"]).read_text())
    args.snapshot.mkdir(parents=True, exist_ok=False)
    args.output.mkdir(parents=True, exist_ok=False)
    files, before = {}, {}
    for record in original_identity["files"]:
        path = checked(record)
        relative = record["relative_path"]
        if path != Path(original_identity["path"]) / relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("source outside explicit snapshot index")
        destination = args.snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        files[relative] = destination
        before[relative] = record["sha256"]
    overlays = []
    for record in packet["overlays"]:
        relative = record["relative_path"]
        if record["commit"] != packet["commit"] or record["before_sha256"] != before.get(relative):
            raise ValueError("overlay lineage differs")
        raw = base64.b64decode(record["data_base64"], validate=True)
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("overlay bytes differ")
        destination = args.snapshot / relative
        if relative == ADAPTER and raw != adapter_patch(destination.read_bytes()):
            raise ValueError("adapter may only wire dense diagnostic entry")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        files[relative] = destination
        overlays.append({key: record[key] for key in ("relative_path", "commit", "before_sha256", "sha256")})
    indexed = {key: {**ref(path), "relative_path": key} for key, path in sorted(files.items())}
    archive = Path(str(args.snapshot) + ".tar")
    with tarfile.open(archive, "x") as stream:
        for record in indexed.values():
            stream.add(record["path"], arcname=record["relative_path"], recursive=False)
    identity = {"path": str(args.snapshot), "commit": packet["commit"],
                "identity_kind": "source4529_plus_per_control_public_diagnostic_overlay",
                "base_source_identity": ref(BASE_IDENTITY), "overlays": overlays,
                "files": list(indexed.values()), "archive": ref(archive)}
    identity_path = args.output / "source_identity.json"
    identity_path.write_text(json.dumps(identity, indent=2) + "\n")
    plan = copy.deepcopy(original)
    if (plan["cohort"] != "development" or len(plan["cases"]) != 1
            or plan["cases"][0]["episode"] != {"suite": "libero_90", "task": 33, "seed": 0}):
        raise ValueError("same previously visited original task33/init0 diagnostic required")
    condition = plan["conditions"][plan["cases"][0]["condition"]]
    if condition["max_chunks"] != 40:
        raise ValueError("retain forty blocks and five original actions per block")
    # No execution option, controller, verifier, recovery or prompt is changed.
    plan["source_snapshot"] = identity
    plan["source_identity_file"] = ref(identity_path)
    plan["source_snapshot_sha256"] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    plan["producer"] = indexed[RECIPE]
    dependencies = []
    for record in original["producer_dependencies"]:
        path = Path(record["path"])
        if path.is_relative_to(Path(original_identity["path"])):
            dependencies.append(indexed[str(path.relative_to(original_identity["path"]))])
        else:
            checked(record)
            dependencies.append(record)
    dependencies.append(indexed[DENSE])
    plan["producer_dependencies"] = dependencies
    for key in ("adapter", "launcher"):
        relative = str(Path(original[key]["path"]).relative_to(original_identity["path"]))
        plan[key] = indexed[relative]
    plan.update(purpose="per-control public observability diagnostic; same pi05 chunks, prompts and budget as4529",
        qualification_authorized=False, training_allowed=False, train_allowed=False,
        new_training_rows=0, runtime_default_changed=False,
        dense_public_contract={"capture_interval_controls": 1, "control_dt_s": .05,
            "views": ["agentview", "wrist"], "resolution": [1024, 1024],
            "runtime_fields_changed": False, "motion_actions_added": 0,
            "private_labels_separate_ledger": True, "private_labels_control_execution": False,
            "confirmation_states_used_for_training": False},
        comparison_baseline={"job": 4529, "manifest": packet["base_plan"], "source_identity": ref(BASE_IDENTITY)})
    plan["cases"][0].update(previously_used_for_selection=True, excluded_from_training=True)
    plan["cases"][0]["name"] += "_per_control_public_dev"
    plan_path = args.output / "close_dense40.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    for record in original_identity["files"]:
        checked(record)
    checked(original_identity["archive"])
    receipt = {"version": "microwave-per-control-public-preparation/1-dev", "source_identity": ref(identity_path),
        "manifest": ref(plan_path), "snapshot": str(args.snapshot), "launcher": plan["launcher"],
        "source_files": len(indexed), "code_changes": overlays,
        "output": str(ROOT / "results/harness_v5/microwave_dense_public_original_20261008/close40"),
        "training_allowed": False, "qualification": False, "GPU_submitted": False,
        "base_snapshot_and_archive_unchanged": True, "same_launcher_CPU_preflight_pending": True,
        "same_launcher_physical_startup_pending": True}
    (args.output / "preparation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args())
