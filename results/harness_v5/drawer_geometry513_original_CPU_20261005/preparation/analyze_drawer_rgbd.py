"""Compare original task RGB-D cabinet bands without simulator state."""

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

from robots.libero.v5_fixture_parts import fixture_parts, fixture_points, infer_cabinet_front, measured_handle_front
from robots.libero.v5_state import Entity


def entity(record):
    keys = ("id", "name", "xyz", "lower", "upper", "visible", "source_step", "part_of", "geometry")
    return Entity(**{key: record[key] for key in keys})


def file_identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    root = Path(__file__).resolve().parents[4]
    preparation = Path(__file__).resolve().parent
    inputs = json.loads((preparation / "public_inputs.json").read_text())
    baseline_commit = "45a91d0"
    old_source = subprocess.check_output(
        ["git", "show", f"{baseline_commit}:robots/libero/v5_fixture_parts.py"], cwd=root)
    baseline = {}
    exec(compile(old_source, "baseline_fixture_parts", "exec"), baseline)
    parents = {}
    for name, episode in zip(("open", "close"), inputs["episodes"]):
        parents[name] = entity(next(e for e in episode["public_at_stop"]["entities"] if e["name"] == "cabinet"))
    captures = []
    keys = ("open_agentview_00", "open_wrist_00", "close_agentview_00", "close_wrist_00",
            "close_agentview_01", "close_wrist_01")
    for key in keys:
        paths = {kind: preparation / f"{key}_{suffix}" for kind, suffix in (
            ("rgb", "high.png"), ("world", "world_high.npz"), ("metadata", "metadata.json"))}
        world = np.load(paths["world"])["array"]
        metadata = json.loads(paths["metadata"].read_text())
        camera = np.asarray(metadata["extrinsic_cam2world"], dtype=float)[:3, 3]
        parent = parents[key.split("_")[0]]
        cloud = fixture_points(world, parent)
        handle_axis, handle_evidence, handles = measured_handle_front(world, parent)
        combined = np.concatenate([cloud, handles])
        profile_axis, profile_evidence = infer_cabinet_front(combined, camera)
        axis = profile_axis or handle_axis
        valid = np.isfinite(world).all(axis=-1) & (np.abs(world).sum(axis=-1) > 1e-6)
        capture = {
            "capture": key, "files": {kind: file_identity(path) for kind, path in paths.items()},
            "coordinate_source": "public_rgbd_camera_to_world_measurement",
            "world_shape": list(world.shape), "valid_world_points": int(valid.sum()),
            "camera_xyz_m": camera.tolist(), "cabinet_points": len(cloud), "handle_points": len(handles),
            "front_axis": axis, "handle_evidence": handle_evidence, "profile_evidence": profile_evidence,
            "before_parts": baseline["fixture_parts"](parent, combined, axis, calibrated_front=True),
            "after_parts": fixture_parts(parent, combined, axis, calibrated_front=True),
        }
        if key == "close_agentview_00":
            public = inputs["episodes"][1]["setup"][0]["public_before"]["entities"]
            drawer = entity(next(e for e in public if e["name"] == "drawer"))
            current_drawer = fixture_points(world, drawer)
            augmented = np.concatenate([cloud, current_drawer])
            augmented_axis, augmented_evidence = infer_cabinet_front(augmented, camera)
            capture["initial_current_public_drawer_bound_diagnostic"] = {
                "public_drawer": next(e for e in public if e["name"] == "drawer"),
                "current_points": len(current_drawer), "front_axis": augmented_axis,
                "evidence": augmented_evidence,
                "parts": fixture_parts(parent, augmented, augmented_axis, calibrated_front=True),
                "limitation": "bounds-selected current pixels, not a saved SAM mask; not a runtime visibility claim",
            }
        captures.append(capture)
    report = {
        "version": "original-public-drawer-rgbd-diagnosis/1", "mode": "CPU_only_no_physics_qualification",
        "inputs": inputs, "public_inputs_file": file_identity(preparation / "public_inputs.json"),
        "baseline_commit": baseline_commit, "baseline_module_sha256": hashlib.sha256(old_source).hexdigest(),
        "current_module": file_identity(root / "robots/libero/v5_fixture_parts.py"),
        "parameters": {"parent_extent": "measured_public_bounds", "top_exclusion_m": .01,
                       "minimum_drawer_band_vertical_span_m": .015,
                       "current_captures_only": True, "moving_cloud_reused": False},
        "captures": captures,
    }
    output = preparation.parent / "report"
    output.mkdir(exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    for capture in captures:
        print(capture["capture"], "front", capture["front_axis"],
              "parts", [(part["name"], round(part["xyz"][2], 5)) for part in capture["after_parts"]])


if __name__ == "__main__":
    main()
