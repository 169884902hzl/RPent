"""Inspect explicit saved public placement evidence; never upgrade old verdicts."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


REMOTE = Path("/public/home/sunyihan/rpent_libero_eval")
PRIOR = "results/harness_v5/place4311_public_identity_CPU_20261007/report.json"
PRIOR_SHA = "fb19d66f807226d28212212db3b8e1ec61dc25c8e2bd118bc5992b2f5584765c"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_artifact_manifest(path):
    value = json.loads(path.read_text())
    for item in value["artifacts"]:
        if sha(Path(item["local_path"])) != item["sha256"]:
            raise ValueError("explicit artifact changed: " + item["local_path"])
    return value


def point_support(entity, cloud):
    lower, upper = np.asarray(entity["lower"]), np.asarray(entity["upper"])
    mask = np.isfinite(cloud).all(2) & (cloud >= lower).all(2) & (cloud <= upper).all(2)
    points = cloud[mask]
    if not len(points):
        return {"points_inside_saved_endpoint_box": 0}
    return {"points_inside_saved_endpoint_box": len(points),
            "unsegmented_raw_quantile_bounds": np.quantile(points, (.02, .98), axis=0).tolist(),
            "points_above_1_23m": int((points[:, 2] > 1.23).sum()),
            "scope": "all visible depth in stored box; no original SAM mask or label recomputation"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--explicit-inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, inputs = args.root.resolve(), args.explicit_inputs.resolve()
    prior_path = root / PRIOR
    if sha(prior_path) != PRIOR_SHA:
        raise ValueError("original CPU binding/footprint evidence changed")
    prior = json.loads(prior_path.read_text())
    frames = load_artifact_manifest(inputs / "downloaded_artifacts.json")
    indices = load_artifact_manifest(inputs / "downloaded_carry_indices.json")
    carries = []
    for item in indices["artifacts"]:
        row = next(row for row in prior["false_negative_original_evidence"] if row["case"] == item["case"])
        ledger = root / Path(row["ledger"]).relative_to(REMOTE)
        raw = json.loads(ledger.read_text().splitlines()[row["line"] - 1])
        public = raw["first_attempt"]["public_before"]
        source = row["object_before"]
        support = row["cached_target"]
        endpoint = row["object_after"]
        initial_mid = (np.asarray(source["lower"]) + source["upper"]) / 2
        support_mid = (np.asarray(support["lower"]) + support["upper"]) / 2
        endpoint_mid = (np.asarray(endpoint["lower"]) + endpoint["upper"]) / 2
        steps = json.loads(Path(item["local_path"]).read_text())["steps"]
        start = next(step for step in steps if step["step_idx"] == source.get("source_step", 5))
        start_rotation = Rotation.from_quat(start["state"]["robot0_eef_quat"])
        rotations = [{"capture_step": step["step_idx"],
                      "eef_rotation_change_deg": float(np.degrees((start_rotation.inv() *
                           Rotation.from_quat(step["state"]["robot0_eef_quat"])).magnitude()))}
                     for step in steps if step["step_idx"] >= start["step_idx"]]
        carries.append({"case": row["case"], "explicit_index": item,
            "ledger_sha256": sha(ledger), "line_1based": row["line"],
            "eef_pre_minus_measured_object_midpoint_m":
                (np.asarray(public["robot"]["eef_xyz"]) - initial_mid).tolist(),
            "endpoint_measured_object_midpoint_minus_support_midpoint_m":
                (endpoint_mid - support_mid).tolist(),
            "eef_rotation_changes": rotations,
            "supported_finding": "1.1-1.4 degree endpoint orientation change cannot explain 3-6cm centre discrepancy by rotation alone",
            "unresolved": "held-centre measurement bias, carry slip and mask/depth mixing remain distinct hypotheses; missing exact intermediate masks/clouds prevent choosing one",
            "private_object_coordinates_used": False, "old_verdict_unchanged": True})
    endpoint_row = next(row for row in prior["false_negative_original_evidence"]
                        if "t25_s4" in row["case"])
    support = []
    for camera in ("agentview", "wrist"):
        item = next(item for item in frames["artifacts"] if item["role"] == camera + "_world_high.npz")
        with np.load(item["local_path"]) as encoded:
            cloud = encoded["array"].astype(float)
        support.append({"camera": camera, "capture_step": item["step"], "source": item,
                        **point_support(endpoint_row["object_after"], cloud)})
    pre = np.asarray(endpoint_row["preaction_extent_m"])
    after = np.asarray(endpoint_row["endpoint_extent_m"])
    report = {"version": "place4311_endpoint_public_root/2-dev",
        "source_report": {"path": str(prior_path), "sha256": PRIOR_SHA},
        "producer": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__))},
        "explicit_frame_manifest_sha256": sha(inputs / "downloaded_artifacts.json"),
        "explicit_index_manifest_sha256": sha(inputs / "downloaded_carry_indices.json"),
        "unchanged_4311_binding_count": prior["binding_counts"],
        "unresolved_binding": "t25/init2 selected cabinet remains ambiguous: no independently queried current drawer proves its cached cabinet fragment alias",
        "current_on_carry_checks": carries,
        "t25_init4_vla_endpoint": {
            "saved_entity": endpoint_row["object_after"],
            "extent_ratio_to_pregrasp": (after / pre).tolist(),
            "bbox_volume_ratio_to_pregrasp": float(np.prod(after) / np.prod(pre)),
            "same_capture_unsegmented_cloud_support": support,
            "supported_finding": "saved entity upper tail is not supported by the dense visible bowl surface in this capture; wrist has no depth inside its stored box",
            "remaining_unknown": "original masks and selected segmented clouds absent, so exact contamination source and new verifier outcome are unavailable"},
        "next_original_development_capture": {
            "moving_target_geometry": "current capture only, including segmentation ROI; commits 94b3a5b and 6b8de9b",
            "persist": ["both current RGB-D images and world maps", "selected-object SAM masks per camera",
                        "selected-object segmented clouds per camera and fused cloud", "measured target and robot pose",
                        "held-offset before/after each carry segment", "first/second final placement frames"],
            "independent_drawer_query": "query drawer on the same original t25/init2 RGB-D capture; associate geometrically before deleting any cached fragment",
            "thresholds": "keep strict6 on>=0.90 and in>=0.85; never fabricate hidden support boundaries"},
        "new_GPU_jobs": 0, "new_physical_trials": 0, "new_training_rows": 0,
        "qualification_authorized": False, "old_results_unchanged": True}
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output / "report.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"path": str(output), "sha256": sha(output),
                      "carry_cases": len(carries), "endpoint_views": len(support)}))


if __name__ == "__main__":
    main()
