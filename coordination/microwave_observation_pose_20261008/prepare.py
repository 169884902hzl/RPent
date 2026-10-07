"""Prepare a code-only, opt-in observation-pose comparison to job4493.

Read only the explicit source584 index and the already visited capture8 case.
No running snapshot, original state, verifier threshold or launcher is changed.
"""

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
BASE_DIRECTORY = ROOT / "results/harness_v5/microwave584_source_CPU_20261008/r1"
BASE_IDENTITY = BASE_DIRECTORY / "source_identity.json"
BASE_SHA = "58961a05eeaf54ad97aee5654738f3c25fdc4310787689863e3ca399ae8e4299"
BASE_PLAN = BASE_DIRECTORY / "capture8.json"
RECIPE = "coordination/microwave_observation_pose_20261008/prepare.py"
OVERLAYS = {"robots/libero/v5_microwave_capture.py", "robots/libero/v5_runtime.py", RECIPE}


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(record):
    path = Path(record["path"])
    if not path.is_absolute() or ref(path)["sha256"] != record["sha256"]:
        raise ValueError("registered file changed: " + str(path))
    return path


def runtime_flag_patch(raw):
    """Apply exactly the two committed flag lines to the comparison runtime."""
    text = raw.decode()
    replacements = (
        ("        microwave_temporal_capture_every_v1: int = 1,\n",
         "        microwave_temporal_capture_every_v1: int = 1,\n        microwave_observation_pose_v1: bool = False,\n"),
        ("        self.microwave_temporal_capture_every_v1 = int(microwave_temporal_capture_every_v1)\n",
         "        self.microwave_temporal_capture_every_v1 = int(microwave_temporal_capture_every_v1)\n        self.microwave_observation_pose_v1 = bool(microwave_observation_pose_v1)\n"))
    if "microwave_observation_pose_v1" in text:
        raise ValueError("base runtime already contains observation flag")
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError("runtime flag patch does not match explicit source584")
        text = text.replace(old, new, 1)
    compile(text, "source584_runtime_with_observation_flag.py", "exec")
    return text.encode()


def build(args):
    if not all(path.is_absolute() for path in (args.packet, args.snapshot, args.output)):
        raise ValueError("absolute packet/snapshot/output required")
    checked({"path": str(BASE_IDENTITY), "sha256": BASE_SHA})
    base = json.loads(BASE_IDENTITY.read_text())
    checked(base["archive"])
    packet = json.loads(args.packet.read_text())
    if {item["relative_path"] for item in packet["overlays"]} != OVERLAYS:
        raise ValueError("only observation capture, runtime flag and preparation recipe may change")
    original = json.loads(checked(packet["base_plan"]).read_text())
    if Path(packet["base_plan"]["path"]) != BASE_PLAN:
        raise ValueError("comparison must reuse the explicit source584 capture8 case")
    snapshot, output = args.snapshot, args.output
    snapshot.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    files, before = {}, {}
    for record in base["files"]:
        old = checked(record)
        relative = record["relative_path"]
        if (old != Path(base["path"]) / relative or Path(relative).is_absolute()
                or ".." in Path(relative).parts or relative in files):
            raise ValueError("source file outside explicit source584 index: " + relative)
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old, destination)
        files[relative] = destination
        before[relative] = record["sha256"]
    changes = []
    for overlay in packet["overlays"]:
        relative = overlay["relative_path"]
        if overlay["commit"] != packet["commit"] or before.get(relative) != overlay["before_sha256"]:
            raise ValueError("overlay lineage does not match source584: " + relative)
        raw = base64.b64decode(overlay["data_base64"], validate=True)
        if hashlib.sha256(raw).hexdigest() != overlay["sha256"]:
            raise ValueError("overlay bytes changed: " + relative)
        destination = snapshot / relative
        if relative == "robots/libero/v5_runtime.py" and raw != runtime_flag_patch(destination.read_bytes()):
            raise ValueError("comparison runtime may only gain the two observation flag lines")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        files[relative] = destination
        changes.append({key: overlay[key] for key in ("relative_path", "commit", "before_sha256", "sha256", "content_origin")})
    indexed = {relative: {**ref(path), "relative_path": relative} for relative, path in sorted(files.items())}
    archive = Path(str(snapshot) + ".tar")
    if archive.exists():
        raise FileExistsError(archive)
    with tarfile.open(archive, "w") as stream:
        for record in indexed.values():
            stream.add(record["path"], arcname=record["relative_path"], recursive=False)
    identity = {"path": str(snapshot), "commit": packet["commit"],
        "identity_kind": "explicit_source584_plus_observation_pose_overlays",
        "base_source_identity": ref(BASE_IDENTITY), "overlays": changes,
        "files": list(indexed.values()), "archive": ref(archive)}
    identity_path = output / "source_identity.json"
    identity_path.write_text(json.dumps(identity, indent=2) + "\n")
    plan = copy.deepcopy(original)
    if (plan["cohort"] != "development" or len(plan["cases"]) != 1 or plan["new_training_rows"] != 0
            or plan["cases"][0]["episode"] != {"suite": "libero_90", "task": 33, "seed": 0}):
        raise ValueError("one visited original task33/init0 development comparison required")
    condition = plan["conditions"][plan["cases"][0]["condition"]]
    if (condition["max_chunks"] != 8 or condition["overrides"]["microwave_temporal_stop_v1"] is not False
            or condition["overrides"]["microwave_temporal_capture_v1"] is not True):
        raise ValueError("retain source584 capture-only eight-block budget")
    condition["overrides"]["microwave_observation_pose_v1"] = True
    plan["source_snapshot"] = identity
    plan["source_identity_file"] = ref(identity_path)
    plan["source_snapshot_sha256"] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    plan["producer"] = indexed[RECIPE]
    dependencies = []
    for item in original["producer_dependencies"]:
        path = Path(item["path"])
        if path.is_relative_to(Path(base["path"])):
            dependencies.append(indexed[str(path.relative_to(base["path"]))])
        else:
            checked(item)
            dependencies.append(item)
    plan["producer_dependencies"] = dependencies
    for key in ("adapter", "launcher"):
        relative = str(Path(original[key]["path"]).relative_to(base["path"]))
        plan[key] = indexed[relative]
    plan.update(purpose="visited original current-plane observation-pose development comparison to4493; not qualification",
        qualification_authorized=False, runtime_default_changed=False, new_training_rows=0,
        comparison_baseline={"job": 4493, "manifest": packet["base_plan"], "source_identity": ref(BASE_IDENTITY)},
        observation_pose_contract={"enabled": True, "source": "current independent measured frame/moving planes and proprioception",
            "raise_then_translate": True, "maximum_translation_m": .15,
            "after_motion": "two fresh RGB-D frames, existing fits and thresholds unchanged",
            "private_labels_control_motion": False, "missing_measurement": "unmeasured, never fallback truth"})
    plan["cases"][0].update(previously_used_for_selection=True, excluded_from_training=True)
    plan["cases"][0]["name"] += "_observation_pose_dev"
    plan_path = output / "capture8.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    for record in base["files"]:
        checked(record)
    checked(base["archive"])
    receipt = {"version": "microwave-public-observation-pose-preparation/1-dev", "source_identity": ref(identity_path),
        "base_source584_files_unchanged": True, "base_source584_archive_unchanged": True,
        "source_files": len(indexed), "manifest": ref(plan_path), "launcher": plan["launcher"],
        "code_changes": changes, "snapshot": str(snapshot),
        "output": str(ROOT / "results/harness_v5/microwave_observation_pose_original_20261008/capture8"),
        "GPU_submitted": False, "new_physical_trials": 0, "same_launcher_CPU_preflight_pending": True,
        "real_same_launcher_startup_pending": True, "qualification": False}
    (output / "preparation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args())
