"""Fit an observed pan outline on explicit public clouds, never simulator sizes.

These are geometric hypotheses from one original episode, not replacement
placement verdicts. Missing views and duplicate final clouds remain explicit.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measured_plane(points, tolerance_m=.002, trials=384):
    rng = np.random.default_rng(0)
    subset = points[rng.choice(len(points), min(4096, len(points)), replace=False)]
    best = None
    for _ in range(trials):
        a, b, c = subset[rng.choice(len(subset), 3, replace=False)]
        normal = np.cross(b - a, c - a)
        length = np.linalg.norm(normal)
        if length < 1e-10:
            continue
        normal /= length
        residual = np.abs(np.sum((subset - a) * normal, axis=1))
        score = int((residual <= tolerance_m).sum())
        if best is None or score > best[0]:
            best = score, a, normal
    if best is None:
        return None
    _, origin, normal = best
    inliers = np.abs(np.sum((points - origin) * normal, axis=1)) <= tolerance_m
    origin = points[inliers].mean(axis=0)
    _, _, axes = np.linalg.svd(points[inliers] - origin, full_matrices=False)
    normal = axes[-1]
    if normal[2] < 0:
        normal *= -1
    u = axes[0]
    v = np.cross(normal, u)
    residual = np.abs(np.sum((points - origin) * normal, axis=1))
    return {"origin": origin, "normal": normal, "basis": np.stack((u, v)),
        "inlier_fraction": float((residual <= tolerance_m).mean()),
        "inlier_residual_p95_m": float(np.quantile(residual[residual <= tolerance_m], .95)),
        "tolerance_m": tolerance_m}


def circle_fit(points, grid_m):
    low = points.min(axis=0)
    cells = np.floor((points - low) / grid_m).astype(int)
    shape = tuple(cells.max(axis=0) + 3)
    mask = np.zeros(shape, dtype=bool)
    mask[cells[:, 0] + 1, cells[:, 1] + 1] = True
    closed = ndimage.binary_closing(mask, iterations=2)
    labels, _ = ndimage.label(closed)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    main = labels == sizes.argmax()
    filled = ndimage.binary_fill_holes(main)
    boundary = filled & ~ndimage.binary_erosion(filled)
    edge = (np.argwhere(boundary) - 1 + .5) * grid_m + low
    if len(edge) < 3:
        return None
    rng, best = np.random.default_rng(0), None
    for _ in range(2048):
        a, b, c = edge[rng.choice(len(edge), 3, replace=False)]
        matrix = 2 * np.stack((b - a, c - a))
        if abs(np.linalg.det(matrix)) < 1e-12:
            continue
        centre = np.linalg.solve(matrix, np.array([b @ b - a @ a, c @ c - a @ a]))
        radius = np.linalg.norm(a - centre)
        if not np.all((centre >= low) & (centre <= points.max(axis=0))):
            continue
        distances = np.abs(np.linalg.norm(edge - centre, axis=1) - radius)
        inliers = distances <= 2 * grid_m
        score = int(inliers.sum())
        if best is None or score > best[0]:
            best = score, centre, radius, inliers
    if best is None:
        return None
    _, centre, radius, inliers = best
    for _ in range(2):
        rim = edge[inliers]
        design = np.column_stack((2 * rim, np.ones(len(rim))))
        values, *_ = np.linalg.lstsq(design, np.sum(rim ** 2, axis=1), rcond=None)
        centre = values[:2]
        radius = float(np.sqrt(max(values[2] + centre @ centre, 0.)))
        residual = np.abs(np.linalg.norm(edge - centre, axis=1) - radius)
        inliers = residual <= 2 * grid_m
    rim = edge[inliers]
    angles = np.sort(np.mod(np.arctan2(rim[:, 1] - centre[1], rim[:, 0] - centre[0]), 2 * np.pi))
    largest_gap = np.max(np.diff(np.r_[angles, angles[0] + 2 * np.pi]))
    radial = np.linalg.norm(points - centre, axis=1)
    return {"grid_m": grid_m, "boundary_points": len(edge), "circular_boundary_inliers": int(inliers.sum()),
        "boundary_inlier_fraction": float(inliers.mean()), "centre_uv": centre.tolist(), "radius_m": radius,
        "supported_angular_span_deg": float(360 - largest_gap * 180 / np.pi),
        "radial_residual_p95_m": float(np.quantile(residual[inliers], .95)),
        "point_fraction_within_fitted_body": float((radial <= radius + 2 * grid_m).mean()),
        "point_fraction_outside_fitted_body": float((radial > radius + 2 * grid_m).mean()),
        "boundary_extraction": "largest measured occupancy component; 2-cell closing and hole fill for diagnostic silhouette only"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    clouds, records = [], []
    for row in plan["frames"]:
        p = Path(row["inputs"]["points"]["local_path"])
        if sha(p) != row["inputs"]["points"]["sha256"]:
            raise ValueError("registered public cloud changed")
        with np.load(p) as values:
            cloud = np.asarray(values[values.files[0]], dtype=float)
        clouds.append((row, cloud))
    pre = [cloud for row, cloud in clouds if row["sample_index"] == 0]
    if len(pre) == 2:
        clouds.append(({"sample_index": 0, "camera": "same_frame_public_dual_view_union",
            "source_step": 0, "phase": "pregrasp", "src": "perception"}, np.concatenate(pre)))
    args.output.mkdir(parents=True, exist_ok=False)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(clouds), figsize=(4 * len(clouds), 4), constrained_layout=True)
    for ax, (row, raw) in zip(axes, clouds):
        points = raw[np.isfinite(raw).all(axis=1)]
        plane = measured_plane(points)
        uv = (points - plane["origin"]) @ plane["basis"].T
        fits = [circle_fit(uv, grid) for grid in (.002, .003, .004, .006)]
        fitting = [fit for fit in fits if fit is not None]
        entry = {"sample_index": row["sample_index"], "source_step": row["source_step"],
            "camera": row["camera"], "raw_points": len(raw), "finite_points": len(points),
            "world_bbox_xyz": [points.min(axis=0).tolist(), points.max(axis=0).tolist()],
            "plane": {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in plane.items()},
            "fits": fits,
            "radius_range_m": [min(f["radius_m"] for f in fitting), max(f["radius_m"] for f in fitting)]}
        for fit in fitting:
            fit["measured_world_centre"] = (plane["origin"] + np.asarray(fit["centre_uv"]) @ plane["basis"]).tolist()
        records.append(entry)
        ax.scatter(uv[::8, 0], uv[::8, 1], c=points[::8, 2], s=1, cmap="viridis")
        for fit in fitting:
            angle = np.linspace(0, 2 * np.pi, 256)
            ring = np.asarray(fit["centre_uv"]) + fit["radius_m"] * np.column_stack((np.cos(angle), np.sin(angle)))
            ax.plot(ring[:, 0], ring[:, 1], label=f"grid{fit['grid_m']*1000:g}mm", lw=.7)
        ax.set_title(f"sample{row['sample_index']} {row['camera']}", fontsize=9)
        ax.set_aspect("equal")
        ax.set_xlabel("fitted-plane U (m)")
        ax.set_ylabel("fitted-plane V (m)")
        ax.legend(fontsize=6)
    fig.savefig(args.output / "measured_body_circle_hypotheses.png", dpi=140)
    report = {"scope": "one original episode, public measured pan geometry hypothesis only",
        "manifest_sha256": sha(args.manifest), "script_sha256": sha(__file__), "records": records,
        "source_point_hash_repetition": dict(Counter(row["inputs"]["points"]["sha256"] for row in plan["frames"])),
        "private_coordinates_or_object_dimensions_used": False, "runtime_helper_created": False,
        "original_90percent_overlap_threshold_changed": False, "qualification_authorized": False,
        "new_training_rows": 0, "recommendation": "register a measured-plane circular body support-footprint hypothesis excluding measured handle extension; preserve90% coverage and all existing release/height/stability conditions; insufficient/occluded/inconsistent views must remain unknown",
        "limits": ["Plane/silhouette fit derives coordinates and radius from saved SAM RGB-D clouds only, without simulator object dimensions.",
            "Morphological contour and circular shape prior are exploratory modeling choices, not independently verified physical support geometry.",
            "One original episode and repeated final cloud cannot establish placement precision or eligibility to replace a verifier.",
            "Need raw current object clouds, target support-plane clouds, per-view masks/transforms and two stable post-release frames on original positive and negative physical branches before retaining a new verifier.",
            "Do not label unseen body/handle portions as measured or silently convert unknown to true."]}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report_sha256": sha(args.output / "report.json"), "records": [{k:r[k] for k in ["sample_index","camera","radius_range_m"]} for r in records]}))


if __name__ == "__main__":
    main()
