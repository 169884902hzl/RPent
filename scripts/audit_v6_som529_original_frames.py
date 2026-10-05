"""CPU-only SoM projection audit on an explicit original RGB-D frame audit.

Uses public same-frame measurements and registered SAM masks. No simulation,
private object coordinates, artifact discovery, threshold fitting or training
rows. Cached pregrasp bounds are separate FOV hypotheses, not current marks.
"""

import argparse
from collections import Counter
import hashlib
import inspect
import itertools
import json
from pathlib import Path
import random

import numpy as np
from PIL import Image

from robots.libero import v6_som


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(desc):
    path = Path(desc["path"])
    if identity(path)["sha256"] != desc["sha256"]:
        raise ValueError("explicit artifact SHA changed: " + str(path))
    return path


def artifact(output, name, step):
    if Path(name).name != name:
        raise ValueError("artifact declaration must be a base name")
    return output / name / f"{step:02d}{Path(name).suffix}"


def load(path):
    with np.load(path, allow_pickle=False) as data:
        return data["array"]


def overlap(box, mask):
    if box is None:
        return {"mask_iou": 0., "mask_coverage": 0., "bbox_iou": 0.}
    x0, y0, x1, y1 = box
    intersection, area = int(mask[y0:y1, x0:x1].sum()), (x1 - x0) * (y1 - y0)
    rows, cols = np.nonzero(mask)
    if not len(rows):
        return {"mask_iou": 0., "mask_coverage": 0., "bbox_iou": 0.}
    reference = [int(cols.min()), int(rows.min()), int(cols.max()) + 1, int(rows.max()) + 1]
    common = max(0, min(x1, reference[2]) - max(x0, reference[0])) * max(0, min(y1, reference[3]) - max(y0, reference[1]))
    reference_area = (reference[2] - reference[0]) * (reference[3] - reference[1])
    return {"mask_iou": intersection / max(1, area + int(mask.sum()) - intersection),
            "mask_coverage": intersection / max(1, int(mask.sum())),
            "bbox_iou": common / max(1, area + reference_area - common),
            "sam_bbox_xyxy": reference, "mask_pixels": int(mask.sum())}


def fov(entity, metadata, size):
    """Explain clipping using public bounds and the saved camera calibration."""
    corners = np.array(list(itertools.product(*zip(entity["lower"], entity["upper"]))))
    camera = (np.column_stack([corners, np.ones(8)]) @ np.linalg.inv(metadata["extrinsic_cam2world"]).T)[:, :3]
    positive = camera[camera[:, 2] >= 1e-5]
    if not len(positive):
        return {"reason": "all_public_bounds_behind_camera_near_plane", "corners_in_front": 0}
    intrinsic = np.asarray(metadata["intrinsic_K"], float).copy()
    intrinsic[0] *= size[0] / metadata["width"]
    intrinsic[1] *= size[1] / metadata["height"]
    pixels = positive @ intrinsic.T
    pixels = pixels[:, :2] / pixels[:, 2:3]
    lo, hi = pixels.min(axis=0), pixels.max(axis=0)
    reasons = []
    for test, text in ((hi[0] < 0, "outside_left"), (hi[1] < 0, "outside_top"),
                       (lo[0] >= size[0], "outside_right"), (lo[1] >= size[1], "outside_bottom")):
        if test:
            reasons.append(text)
    clipped = lo[0] < 0 or lo[1] < 0 or hi[0] > size[0] or hi[1] > size[1] or len(positive) != 8
    return {"reason": "+".join(reasons) if reasons else "partially_clipped" if clipped else "within_image_bounds",
            "corners_in_front": len(positive), "positive_corner_pixel_bounds": [lo.tolist(), hi.tolist()],
            "near_plane_edge_projection_is_handled_by_shared_projector": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--audit-report-sha256", required=True)
    parser.add_argument("--seed", type=int, default=360)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if identity(args.audit_report)["sha256"] != args.audit_report_sha256:
        raise ValueError("registered synchronous-frame audit report changed")
    audit = json.loads(args.audit_report.read_text())
    plan = json.loads(checked(audit["manifest"]).read_text())
    registered = {c["name"]: c for c in plan["cases"]}
    public = {}
    for source in audit["sources"]:
        path = checked(source["closed_prefix"])
        for line in path.read_text().splitlines():
            row = json.loads(line)
            case = row["case"]
            if registered.get(case["name"]) != case or case["episode"]["suite"] not in {
                    "libero_spatial", "libero_object", "libero_goal", "libero_10"}:
                raise ValueError("case differs from explicit original-task manifest")
            before = [e for e in row["first_attempt"]["public_before"]["entities"] if e["name"] == case["object_category"]]
            cache = before[0] if len(before) == 1 else None
            public[case["name"]] = {"output": Path(row["output_dir"]), "before_cache": cache}
    evidence_path = checked(audit["frame_evidence"])
    inventory, pools, counts = [], {}, Counter()
    for line in evidence_path.read_text().splitlines():
        record = json.loads(line)
        if record["case"] not in registered:
            raise ValueError("frame case was not registered")
        meta = json.loads(checked(record["metadata"]).read_text())
        output, step = public[record["case"]]["output"], record["source_step"]
        states = json.loads((output / "states.json").read_text())
        state_step = next(s for s in states["steps"] if s["step_idx"] == step)
        declared = set(state_step["artifacts"])
        for camera in ("agentview", "wrist"):
            names = (f"{camera}_high.png", f"{camera}_metadata.json", f"{camera}_world_high.npz")
            if not set(names) <= declared:
                raise ValueError("same-frame RGB-D/camera artifacts not declared")
            image_path, camera_path, world_path = [artifact(output, n, step) for n in names]
            image_id, camera_id, world_id = identity(image_path), identity(camera_path), identity(world_path)
            calibration = json.loads(camera_path.read_text())
            with Image.open(image_path) as image:
                size = image.size
            view = meta["per_view"][camera]
            measurement, points = view["measurement"], view["points"]
            current = bool(measurement is not None and points is not None and points["current"]
                           and measurement["source_step"] == step and points["source_step"] == step
                           and measurement["visible"] and measurement["src"] == "perception")
            source_kind = "current_visible_perception" if current else "cached_or_missing_current_measurement"
            item = {"case": record["case"], "category": registered[record["case"]]["object_category"],
                    "source_step": step, "sample_index": record["sample_index"], "view": camera,
                    "image": image_id, "camera_metadata": camera_id, "world": world_id,
                    "source_kind": source_kind, "current_measurement": measurement if current else None,
                    "original_public_missing_reason": view["missing_reason"]}
            counts[f"{camera}_{source_kind}"] += 1
            projection_entity = measurement if current else public[record["case"]]["before_cache"]
            if projection_entity is not None:
                item["projection_provenance"] = "same_frame_public_measurement" if current else "pregrasp_cache_fov_hypothesis_not_current_localization"
                item["projection_box"] = v6_som.project_bounds(projection_entity, calibration, size)
                item["fov"] = fov(projection_entity, calibration, size)
                counts[f"{source_kind}_{camera}_{item['fov']['reason']}"] += 1
            else:
                item["projection_provenance"] = "no_public_geometry_available"
            if current:
                frame_view = record["views"][camera]
                if world_id != frame_view["world"] or camera_id != frame_view["camera_metadata"]:
                    raise ValueError("registered same-frame world/camera SHA changed")
                checked(frame_view["points"])
                matches = frame_view["target_cloud_exact_mask_matches"]
                if not matches:
                    raise ValueError("current target has no previously verified exact same-frame mask association")
                mask_refs = {m["path"]: m for m in frame_view["masks"]}
                reference = mask_refs[sorted(matches)[0]]
                mask_path = checked(reference)
                mask = load(mask_path)
                if hashlib.sha256(mask.tobytes(order="C")).hexdigest() != reference["raw_array_sha256"]:
                    raise ValueError("registered SAM raw mask digest changed")
                item["mask"] = {"path": str(mask_path), "sha256": reference["sha256"],
                                "raw_array_sha256": reference["raw_array_sha256"],
                                "association": "exact_same_frame_mask_reconstructs_registered_public_target_cloud"}
                pools.setdefault((image_id["sha256"], camera), item)
            inventory.append(item)
    rng, sample = random.Random(args.seed), []
    for camera in ("agentview", "wrist"):
        pool = [v for (_, view), v in pools.items() if view == camera]
        counts[f"{camera}_unique_current_images"] = len(pool)
        sample.extend(rng.sample(pool, min(25, len(pool))))
    args.output.mkdir(parents=True, exist_ok=False)
    checks = []
    for i, item in enumerate(sample):
        entity = item["current_measurement"]
        world = load(checked(item["world"]))
        mask = load(checked(item["mask"]))
        calibration = json.loads(checked(item["camera_metadata"]).read_text())
        image_bytes = checked(item["image"]).read_bytes()
        marked, rendering = v6_som.render_marks(image_bytes, calibration, [entity], world_map=world,
                                               entity_masks={entity["id"]: mask}, visible_component_filter_v1=False)
        marks = rendering["marks"]
        box = marks[0]["box_xyxy"] if marks else None
        item = {**item, "rendering": rendering, "box": box,
                "projected_aabb_metrics": overlap(item["projection_box"], mask),
                "runtime_depth_supported_metrics": overlap(box, mask)}
        path = args.output / f"marked_{i:02d}_{item['view']}.png"
        path.write_bytes(marked)
        item["marked_image"] = identity(path)
        checks.append(item)
    def stats(rows):
        passed = sum(r["runtime_depth_supported_metrics"]["mask_iou"] >= .5 for r in rows)
        return {"images": len(rows), "mask_iou_ge_05": passed, "fraction": passed / len(rows) if rows else None,
                "mask_iou_median": float(np.median([r["runtime_depth_supported_metrics"]["mask_iou"] for r in rows])) if rows else None,
                "bbox_iou_ge_05": sum(r["runtime_depth_supported_metrics"]["bbox_iou"] >= .5 for r in rows)}
    result = stats(checks)
    result.update(version="original-public-double-view-SoM-audit/1", input_audit=identity(args.audit_report),
                  manifest=audit["manifest"], frame_evidence=audit["frame_evidence"], counts=dict(counts),
                  renderer=identity(Path(inspect.getfile(v6_som))), renderer_version=v6_som.VERSION,
                  script=identity(Path(__file__)), sample_seed=args.seed, sample_selection="25 unique image SHA per view, or all available; no private label selection",
                  per_view={view: stats([r for r in checks if r["view"] == view]) for view in ("agentview", "wrist")},
                  per_category={category: stats([r for r in checks if r["category"] == category]) for category in sorted({r["category"] for r in checks})},
                  pass_50_current_images_and_90pct=len(checks) == 50 and result["fraction"] >= .9,
                  selection_calibration_only=True, training_rows=0, qualification=False,
                  limits=["Only frypan/moka and one original scene state per arm; this is not broad LIBERO category admission.",
                          "Missing current targets are not counted as good marks. Cached geometry supplies only explicitly labeled FOV hypotheses.",
                          "SAM references are the exact recorded measured instances, not masks chosen for best IoU.",
                          "Pixel capture sim_time was not independently recorded."])
    for name, rows in (("checks.jsonl", checks), ("inventory.jsonl", inventory)):
        path = args.output / name
        path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
        result[name.removesuffix(".jsonl")] = identity(path)
    path = args.output / "report.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"report": identity(path), **stats(checks), "counts": dict(counts), "passed": result["pass_50_current_images_and_90pct"]}))


if __name__ == "__main__":
    main()
