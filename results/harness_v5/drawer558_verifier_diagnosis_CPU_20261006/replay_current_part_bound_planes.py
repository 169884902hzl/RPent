"""CPU hypothesis: bind moving depth to the current measured drawer AABB."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

from analyze_public_drawer_planes import checked, entity, identity


def bound_moving_plane(world, parent, anchored_part, current_part, front, vertical_face):
    empty = np.empty((0, 3))
    if current_part is None or not current_part["visible"]:
        return None, {"reason": "current_drawer_identity_not_measured"}, empty
    points = np.asarray(world, dtype=float).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
    front = np.asarray(front, dtype=float)[:2]
    tangent = np.array((-front[1], front[0]))
    lower, upper = np.asarray(parent["lower"]), np.asarray(parent["upper"])
    corners = np.array([(x, y) for x in (lower[0], upper[0]) for y in (lower[1], upper[1])])
    side_lo, side_hi = np.min(corners @ tangent), np.max(corners @ tangent)
    edge = np.max(corners @ front)
    border_width = min(.025, (side_hi - side_lo) * .12)
    depth, side = points[:, :2] @ front, points[:, :2] @ tangent
    anchored_gate = ((side >= side_lo + border_width) & (side <= side_hi - border_width)
                    & (points[:, 2] >= anchored_part["lower"][2] + .005)
                    & (points[:, 2] <= anchored_part["upper"][2] - .005)
                    & (depth >= edge - .03) & (depth <= edge + .35))
    current_lo = np.asarray(current_part["lower"]) - .005
    current_hi = np.asarray(current_part["upper"]) + .005
    current_gate = ((points >= current_lo) & (points <= current_hi)).all(axis=1)
    moving = points[anchored_gate & current_gate]
    projection = moving[:, :2] @ front
    histogram, edges = np.histogram(projection, bins=np.arange(edge - .031, edge + .356, .004))
    best, best_cloud, rows = None, empty, []
    for index in np.argsort(histogram)[-5:]:
        if histogram[index] < 30:
            continue
        centre = (edges[index] + edges[index + 1]) / 2
        selected = moving[np.abs(projection - centre) <= .004]
        fit = vertical_face(selected)
        accepted = fit is not None and abs(np.asarray(fit["normal_xy"]) @ front) >= .95
        rows.append({"bin_centre_m": float(centre), "bin_points": int(histogram[index]),
                     "selected_points": len(selected), "accepted": bool(accepted), "fit": fit})
        if accepted and (best is None or len(selected) > len(best_cloud)):
            best, best_cloud = fit, selected
    evidence = {"current_part_id": current_part["id"], "current_part_source_step": current_part["source_step"],
                "margin_m": .005, "current_part_window_lower_m": current_lo.tolist(),
                "current_part_window_upper_m": current_hi.tolist(), "candidate_planes": rows,
                "old_anchor_gate_points": int(anchored_gate.sum()), "current_bound_gate_points": len(moving),
                "selected_points": len(best_cloud), "chosen_by": "largest supported valid plane after identity window",
                "private_coordinates_or_outcomes_used": False}
    return best, evidence, best_cloud


def fuse_views(original_fused, views, bound_fused):
    sample = deepcopy(original_fused)
    sample["moving"] = bound_fused
    sample["views"] = views
    disagreements = {}
    for kind in ("frame", "moving"):
        first, second = views["agentview"].get(kind), views["wrist"].get(kind)
        if first and second:
            normal = np.asarray(first["normal_xy"])
            distance = abs(float((np.asarray(first["centre"])[:2] - np.asarray(second["centre"])[:2]) @ normal))
            cosine = abs(float(normal @ second["normal_xy"]))
            if distance > .015 or cosine < .95:
                sample[kind] = None
                disagreements[kind] = {"normal_distance_m": distance, "normal_cosine": cosine}
    if disagreements:
        sample.update(reason="drawer_views_disagree", view_disagreements=disagreements)
    return sample


def main():
    manifest_path, output = map(Path, sys.argv[1:])
    plan = json.loads(manifest_path.read_text())
    if identity(manifest_path)["sha256"] != "bbe19b3087d0e1915a154042387f5eff9ef1965fdb8646de91a14d0f1a7e8640":
        raise ValueError("registered public inputs changed")
    for ref in plan["source_files"]: checked(ref)
    from robots.libero.v5_fixture_parts import measured_drawer_faces
    from robots.libero.v5_state import Entity
    from robots.libero.v5_verification import measured_fixture_endpoint, vertical_face
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for case in plan["cases"]:
        parent, part = entity(case["anchor_parent"], Entity), entity(case["anchor_part"], Entity)
        row = {"case": case["case"], "original_public_verdict": case["recorded_public_verdict"],
               "original_extension_cm": case["recorded_extension_cm"], "phases": {}}
        for phase, inputs in case["frames"].items():
            worlds, views, binding = {}, {}, {}
            for camera, refs in inputs.items():
                for ref in refs.values(): checked(ref)
                with np.load(refs["world"]["path"], allow_pickle=False) as archive: worlds[camera] = archive["array"]
                original, _ = measured_drawer_faces(worlds[camera], parent, part, case["front_axis"])
                moving, evidence, _ = bound_moving_plane(worlds[camera], case["anchor_parent"], case["anchor_part"],
                    case["public_part"][phase], case["front_axis"], vertical_face)
                views[camera] = {**original, "moving": moving, "source_step": case["recorded_endpoint"][phase]["source_step"]}
                binding[camera] = evidence
            joined = np.concatenate([world.reshape(-1, 3) for world in worlds.values()])
            original_fused, _ = measured_drawer_faces(joined, parent, part, case["front_axis"])
            moving, evidence, _ = bound_moving_plane(joined, case["anchor_parent"], case["anchor_part"],
                case["public_part"][phase], case["front_axis"], vertical_face)
            fused = fuse_views(original_fused, views, moving)
            fused["source_step"] = case["recorded_endpoint"][phase]["source_step"]
            row["phases"][phase] = {"views": views, "fused": fused, "binding": {**binding, "fused": evidence}}
        outcomes = {}
        for camera in ("agentview", "wrist", "fused"):
            samples = [row["phases"][phase]["fused"] if camera == "fused" else row["phases"][phase]["views"][camera]
                       for phase in ("before", "after")]
            verified, evidence = measured_fixture_endpoint(*samples, "open", drawer=True)
            outcomes[camera] = {"public_verdict": verified, "measured_extension_cm": evidence.get("measured_extension_cm"),
                                "reason": evidence.get("reason")}
        row["outcomes"] = outcomes
        rows.append(row)
    report = {"input_manifest": identity(manifest_path), "producer": identity(__file__),
              "source_files": plan["source_files"], "moving_window_margin_m": .005,
              "original_endpoint_thresholds_m": {"open": .025, "close": .015, "stable_frame_drift": .01,
                                                 "view_disagreement": .015},
              "records": rows, "fused_counts": {"true": sum(r["outcomes"]["fused"]["public_verdict"] is True for r in rows),
                  "false": sum(r["outcomes"]["fused"]["public_verdict"] is False for r in rows),
                  "null": sum(r["outcomes"]["fused"]["public_verdict"] is None for r in rows)},
              "private_outcomes_used": False, "private_coordinates_used": False,
              "GPU_started": False, "simulator_started": False, "runtime_changed": False,
              "new_physical_trials": 0, "qualification_authorized": False}
    target = output / "report.json"
    target.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"fused_counts": report["fused_counts"], "report": identity(target)}))


if __name__ == "__main__":
    main()
