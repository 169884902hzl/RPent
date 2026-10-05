"""Original-task false-off diagnosis; private predicate fields are labels only."""

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
from scipy.ndimage import label

from robots.libero.v5_stove_measurement import measured_stove_endpoint


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    preparation = Path(__file__).resolve().parent
    root = preparation.parents[3]
    selected = json.loads((preparation / "selected_evidence.json").read_text())
    first = selected["first_attempt"]
    measurements = first["verification_measurements"]["stove_rgbd"]
    old_source = subprocess.check_output(
        ["git", "show", "f62d053:robots/libero/v5_stove_measurement.py"], cwd=root)
    baseline = {"__name__": "robots.libero.v5_stove_measurement"}
    exec(compile(old_source, "baseline_stove", "exec"), baseline)
    old, old_evidence = baseline["measured_stove_endpoint"](measurements["before"], measurements["after"], "turn_off")
    new, new_evidence = measured_stove_endpoint(measurements["before"], measurements["after"], "turn_off")
    bounds = measurements["before"]["measured_bounds"]
    lower, upper = np.asarray(bounds["lower"]), np.asarray(bounds["upper"])
    captures = []
    for step in range(3):
        paths = {"rgb": preparation / f"main_0{step}.png",
                 "world": preparation / f"main_0{step}_world.npz",
                 "metadata": preparation / f"main_0{step}_metadata.json"}
        image = np.asarray(Image.open(paths["rgb"]).convert("RGB"))
        world = np.load(paths["world"])["array"].astype(float)
        metadata = json.loads(paths["metadata"].read_text())
        available = np.isfinite(world).all(axis=-1) & (np.abs(world).sum(axis=-1) > 1e-6)
        # Diagnostic-only ROI from the publicly measured stove extent. It is
        # not an adopted control detector or a semantic knob segmentation.
        available &= ((world[..., 0] >= lower[0] - .15) & (world[..., 0] <= lower[0] + .01)
                      & (world[..., 1] >= lower[1] - .02) & (world[..., 1] <= upper[1] + .02))
        available &= ((world[..., 2] >= upper[2] + .014)
                      & (world[..., 2] <= upper[2] + .031) & (image.max(axis=-1) < 70))
        components, count = label(available)
        candidates = []
        for index in range(1, count + 1):
            mask = components == index
            points = world[mask]
            if len(points) < 50:
                continue
            lo, hi = np.quantile(points, (.02, .98), axis=0)
            _, values, vectors = np.linalg.svd(points[:, :2] - np.median(points[:, :2], axis=0), full_matrices=False)
            rows, cols = np.where(mask)
            candidates.append({
                "pixels": len(points), "lower": lo.tolist(), "upper": hi.tolist(),
                "pixel_bounds_rc": [int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max())],
                "axis_angle_degrees_mod180": float(np.degrees(np.arctan2(vectors[0, 1], vectors[0, 0])) % 180),
                "axis_elongation_ratio": float(values[0] / values[1]),
            })
        captures.append({"source_step": step, "files": {key: identity(path) for key, path in paths.items()},
                         "camera_to_world": metadata["extrinsic_cam2world"],
                         "candidate_components": candidates,
                         "limitation": "geometry/color proposal only; no SAM control mask and no endpoint classification"})
    report = {
        "scope": "original Goal task7 init0, job3643 selected case; CPU only",
        "source_record": {"path": selected["path"], "sha256": selected["sha256"]},
        "public_input_file": identity(preparation / "selected_evidence.json"),
        "baseline_module_commit": "f62d053", "baseline_module_sha256": hashlib.sha256(old_source).hexdigest(),
        "new_module": identity(root / "robots/libero/v5_stove_measurement.py"),
        "diagnostic_labels_only": {"before": first["private_before"], "after": first["private_after"]},
        "public_before": measurements["before"]["features"], "public_after": measurements["after"]["features"],
        "old_verified": old, "old_evidence": old_evidence, "new_verified": new, "new_evidence": new_evidence,
        "diagnostic_control_proposal_parameters": {
            "region": "negative-X edge of measured stove expanded outward 15cm",
            "height_band_above_measured_stove_m": [.014, .031], "rgb_maximum": 70,
            "minimum_component_pixels": 50, "deployed": False,
        },
        "captures": captures,
        "conclusion": "dark coils can coexist with an intermediate knob position; current control views are arm-occluded",
        "physical_trials": 0, "new_training_rows": 0, "qualification_authorized": False,
    }
    output = preparation.parent / "report.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"old_verified": old, "new_verified": new, "private_off_label": first["private_after"]["satisfied"],
                      "red_pixels": [report["public_before"]["red_pixels"], report["public_after"]["red_pixels"]],
                      "capture_components": [len(c["candidate_components"]) for c in captures],
                      "report": identity(output)}))


if __name__ == "__main__":
    main()
