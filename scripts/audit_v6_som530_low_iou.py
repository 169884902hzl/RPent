"""Diagnose low SoM mask IoU using only registered public RGB-D and masks."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import label


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(desc):
    path = Path(desc["path"])
    if identity(path)["sha256"] != desc["sha256"]:
        raise ValueError("explicit public artifact SHA changed: " + str(path))
    return path


def load(path):
    with np.load(path, allow_pickle=False) as data:
        return data["array"]


def area(box):
    return (box[2] - box[0]) * (box[3] - box[1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if identity(args.report)["sha256"] != args.report_sha256:
        raise ValueError("original SoM report changed")
    report = json.loads(args.report.read_text())
    checks = [json.loads(line) for line in checked(report["checks"]).read_text().splitlines()]
    selected = [r for r in checks if r["runtime_depth_supported_metrics"]["mask_iou"] < .5]
    args.output.mkdir(parents=True, exist_ok=False)
    panels, records, counts = [], [], Counter()
    for item in selected:
        image_path, world_path, camera_path, mask_path = [checked(item[k]) for k in ("image", "world", "camera_metadata", "mask")]
        image = Image.open(image_path).convert("RGB")
        world, mask = load(world_path), load(mask_path)
        metadata = json.loads(camera_path.read_text())
        if world.shape != (image.height, image.width, 3) or mask.shape != (image.height, image.width):
            raise ValueError("registered image/world/mask dimensions disagree")
        transform, intrinsic = np.asarray(metadata["extrinsic_cam2world"], float), np.asarray(metadata["intrinsic_K"], float)
        intrinsic = intrinsic.copy()
        intrinsic[0] *= image.width / metadata["width"]
        intrinsic[1] *= image.height / metadata["height"]
        rotation = transform[:3, :3]
        valid = mask & np.isfinite(world).all(axis=-1) & (np.abs(world).sum(axis=-1) > 1e-6)
        yy, xx = np.nonzero(valid)
        camera = (np.column_stack([world[valid], np.ones(len(xx))]) @ np.linalg.inv(transform).T)[:, :3]
        projected = camera @ intrinsic.T
        projected = projected[:, :2] / projected[:, 2:3]
        residual = projected - np.column_stack([xx, yy])
        errors = np.linalg.norm(residual, axis=1)
        components, _ = label(mask, np.ones((3, 3)))
        sizes = np.bincount(components.ravel())[1:]
        sizes = np.sort(sizes)[::-1]
        metrics, bbox, box = item["runtime_depth_supported_metrics"], item["runtime_depth_supported_metrics"]["sam_bbox_xyxy"], item["box"]
        boundary = [name for name, touched in (("left", mask[:, 0].any()), ("right", mask[:, -1].any()),
                                               ("top", mask[0].any()), ("bottom", mask[-1].any())) if touched]
        output = {"case": item["case"], "view": item["view"], "source_step": item["source_step"],
                  "category": item["category"], "entity": item["current_measurement"],
                  "input": {k: item[k] for k in ("image", "world", "camera_metadata", "mask")},
                  "runtime_metrics": metrics, "projected_aabb_metrics": item["projected_aabb_metrics"],
                  "runtime_box_to_SAM_bbox_area_ratio": area(box) / area(bbox),
                  "projected_AABB_box_to_SAM_bbox_area_ratio": area(item["projection_box"]) / area(bbox),
                  "SAM_mask_fill_of_own_bbox": int(mask.sum()) / area(bbox),
                  "SAM_connected_components": len(sizes),
                  "SAM_largest_component_fraction": int(sizes[0]) / int(mask.sum()),
                  "SAM_top_component_sizes": sizes[:5].tolist(),
                  "SAM_boundary_touch": boundary, "public_AABB_fov": item["fov"],
                  "camera_resolution": [metadata["width"], metadata["height"]],
                  "image_world_mask_resolution": [image.width, image.height],
                  "intrinsic_scale_xy": [image.width / metadata["width"], image.height / metadata["height"]],
                  "world_to_pixel_roundtrip": {"public_points": len(xx), "median_error_px": float(np.median(errors)),
                                               "p99_error_px": float(np.quantile(errors, .99)),
                                               "median_signed_xy_px": np.median(residual, axis=0).tolist(),
                                               "camera_z_positive_fraction": float((camera[:, 2] > 0).mean()),
                                               "rotation_det": float(np.linalg.det(rotation)),
                                               "rotation_orthogonality_max_abs": float(np.abs(rotation.T @ rotation - np.eye(3)).max())},
                  "interpretation": "roundtrip checks internal saved-public projection consistency, not an independent camera calibration ground truth"}
        records.append(output)
        counts[f"{item['view']}_low_mask_iou"] += 1
        counts["public_AABB_partially_clipped"] += item["fov"]["reason"] == "partially_clipped"
        counts["SAM_mask_touches_actual_image_boundary"] += bool(boundary)
        counts["mask_fill_of_own_bbox_below_half"] += output["SAM_mask_fill_of_own_bbox"] < .5
        overlay = np.asarray(image).copy()
        overlay[mask] = (.45 * overlay[mask] + .55 * np.array([0, 255, 80])).astype(np.uint8)
        panel = Image.fromarray(overlay)
        draw = ImageDraw.Draw(panel)
        draw.rectangle(item["projection_box"], outline=(255, 220, 0), width=4)
        draw.rectangle(box, outline=(255, 0, 100), width=4)
        panel.thumbnail((420, 420))
        tile = Image.new("RGB", (420, 460), "white")
        tile.paste(panel, (0, 40))
        ImageDraw.Draw(tile).text((4, 3), f"{item['view']} step {item['source_step']} IoU {metrics['mask_iou']:.3f}\nSAM green / projection yellow / runtime magenta", fill="black")
        panels.append(tile)
    canvas = Image.new("RGB", (420 * 3, 460 * ((len(panels) + 2) // 3)), "white")
    for i, panel in enumerate(panels):
        canvas.paste(panel, ((i % 3) * 420, (i // 3) * 460))
    montage = args.output / "low_iou_montage.png"
    canvas.save(montage)
    result = {"version": "public-original-SoM-low-IoU-diagnosis/1", "source_report": identity(args.report),
              "selected_low_cases": len(records), "selection": "all 11 sampled mask IoU<.5, no private label selection",
              "counts": dict(counts), "cases": records, "montage": identity(montage),
              "script": identity(Path(__file__)), "training_rows": 0, "renderer_changed": False,
              "old_mask_gate_result_preserved": {"passed": False, "images": report["images"], "fraction": report["fraction"]},
              "limits": ["A SAM mask can itself have wrong or fragmented semantic support; these computations do not invent object truth.",
                         "AABB clipping and actual recorded-mask boundary clipping are reported separately.",
                         "No mask-trimming, rectangle optimization, new entity parts or acceptance-rule change is made."]}
    path = args.output / "report.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"report": identity(path), "cases": len(records), "counts": dict(counts),
                      "roundtrip_p99_max_px": max(r["world_to_pixel_roundtrip"]["p99_error_px"] for r in records)}))


if __name__ == "__main__":
    main()
