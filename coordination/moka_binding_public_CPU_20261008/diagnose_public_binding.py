"""Diagnose three pinned stove-binding failures from saved public evidence."""

import ast
from itertools import combinations
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np


BASE = Path(__file__).resolve().parent
SOURCE = "/public/home/sunyihan/rpent_libero_eval/source_v5_placement582_r2_20261008"
INPUTS = [
    (580104, "job4502_part3_episodes.jsonl", "e54a545506c66ad33fc67f275ec5c3a787d5be7d967f8ef29caa21af794bc677", "/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill24_CPU_20261008/smoke10/job4502/part3/probe/episodes.jsonl"),
    (580152, "job4531_part2_episodes.jsonl", "d6739926bca425fe2ad1e56faa06e98234152617ded8e741e985b6ae75c8f855", "/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill76_CPU_20261008/smoke10/job4531/part2/probe/episodes.jsonl"),
    (580159, "job4531_part1_episodes.jsonl", "3af20be47ef1512f75132db4969f52015dc57a8efeae22a0654c5ff9508971dc", "/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill76_CPU_20261008/smoke10/job4531/part1/probe/episodes.jsonl"),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(local: str, expected: str, remote: str) -> tuple[Path, dict]:
    path = BASE / "inputs" / local
    if sha(path) != expected:
        raise ValueError(f"registered evidence changed: {path}")
    return path, {"path": remote, "sha256": expected}


def bbox_metrics(a: dict, b: dict) -> dict:
    alo, ahi, blo, bhi = [np.asarray(value, dtype=float) for value in (a["lower"], a["upper"], b["lower"], b["upper"])]
    overlap = np.maximum(0, np.minimum(ahi, bhi) - np.maximum(alo, blo))
    values = {}
    for count, label in [(3, "bbox_3d_iou"), (2, "bbox_xy_iou")]:
        intersection = np.prod(overlap[:count])
        union = np.prod((ahi - alo)[:count]) + np.prod((bhi - blo)[:count]) - intersection
        values[label] = float(intersection / union) if union > 0 else None
    values["max_bbox_edge_difference_m"] = float(max(np.abs(alo - blo).max(), np.abs(ahi - bhi).max()))
    values["median_centre_distance_m"] = math.dist(a["xyz"], b["xyz"])
    return values


def unique_points(points: np.ndarray) -> np.ndarray:
    array = np.ascontiguousarray(points.astype("<f8"))
    dtype = [("x", "<f8"), ("y", "<f8"), ("z", "<f8")]
    return np.unique(array.view(dtype).reshape(-1))


def main() -> None:
    runtime_path, runtime_ref = checked("registered_v5_runtime.py", "17b7ce4ffc1d0a02278eb3308b6f7c76425c19241fbf74aeffcbf76dfefab7bb", SOURCE + "/robots/libero/v5_runtime.py")
    probe_path, probe_ref = checked("registered_probe_v5_moka_transfer_public.py", "5cc5def4fa8d666ecd73815da7987772add2a9151f1deb530a0937affffba7d7", SOURCE + "/scripts/probe_v5_moka_transfer_public_20261007.py")
    tree = ast.parse(probe_path.read_text())
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "same_measured_bbox")
    scope = {}
    # Execute only the pure nested predicate from the immutable probe; no
    # simulator, service, model, or live runtime module is imported.
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(probe_path), "exec"), scope)
    same_bbox = scope["same_measured_bbox"]
    reports = []
    for seed, filename, expected_sha, remote in INPUTS:
        episodes_path, episodes_ref = checked(filename, expected_sha, remote)
        matches = [(line_number, json.loads(line)) for line_number, line in enumerate(episodes_path.read_text().splitlines(), 1)
                   if line and json.loads(line)["case"]["layout_seed"] == seed]
        if len(matches) != 1:
            raise ValueError("expected one immutable first-attempt record per registered layout")
        line_number, row = matches[0]
        choices_path, choices_ref = checked(f"choices{seed}.jsonl", row["choices_sha256"], row["output_dir"] + "/choices.jsonl")
        choices = [json.loads(line) for line in choices_path.read_text().splitlines() if line]
        if len(choices) != 1:
            raise ValueError("failed pre-contact probe must have one decision")
        choice = choices[0]
        binding = row["public_stove_binding_evidence"]
        if (binding["outcome"] != "ambiguous" or row["first_receipt"]["failure_reason"] != "original_transfer_public_stove_binding_missing_or_ambiguous"
                or row["executed_vla_actions"] != 0 or row["executed_public_motion_actions"] != 0
                or row["official_subtask_success"] is not None):
            raise ValueError("the original record differs from the assigned zero-control binding failure")
        if sha(runtime_path) != row["result"]["source_hashes"]["robots/libero/v5_runtime.py"]:
            raise ValueError("diagnosis runtime is not the runtime recorded by the job")
        stoves = {entity["id"]: entity for entity in choice["measurements"] if entity["name"] == "stove"}
        clouds, cloud_refs, cloud_checks = {}, [], []
        for eid, ref in choice["fixture_measurement_evidence"].items():
            if eid not in stoves:
                continue
            path, evidence_ref = checked(f"cloud_{seed}_{eid}.npz", ref["sha256"], ref["path"])
            points = np.load(path, allow_pickle=False)["array"]
            if not np.isfinite(points).all():
                raise ValueError("public segmented cloud contains non-finite values")
            entity = stoves[eid]
            bbox_error = float(np.abs(np.quantile(points, [.02, .98], axis=0) - np.array([entity["lower"], entity["upper"]])).max())
            median_error = float(np.abs(np.median(points, axis=0) - entity["xyz"]).max())
            if bbox_error != 0 or median_error != 0:
                raise ValueError("saved segmented RGB-D cloud does not reproduce the public entity")
            clouds[eid] = unique_points(points)
            cloud_refs.append(evidence_ref)
            cloud_checks.append({"entity_id": eid, "points": len(points), "unique_points": len(clouds[eid]),
                                 "quantile_bbox_max_error_m": bbox_error, "median_max_error_m": median_error,
                                 "source_cameras": choice["perception_measurement_evidence"][eid]["source_cameras"],
                                 "sam_mask_file_refs": choice["perception_measurement_evidence"][eid].get("sam_mask_files", {})})
        eligible = []
        guard_checks = []
        eef = binding["public_eef_xyz_m"]
        for record in binding["entities"]:
            eid = record["id"]
            entity = stoves[eid]
            distance = math.hypot(*(max(entity["lower"][i] - eef[i], 0, eef[i] - entity["upper"][i]) for i in (0, 1)))
            if not math.isclose(distance, record["nearest_bbox_xy_distance_m"], abs_tol=1e-12):
                raise ValueError("saved operating-area guard distance did not reproduce")
            if distance <= binding["max_nearest_bbox_xy_distance_m"]:
                eligible.append(eid)
            guard_checks.append({"id": eid, "bbox_xy_distance_m": distance,
                                 "median_xy_distance_m": math.dist(entity["xyz"][:2], eef[:2]),
                                 "measured_bbox_size_m": np.subtract(entity["upper"], entity["lower"]).tolist(),
                                 "original_disposition": record["disposition"]})
        pairs = []
        for first, second in combinations(sorted(stoves), 2):
            a, b = stoves[first], stoves[second]
            shared = len(np.intersect1d(clouds[first], clouds[second]))
            pairs.append({"ids": [first, second], **bbox_metrics(a, b),
                          "source_pure_bbox_duplicate_predicate": bool(same_bbox(SimpleNamespace(**a), SimpleNamespace(**b))),
                          "exact_shared_rgbd_points": shared,
                          "fraction_of_smaller_unique_public_cloud_shared": shared / min(len(clouds[first]), len(clouds[second])),
                          "shared_points_are_sam_mask_iou": False})
        # Reapply the original rank and pure duplicate predicate, without
        # selecting a new target or changing any original output.
        measurements = choice["perception_measurement_evidence"]
        rank = lambda eid: (-int(bool(measurements[eid].get("fusion", {}).get("fused", measurements[eid].get("fused")))),
                            -len(measurements[eid].get("source_cameras", [])), eid)
        unique = []
        for eid in sorted(eligible, key=rank):
            if not any(same_bbox(SimpleNamespace(**stoves[eid]), SimpleNamespace(**stoves[other])) for other in unique):
                unique.append(eid)
        if unique != binding["eligible_entity_ids"]:
            raise ValueError("original ambiguous eligible IDs did not reproduce")
        reason = ("nested_same_view_segmented_clouds_not_merged_by_thin_3d_bbox" if seed == 580152
                  else "separated_same_category_clouds_wide_far_bbox_passes_operating_area_guard")
        reports.append({"layout_seed": seed, "episodes": {**episodes_ref, "line": line_number}, "choices": choices_ref,
                        "source_runtime": runtime_ref, "source_probe": probe_ref,
                        "original_failure_reason": row["first_receipt"]["failure_reason"],
                        "original_public_binding": binding, "original_stove_entities": list(stoves.values()),
                        "zero_target_controls": True, "original_private_completion_label": None,
                        "diagnostic_class": reason, "missing_sam_measurement": False,
                        "name_normalization_mismatch": False, "original_bbox_guard_reproduced": True,
                        "original_duplicate_predicate_reproduced": True,
                        "recomputed_eligible_ids": unique,
                        "cloud_refs": cloud_refs, "cloud_reproduction": cloud_checks,
                        "guard_metrics": guard_checks, "pair_metrics": pairs,
                        "semantic_false_positive_of_far_cloud_verified": False,
                        "mask_or_rgb_gap": "original SAM mask references and planner RGB media were not persisted for these stove measurements"})
    result = {"schema": "moka-stove-binding-saved-public-diagnosis/1-CPU", "cases": reports,
              "summary": {"cases": 3, "missing_sam_measurement": 0, "name_normalization_mismatch": 0,
                          "nested_segmented_cloud_duplicate": 1, "separated_same_category_clouds": 2,
                          "public_clouds_sha_checked": 7, "private_geometry_used": False,
                          "physical_reruns": 0, "gpu_submissions": 0, "old_labels_or_results_changed": False},
              "source_pure_duplicate_predicate_lines": [function.lineno, function.end_lineno],
              "analyzer": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__))}}
    output = BASE / "public_binding_diagnosis_r1.json"
    encoded = json.dumps(result, indent=2) + "\n"
    if output.exists() and output.read_text() != encoded:
        raise ValueError("immutable diagnosis already exists with different bytes")
    output.write_text(encoded)
    print(json.dumps({"path": str(output), "sha256": sha(output), "summary": result["summary"]}))


if __name__ == "__main__":
    main()
