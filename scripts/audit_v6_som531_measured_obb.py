"""Finite CPU feasibility of public 3D OBB/component marks on fixed 50 frames.

Fit only registered same-frame measured 3D points. The original SAM mask is
loaded afterward for scoring, never for tightening pixel boxes. All points,
including the handle and separate observed components, remain in the fit.
"""

import argparse
from collections import Counter
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import ConvexHull


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(desc):
    path = Path(desc["path"])
    if identity(path)["sha256"] != desc["sha256"]:
        raise ValueError("registered public input SHA changed: " + str(path))
    return path


def load(path):
    with np.load(path, allow_pickle=False) as data:
        return data["array"]


def fit_obb(points):
    centre = points.mean(axis=0)
    _, _, rotation = np.linalg.svd(points - centre, full_matrices=False)
    local = (points - centre) @ rotation.T
    # Existing public visible-depth support uses 2 mm for measurement roundoff.
    lower, upper = local.min(axis=0) - .002, local.max(axis=0) + .002
    corners = np.array(list(itertools.product(*zip(lower, upper)))) @ rotation + centre
    return {"origin_m": centre.tolist(), "axes": rotation.tolist(),
            "lower_local_m": lower.tolist(), "upper_local_m": upper.tolist(),
            "corners_m": corners.tolist(), "points": len(points),
            "all_observed_points_enclosed": bool(((local >= lower) & (local <= upper)).all()),
            "padding_m": .002, "point_trimming": False}


def project_obb(obb, metadata, size):
    corners = np.asarray(obb["corners_m"])
    camera = (np.column_stack([corners, np.ones(8)]) @ np.linalg.inv(metadata["extrinsic_cam2world"]).T)[:, :3]
    points = [p for p in camera if p[2] >= 1e-5]
    for i, j in itertools.combinations(range(8), 2):
        # The original Cartesian product index identifies the 12 OBB edges.
        if (i ^ j) not in (1, 2, 4):
            continue
        a, b = camera[i], camera[j]
        if (a[2] < 1e-5) != (b[2] < 1e-5):
            points.append(a + (b - a) * ((1e-5 - a[2]) / (b[2] - a[2])))
    if len(points) < 3:
        return None
    intrinsic = np.asarray(metadata["intrinsic_K"], float).copy()
    intrinsic[0] *= size[0] / metadata["width"]
    intrinsic[1] *= size[1] / metadata["height"]
    projected = np.asarray(points) @ intrinsic.T
    pixels = projected[:, :2] / projected[:, 2:3]
    return pixels[ConvexHull(pixels).vertices].tolist()


def clip_polygon(vertices, width, height):
    if vertices is None:
        return []
    result = vertices
    for axis, boundary, keep_low in ((0, 0., False), (0, float(width), True),
                                     (1, 0., False), (1, float(height), True)):
        incoming, result = result, []
        if not incoming:
            break
        for a, b in zip(incoming, incoming[1:] + incoming[:1]):
            a, b = np.asarray(a), np.asarray(b)
            inside_a = a[axis] <= boundary if keep_low else a[axis] >= boundary
            inside_b = b[axis] <= boundary if keep_low else b[axis] >= boundary
            if inside_a:
                result.append(a.tolist())
            if inside_a != inside_b:
                result.append((a + (b - a) * ((boundary - a[axis]) / (b[axis] - a[axis]))).tolist())
    return result


def rasterize(polygons, size, rectangles):
    image = Image.new("1", size)
    draw = ImageDraw.Draw(image)
    for vertices in polygons:
        clipped = clip_polygon(vertices, *size)
        if len(clipped) < 3:
            continue
        if rectangles:
            points = np.asarray(clipped)
            lo, hi = points.min(axis=0), points.max(axis=0)
            draw.rectangle([int(np.floor(lo[0])), int(np.floor(lo[1])), int(np.ceil(hi[0])) - 1, int(np.ceil(hi[1])) - 1], fill=1)
        else:
            draw.polygon([tuple(p) for p in clipped], fill=1)
    return np.asarray(image, bool)


def score(mark, reference):
    common, union = int((mark & reference).sum()), int((mark | reference).sum())
    return {"mask_iou": common / max(1, union), "mask_coverage": common / max(1, int(reference.sum())),
            "mark_pixels": int(mark.sum()), "reference_pixels": int(reference.sum()), "intersection_pixels": common}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--geometry-helper", type=Path, required=True)
    parser.add_argument("--geometry-helper-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if identity(args.report)["sha256"] != args.report_sha256 or identity(args.geometry_helper)["sha256"] != args.geometry_helper_sha256:
        raise ValueError("registered CPU inputs changed")
    source = json.loads(args.report.read_text())
    checks = [json.loads(line) for line in checked(source["checks"]).read_text().splitlines()]
    original_audit = json.loads(checked(source["input_audit"]).read_text())
    frames = {(r["case"], r["sample_index"]): r for r in (
        json.loads(line) for line in checked(original_audit["frame_evidence"]).read_text().splitlines())}
    spec = importlib.util.spec_from_file_location("registered_pan526_geometry", args.geometry_helper)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for index, item in enumerate(checks):
        descriptor = frames[item["case"], item["sample_index"]]["views"][item["view"]]["points"]
        cloud = np.asarray(load(checked(descriptor)), float)
        if not np.isfinite(cloud).all() or cloud.ndim != 2 or cloud.shape[1:] != (3,):
            raise ValueError("only the complete registered finite public cloud is accepted")
        metadata = json.loads(checked(item["camera_metadata"]).read_text())
        with Image.open(checked(item["image"])) as image:
            size = image.size
        global_obb = fit_obb(cloud)
        components, circle = [global_obb], None
        if item["category"] == "frypan":
            plane = helper.measured_plane(cloud)
            if plane is not None:
                uv = (cloud - plane["origin"]) @ plane["basis"].T
                circle = helper.circle_fit(uv, .003)
                if circle is not None:
                    radial = np.linalg.norm(uv - circle["centre_uv"], axis=1)
                    body = radial <= circle["radius_m"] + .006
                    # The circle merely partitions observations. Every point
                    # outside it is retained, never silently deleted as noise.
                    if body.sum() >= 10 and (~body).sum() >= 10:
                        components = [fit_obb(cloud[body]), fit_obb(cloud[~body])]
                        components[0]["hypothesis"] = "measured_circular_body_partition"
                        components[1]["hypothesis"] = "all_remaining_observed_geometry_including_handle"
        polygons = [project_obb(global_obb, metadata, size)]
        parts = [project_obb(component, metadata, size) for component in components]
        geometry = {"single_OBB_rectangle": (polygons, True), "single_OBB_projected_volume": (polygons, False),
                    "body_handle_rectangles_union": (parts, True), "body_handle_projected_volumes_union": (parts, False)}
        # Fitting above never reads the original 2D mask. Scoring starts here.
        reference = load(checked(item["mask"]))
        scores = {name: score(rasterize(vertices, size, rectangles), reference) for name, (vertices, rectangles) in geometry.items()}
        record = {"case": item["case"], "view": item["view"], "source_step": item["source_step"],
                  "entity_id": item["current_measurement"]["id"], "category": item["category"], "cloud": descriptor,
                  "same_frame_source": "perception", "global_OBB": global_obb, "components": components,
                  "body_circle_fit": circle, "scores": scores,
                  "baseline": item["runtime_depth_supported_metrics"], "all_observed_points_retained": sum(c["points"] for c in components) == len(cloud),
                  "geometry_complete_before_original_mask_loaded": True, "runtime_or_training_row_written": False}
        records.append(record)
        with (args.output / "cases.jsonl").open("a") as log:
            log.write(json.dumps(record) + "\n")
    names = list(records[0]["scores"])
    def stats(rows, name):
        return {"images": len(rows), "mask_iou_ge_05": sum(r["scores"][name]["mask_iou"] >= .5 for r in rows),
                "fraction": sum(r["scores"][name]["mask_iou"] >= .5 for r in rows) / len(rows),
                "mask_coverage_min": min(r["scores"][name]["mask_coverage"] for r in rows),
                "mask_coverage_median": float(np.median([r["scores"][name]["mask_coverage"] for r in rows])),
                "same_numeric_50_image_90pct_gate": len(rows) == 50 and sum(r["scores"][name]["mask_iou"] >= .5 for r in rows) >= 45}
    result = {"version": "public-3D-SoM-feasibility/1", "source_report": identity(args.report), "geometry_helper": identity(args.geometry_helper),
              "script": identity(Path(__file__)), "cases": identity(args.output / "cases.jsonl"),
              "methods": {name: stats(records, name) for name in names},
              "by_view": {view: {name: stats([r for r in records if r["view"] == view], name) for name in names} for view in ("agentview", "wrist")},
              "category_id_unchanged": True, "all_points_retained": all(r["all_observed_points_retained"] for r in records),
              "shared_renderer_changed": False, "GPU_jobs": 0, "training_rows": 0, "qualification": False,
              "limits": ["Fixed same 50 correlated original frames, not a new independent validation batch.",
                         "Circle fit partitions public observations; no simulator dimensions, contact footprint or hidden surface is asserted.",
                         "Every remaining point including handle/fragments is enclosed; the original full SAM mask is scored without trimming.",
                         "Projected OBB polygons and multiple rectangles need shared training/runtime implementation before admission; this is CPU feasibility only.",
                         "Mask coverage includes pixels without usable measured depth; those are never invented as 3D measurements."]}
    path = args.output / "report.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"report": identity(path), "methods": result["methods"], "all_points_retained": result["all_points_retained"]}))


if __name__ == "__main__":
    main()
