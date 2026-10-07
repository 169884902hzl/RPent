"""Prepare a code-only, opt-in staged withdrawal comparison to job4516.

Read only the explicit wrist-ROI source index and the visited close40 case.
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
BASE_DIRECTORY = ROOT / "results/harness_v5/microwave_wrist_roi_CPU_20261008/r1"
BASE_IDENTITY = BASE_DIRECTORY / "source_identity.json"
BASE_SHA = "1a22588bed125c1bdf4c3ce166d72a5a0841c2d7e4d927595b605caf67f8c52d"
BASE_PLAN = BASE_DIRECTORY / "close_wrist_roi40.json"
RECIPE = "coordination/microwave_staged_candidate_CPU_20261008/prepare.py"
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
        ("        microwave_wrist_fixed_roi_v1: bool = False,\n",
         "        microwave_wrist_fixed_roi_v1: bool = False,\n        microwave_staged_candidate_v1: bool = False,\n"),
        ("        self.microwave_wrist_fixed_roi_v1 = bool(microwave_wrist_fixed_roi_v1)\n",
         "        self.microwave_wrist_fixed_roi_v1 = bool(microwave_wrist_fixed_roi_v1)\n        self.microwave_staged_candidate_v1 = bool(microwave_staged_candidate_v1)\n"))
    if "microwave_staged_candidate_v1" in text:
        raise ValueError("base runtime already contains staged candidate flag")
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError("runtime flag patch does not match explicit readonly-source")
        text = text.replace(old, new, 1)
    compile(text, "readonly-source_runtime_with_readonly_flag.py", "exec")
    return text.encode()


def build(args):
    if not all(path.is_absolute() for path in (args.packet, args.snapshot, args.output)):
        raise ValueError("absolute packet/snapshot/output required")
    checked({"path": str(BASE_IDENTITY), "sha256": BASE_SHA})
    base = json.loads(BASE_IDENTITY.read_text())
    checked(base["archive"])
    packet = json.loads(args.packet.read_text())
    if {item["relative_path"] for item in packet["overlays"]} != OVERLAYS:
        raise ValueError("only capture, runtime flag and preparation recipe may change")
    original = json.loads(checked(packet["base_plan"]).read_text())
    if Path(packet["base_plan"]["path"]) != BASE_PLAN:
        raise ValueError("comparison must reuse the explicit readonly-source close40 case")
    snapshot, output = args.snapshot, args.output
    snapshot.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    files, before = {}, {}
    for record in base["files"]:
        old = checked(record)
        relative = record["relative_path"]
        if (old != Path(base["path"]) / relative or Path(relative).is_absolute()
                or ".." in Path(relative).parts or relative in files):
            raise ValueError("source file outside explicit readonly-source index: " + relative)
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old, destination)
        files[relative] = destination
        before[relative] = record["sha256"]
    changes = []
    for overlay in packet["overlays"]:
        relative = overlay["relative_path"]
        if overlay["commit"] != packet["commit"] or before.get(relative) != overlay["before_sha256"]:
            raise ValueError("overlay lineage does not match readonly-source: " + relative)
        raw = base64.b64decode(overlay["data_base64"], validate=True)
        if hashlib.sha256(raw).hexdigest() != overlay["sha256"]:
            raise ValueError("overlay bytes changed: " + relative)
        destination = snapshot / relative
        if relative == "robots/libero/v5_runtime.py" and raw != runtime_flag_patch(destination.read_bytes()):
            raise ValueError("comparison runtime may only gain the two staged candidate flag lines")
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
        "identity_kind": "explicit_wrist_roi_source_plus_staged_candidate_overlays",
        "base_source_identity": ref(BASE_IDENTITY), "overlays": changes,
        "files": list(indexed.values()), "archive": ref(archive)}
    identity_path = output / "source_identity.json"
    identity_path.write_text(json.dumps(identity, indent=2) + "\n")
    plan = copy.deepcopy(original)
    if (plan["cohort"] != "development" or len(plan["cases"]) != 1 or plan["new_training_rows"] != 0
            or plan["cases"][0]["episode"] != {"suite": "libero_90", "task": 33, "seed": 0}):
        raise ValueError("one visited original task33/init0 development comparison required")
    condition = plan["conditions"][plan["cases"][0]["condition"]]
    if (condition["max_chunks"] != 40 or condition["overrides"]["microwave_temporal_stop_v1"] is not True
            or condition["overrides"]["microwave_temporal_capture_v1"] is not True):
        raise ValueError("retain readonly-source forty-block budget and temporal stop")
    if (condition["overrides"].get("microwave_readonly_probe_v1") is not True
            or condition["overrides"].get("microwave_wrist_fixed_roi_v1") is not True):
        raise ValueError("retain readonly probe, wrist ROI and measured action trace")
    condition["overrides"]["microwave_staged_candidate_v1"] = True
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
    plan.update(purpose="visited original staged-public-candidate development comparison to4516; not qualification",
        qualification_authorized=False, runtime_default_changed=False, new_training_rows=0,
        comparison_baseline={"job": 4516, "manifest": packet["base_plan"], "source_identity": ref(BASE_IDENTITY)},
        staged_candidate_contract={"enabled": True, "source": "current independent measured frame/moving planes and proprioception",
            "reference": "same-frame independent agentview fixed patch is ROI guidance only",
            "fit": "actual wrist RGB-D points; original plane residual/reference thresholds",
            "missing_support": "unknown; never reuse agentview points as wrist",
            "promotion": "requires fresh measured wrist robot occlusion, otherwise retain original view",
            "baseline": "two non-withdrawing public frames with six real neutral holds before contact",
            "contact_probe": "one fresh RGB-D frame, zero release/move/hold controls",
            "endpoint_candidate": "original public plane-angle thresholds; trigger only, never stop",
            "after_candidate": "stable across actual contact controls for original 0.3s minimum, then withdraw and unchanged full validator",
            "stability": "original 3deg / 10mm door stability and original fixed-plane stability",
            "actual_interval_source": "vla_act_chunk.executed_action_count; absent trace is unknown",
            "private_labels_control_motion": False, "missing_measurement": "unmeasured, never fallback truth"})
    plan["cases"][0].update(previously_used_for_selection=True, excluded_from_training=True)
    plan["cases"][0]["name"] += "_staged_candidate_dev"
    plan_path = output / "close_staged_candidate40.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    for record in base["files"]:
        checked(record)
    checked(base["archive"])
    receipt = {"version": "microwave-public-staged-candidate-preparation/1-dev", "source_identity": ref(identity_path),
        "base_readonly-source_files_unchanged": True, "base_readonly-source_archive_unchanged": True,
        "source_files": len(indexed), "manifest": ref(plan_path), "launcher": plan["launcher"],
        "code_changes": changes, "snapshot": str(snapshot),
        "output": str(ROOT / "results/harness_v5/microwave_staged_candidate_original_20261008/close40"),
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
