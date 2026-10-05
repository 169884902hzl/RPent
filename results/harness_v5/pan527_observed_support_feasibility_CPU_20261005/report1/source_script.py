"""Audit visible pan layers and explicit disk/target hypotheses on CPU only."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from robots.libero.v5_pan_surface import (
    disk_rectangle_fraction,
    maximum_disk_rectangle_fraction,
    observed_radial_layers,
)
from analyze_v5_pan526_public_body import measured_plane


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_registered(entry):
    path = Path(entry["path"])
    if sha(path) != entry["sha256"]:
        raise ValueError("registered input SHA changed")
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    source = read_registered(plan["cloud_manifest"])
    circles = read_registered(plan["circle_report"])
    boxes = read_registered(plan["public_bbox_evidence"])
    for entry in plan["matched_scene_provenance"].values():
        if sha(entry["path"]) != entry["sha256"]:
            raise ValueError("matched scene provenance SHA changed")
    known = {(r["sample_index"], r["camera"]): r for r in circles["records"]}
    initial = known[0, "agentview"]
    fused = known[0, "same_frame_public_dual_view_union"]
    cached_radius_range = [min(initial["radius_range_m"][0], fused["radius_range_m"][0]),
                           max(initial["radius_range_m"][1], fused["radius_range_m"][1])]
    profiles = []
    plot_data = []
    for row in source["frames"]:
        for item in row["inputs"].values():
            if sha(item["local_path"]) != item["sha256"]:
                raise ValueError("registered point cloud or camera SHA changed")
        with np.load(row["inputs"]["points"]["local_path"]) as values:
            points = np.asarray(values[values.files[0]], dtype=float)
        camera = json.loads(Path(row["inputs"]["camera_metadata"]["local_path"]).read_text())
        record = known[row["sample_index"], row["camera"]]
        fit = next(f for f in record["fits"] if f and f["grid_m"] == .003)
        plane = record["plane"]
        origin = np.asarray(plane["origin"])
        normal = np.asarray(plane["normal"])
        centre = np.asarray(fit["measured_world_centre"])
        profile = observed_radial_layers(points, plane_origin=origin,
            plane_normal=normal, body_centre=centre, radius_m=fit["radius_m"],
            camera_origin=np.asarray(camera["extrinsic_cam2world"])[:3, 3])
        profiles.append({"sample_index": row["sample_index"], "camera": row["camera"],
            "point_file_sha256": row["inputs"]["points"]["sha256"],
            "fit_radius_m": fit["radius_m"],
            "supported_angular_span_deg": fit["supported_angular_span_deg"],
            "measured_centre": centre.tolist(), "profile": profile})
        radial = np.linalg.norm((points - centre)
            - np.outer((points - centre) @ normal, normal), axis=1)
        plot_data.append((row, radial, (points - origin) @ normal))
    comparisons = []
    for case in boxes["cases"]:
        options = [("cached", case["target_cached"]),
                   *[("current:" + t["name"], t) for t in case["target_current"]]]
        for kind, target in options:
            comparisons.append({"case": case["name"], "target_kind": kind,
                "target_src": target["src"], "target_source_step": target["source_step"],
                "target_visible": target["visible"],
                "target_xy_size_m": [target["upper"][i] - target["lower"][i] for i in (0, 1)],
                "object_centre_proxy": case["object"]["xyz"][:2],
                "best_centred_horizontal_disk_fraction": [maximum_disk_rectangle_fraction(
                    radius, target["lower"][:2], target["upper"][:2]) for radius in cached_radius_range],
                "disk_fraction_at_visible_median_proxy": [disk_rectangle_fraction(
                    case["object"]["xyz"][:2], radius, target["lower"][:2], target["upper"][:2])
                    for radius in cached_radius_range],
                "support_verdict": None,
                "matched_pan526_scene": case.get("matched_pan526_scene", False),
                "hypothesis_only": "cached observed rim radius and horizontal disk/visible-median centre; not a measured bottom footprint; radius transfer is cross-scene unless matched_pan526_scene=true"})
    target_profiles = []
    for row in plan["matched_target_clouds"]:
        if sha(row["path"]) != row["sha256"]:
            raise ValueError("matched target cloud SHA changed")
        with np.load(row["path"]) as values:
            cloud = np.asarray(values[values.files[0]], dtype=float)
        cloud = cloud[np.isfinite(cloud).all(axis=1)]
        plane = measured_plane(cloud)
        inliers = np.abs((cloud - plane["origin"]) @ plane["normal"]) <= plane["tolerance_m"]
        target_profiles.append({"sample_index": row["sample_index"], "points": len(cloud),
            "raw_bounds": [cloud.min(axis=0).tolist(), cloud.max(axis=0).tolist()],
            "observed_bbox_quantiles02_98": np.quantile(cloud, (.02, .98), axis=0).tolist(),
            "dominant_visible_plane": {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in plane.items()},
            "dominant_plane_observed_bounds": [cloud[inliers].min(axis=0).tolist(), cloud[inliers].max(axis=0).tolist()],
            "observed_points_above_plane_1cm": int((((cloud - plane["origin"]) @ plane["normal"]) > .01).sum()),
            "support_polygon": None,
            "reason": "visible-plane bounds do not fill occluded target support"})
    args.output.mkdir(parents=True, exist_ok=False)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(plot_data), figsize=(4 * len(plot_data), 4), constrained_layout=True)
    for ax, (row, radial, height) in zip(axes, plot_data):
        ax.scatter(radial[::8] * 100, height[::8] * 100, s=1, alpha=.3)
        ax.axhline(0, color="black", lw=.5)
        ax.axvspan(cached_radius_range[0] * 100, cached_radius_range[1] * 100, color="red", alpha=.2)
        ax.set_title(f"sample{row['sample_index']} {row['camera']}")
        ax.set_xlabel("measured radial distance (cm)")
        ax.set_ylabel("height relative to fitted visible plane (cm)")
    fig.savefig(args.output / "visible_radial_layers.png", dpi=140)
    report = {"version": "pan527-public-support-feasibility/1",
        "scope": "CPU public geometry hypotheses; no runtime verdict or threshold change",
        "manifest_sha256": sha(args.manifest), "script_sha256": sha(__file__),
        "helper_sha256": sha(Path(__file__).resolve().parents[1] / "robots/libero/v5_pan_surface.py"),
        "inputs": plan, "cached_rim_radius_range_m": cached_radius_range,
        "profiles": profiles, "target_hypothesis_comparisons": comparisons,
        "matched_target_profiles": target_profiles,
        "duplicate_final_cloud": profiles[-1]["point_file_sha256"] == profiles[-2]["point_file_sha256"],
        "existing_90percent_threshold_unchanged": True, "runtime_changed": False,
        "old_verdicts_changed": False, "support_footprint_observed": False,
        "private_coordinates_used_for_geometry": False, "qualification_authorized": False,
        "limits": ["Upper-facing visible floor/rim is not an observed underside contact band.",
            "Matched original-scene target raw clouds exist only at sample0 and6, not5 or7; sample6 cannot replace a missing sample7 target measurement.",
            "place525 bbox cases s4/s8/s12 differ from the pan526 cached-circle scene s0; those radius-transfer comparisons are hypotheses only.",
            "Visible medians are biased by masking and occlusion; they are not fitted pan-body centres for the three bbox cases.",
            "Current target bounding-box expansion cannot be chosen to obtain a passing result without mask/surface identity evidence.",
            "Final sample6/7 identical point clouds cannot independently establish stability.",
            "Low measured points may be the inner floor, a side contour or segmentation contamination; none completes an unseen bottom."]}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report_sha256": sha(args.output / "report.json"),
        "profiles": [{"sample_index": p["sample_index"], "camera": p["camera"],
            "camera_signed_plane_distance_m": p["profile"]["camera_signed_plane_distance_m"],
            "low_band_radial_quantiles_m": p["profile"]["observed_low_band"]["radial_quantiles_m"]}
            for p in profiles], "comparisons": comparisons}))


if __name__ == "__main__":
    main()
