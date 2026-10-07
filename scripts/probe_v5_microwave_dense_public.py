"""Owned original diagnostic: observe every real control without changing it.

Public RGB-D and robot proprioception are persisted first. Private fixture
labels go to a separate ledger and never supply motion, prompts, or stop.
This collector is excluded from training and skill qualification.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time


VERSION = "original-microwave-per-control-public-RGBD/1-dev"
MODULE = "scripts.probe_v5_microwave_dense_public"


def reference(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def capture_public(facade, observation, output, control):
    import numpy as np
    from PIL import Image
    from robots.libero.tools import _metric_depth, _world_from_depth

    capture = f"server{os.getpid()}:control{control}"
    root = output / f"server{os.getpid()}" / f"control{control:04d}"
    root.mkdir(parents=True, exist_ok=False)
    views = {}
    for view, camera in (("agentview", "agentview"), ("wrist", "robot0_eye_in_hand")):
        rgb, depth = facade.render_camera(camera_name=camera, height=1024, width=1024, depth=True)
        metadata = facade.get_camera_meta(camera_name=camera, height=1024, width=1024)
        if not metadata:
            raise RuntimeError("public camera metadata missing: " + view)
        rgb = np.asarray(rgb)[::-1]
        metric = _metric_depth(depth, metadata)[::-1]
        world = _world_from_depth(metric, metadata).astype(np.float16)
        if rgb.shape[:2] != world.shape[:2]:
            raise RuntimeError("public RGB-D capture shapes differ: " + view)
        image_path, world_path, meta_path = (root / (view + suffix) for suffix in (".png", "_world.npz", "_metadata.json"))
        Image.fromarray(np.ascontiguousarray(rgb).astype(np.uint8)).save(image_path)
        np.savez_compressed(world_path, array=world)
        meta_path.write_text(json.dumps(metadata, default=lambda a: np.asarray(a).tolist()) + "\n")
        views[view] = {"rgb": reference(image_path), "world": reference(world_path), "calibration": reference(meta_path),
                       "calibration_source": "same_current_public_camera_metadata_as_runtime"}
    states = np.asarray(observation["states"], dtype=float).reshape(-1)
    if len(states) < 8 or not np.isfinite(states[:8]).all():
        raise RuntimeError("current public robot proprioception missing")
    return {"version": VERSION, "capture_id": capture, "actual_control_index": control,
            "source": "perception_and_robot_proprioception", "control_dt_s": .05,
            "views": views, "robot": {"eef_xyz_m": states[:3].tolist(),
                "eef_orientation": states[3:6].tolist(), "gripper_qpos": states[6:8].tolist(),
                "gripper_opening_m": float(np.abs(states[6:8]).sum())},
            "additional_controls": 0, "private_labels_included": False,
            "train_allowed": False, "qualification": False}


def install_dense_capture(probe, plan_path, output):
    """Wrap the owned complete-chunk loop; all five original controls remain."""
    plan = json.loads(Path(plan_path).read_text())
    if (plan["cohort"] != "development" or len(plan["cases"]) != 1
            or plan["cases"][0]["episode"]["suite"] not in probe.ORIGINAL_SUITES
            or plan.get("training_allowed") is not False or plan.get("qualification_authorized") is not False):
        raise ValueError("one original, non-training, non-qualification dense diagnostic required")
    spec = plan["cases"][0]
    if spec.get("kind") != "articulate" or spec.get("object_category") != "microwave":
        raise ValueError("dense diagnostic is restricted to registered original microwave articulation")
    output = Path(output)
    if not output.is_absolute():
        raise ValueError("absolute explicit diagnostic output required")
    output.mkdir(parents=True, exist_ok=True)
    original_chunk = probe.complete_probe_chunk

    def chunk(facade, actions, *, return_all_frames=False):
        original_step = facade.step

        def step(action):
            result = original_step(action)
            control = facade._skill_chunk_accounting["executed_controls"] + 1
            started = time.perf_counter()
            record = {"capture_id": f"server{os.getpid()}:control{control}",
                      "actual_control_index": control, "capture_error": None,
                      "train_allowed": False, "qualification": False}
            try:
                record.update(capture_public(facade, result[0], output, control))
            except Exception as error:
                record.update(capture_error=repr(error), status="public_capture_error")
            record["wall_s"] = time.perf_counter() - started
            # Fix the public record before reading any private fixture label.
            with (output / "public_captures.jsonl").open("a") as stream:
                stream.write(probe.diagnostic_json(record) + "\n")
            label = {"capture_id": record["capture_id"], "actual_control_index": control,
                     "source": "simulation_diagnostic_only", "controls_execution": False,
                     "train_allowed": False, "qualification": False}
            try:
                label["private_fixture_label"] = facade.skill_truth(spec)
            except Exception as error:
                label.update(private_label_error=repr(error), private_fixture_label=None)
            with (output / "private_labels.jsonl").open("a") as stream:
                stream.write(probe.diagnostic_json(label) + "\n")
            return result

        facade.step = step
        try:
            return original_chunk(facade, actions, return_all_frames=return_all_frames)
        finally:
            facade.step = original_step

    probe.complete_probe_chunk = chunk


def run_original_probe(probe):
    """Client-side preparation inherited by its single owned server process."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args, _ = parser.parse_known_args()
    os.environ["MICROWAVE_DENSE_PLAN"] = str(args.manifest.resolve(strict=True))
    os.environ["MICROWAVE_DENSE_OUTPUT"] = str(args.output.resolve() / "dense_public")
    probe.PROBE_MODULE = MODULE
    probe.main()
    public = Path(os.environ["MICROWAVE_DENSE_OUTPUT"]) / "public_captures.jsonl"
    if not public.is_file():
        raise RuntimeError("startup_error: no real per-control public captures")
    rows = [json.loads(line) for line in public.read_text().splitlines() if line.strip()]
    failures = sum(row.get("capture_error") is not None for row in rows)
    summary = {"version": VERSION, "public_frames": len(rows), "public_capture_errors": failures,
               "public_capture_error_rate": failures / len(rows), "public_ledger": reference(public),
               "private_label_ledger": reference(public.with_name("private_labels.jsonl")),
               "train_allowed": False, "qualification": False, "additional_controls": 0}
    (public.parent / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if failures:
        raise RuntimeError("per-control capture_error: preserved physical trial requires infrastructure diagnosis")


def main():
    from scripts import probe_v5_skill501_original as probe
    if "--serve" not in sys.argv:
        raise ValueError("this module is the owned server entry; client must use the unchanged launcher adapter")
    install_dense_capture(probe, Path(os.environ["MICROWAVE_DENSE_PLAN"]), Path(os.environ["MICROWAVE_DENSE_OUTPUT"]))
    probe.serve()


if __name__ == "__main__":
    main()
