"""Evaluate explicit public clouds in the saved wrist camera; no physics."""

import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_verification import vertical_face


ROOT = Path(__file__).resolve().parent


def load_array(path):
    with np.load(path, allow_pickle=False) as saved:
        return saved["array"].astype(float)


def project(points, calibration, displacement=(0., 0., 0.)):
    transform = np.asarray(calibration["extrinsic_cam2world"])
    camera = (points - transform[:3, 3] - np.asarray(displacement)) @ transform[:3, :3]
    intrinsics = np.asarray(calibration["intrinsic_K"])
    pixels = camera[:, :2] / camera[:, 2, None] * np.diag(intrinsics)[:2] + intrinsics[:2, 2]
    inside = ((camera[:, 2] > 0) & (pixels[:, 0] >= 0) & (pixels[:, 0] < 1023.5)
              & (pixels[:, 1] >= 0) & (pixels[:, 1] < 1023.5))
    return pixels, inside


def main():
    manifest = json.loads((ROOT / "input_manifest.json").read_text())
    indexed = {}
    for item in manifest["files"]:
        path = Path(item["local_path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["source"]["sha256"]:
            raise ValueError("explicit public input changed: " + str(path))
        indexed[item["kind"]] = path
    clouds = {kind: load_array(indexed[kind + "_cloud"]) for kind in ("frame", "moving")}
    data = {}
    for camera in ("agentview", "wrist"):
        calibration = json.loads(indexed[camera + "_calibration"].read_text())
        world = load_array(indexed[camera + "_world"])
        rows, columns = [128, 256, 512, 768, 896], [128, 256, 512, 768, 896]
        mapped, _ = project(world[rows, columns], calibration)
        data[camera] = {"camera_xyz_m": np.asarray(calibration["extrinsic_cam2world"])[:3, 3].tolist(),
                        "pixel_roundtrip_max_error_px": float(abs(mapped - np.asarray(list(zip(columns, rows)))).max()),
                        "planes": {}}
        for kind, cloud in clouds.items():
            pixels, visible = project(cloud, calibration)
            locations = np.rint(pixels[visible]).astype(int)
            distances = np.linalg.norm(world[locations[:, 1], locations[:, 0]] - cloud[visible], axis=1)
            data[camera]["planes"][kind] = {
                "points": len(cloud), "in_camera_fov_points": int(visible.sum()),
                "in_camera_fov_fraction": float(visible.mean()),
                "median_projected_pixel_xy": np.median(pixels, axis=0).tolist(),
                "same_measured_surface_within_8mm": int((distances <= .008).sum()),
                "surface_fraction_of_entire_cloud": float((distances <= .008).sum() / len(cloud)),
            }
    wrist_world = load_array(indexed["wrist_world"])
    low, high = np.quantile(clouds["frame"], [.02, .98], axis=0)
    selected = ((wrist_world >= low - .002) & (wrist_world <= high + .002)).all(axis=-1)
    wrist_patch = wrist_world[selected]
    data["wrist_public_crossview_frame_patch"] = {
        "source": "current wrist RGB-D cropped by separately measured agentview frame bounds",
        "points": len(wrist_patch), "z_extent_m": float(np.ptp(wrist_patch[:, 2])),
        "vertical_face": vertical_face(wrist_patch),
        "existing_minimum_vertical_extent_m": .04,
    }
    calibration = json.loads(indexed["wrist_calibration"].read_text())
    data["hypothetical_same_orientation_camera_translation_only"] = []
    for displacement in ((.08, .10, .05), (.10, .10, .08), (.08, .12, .08)):
        data["hypothetical_same_orientation_camera_translation_only"].append({
            "delta_xyz_m": list(displacement),
            "in_camera_fov_fraction": {kind: float(project(cloud, calibration, displacement)[1].mean())
                                       for kind, cloud in clouds.items()},
            "new_scene_depth_or_occlusion_not_simulated": True,
            "robot_reachability_unverified": True,
        })
    data.update(training_allowed=False, private_joint_or_object_coordinates_read=False,
                physics_executed=False, confirmation=False)
    (ROOT / "analysis.json").write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
