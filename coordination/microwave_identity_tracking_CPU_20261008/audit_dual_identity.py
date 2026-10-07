"""Public-only dense identity audit, with actual cross-view depth support."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from robots.libero.v5_microwave_capture import points_mask
from robots.libero.v5_microwave_identity import match_current_door_across_views, track_measured_door


def checked(record):
    path = Path(record["path"])
    if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("public input changed: " + str(path))
    return path


def array(record):
    with np.load(checked(record), allow_pickle=False) as saved:
        if len(saved.files) != 1:
            raise ValueError("one actual public array required")
        return saved[saved.files[0]]


def run(args):
    manifest = json.loads(args.manifest.read_text())
    if manifest["private_labels_included"] is not False:
        raise ValueError("public-only input required")
    previous = {"agentview": None, "wrist": None}
    anchor = manifest["fixed_anchor"]
    rows = []
    for row in manifest["rows"]:
        images, world = {}, {}
        for view, key in (("agentview", "artifacts"), ("wrist", "wrist_artifacts")):
            images[view] = np.asarray(Image.open(checked(row[key]["rgb"])).convert("RGB"))
            world[view] = array(row[key]["world"])
        faces, masks, evidence = {}, {}, {}
        robot = array(row["robot_mask"]).astype(bool) if row.get("robot_mask") else None
        for view in ("agentview", "wrist"):
            prior = previous[view]
            if prior is not None:
                masks[view], faces[view], evidence[view] = track_measured_door(
                    prior[0], images[view], prior[1], world[view], prior[2], anchor,
                    robot_mask=robot if view == "agentview" else None)
            else:
                masks[view], faces[view], evidence[view] = np.zeros(world[view].shape[:2], bool), None, {
                    "reason": "independent_identity_missing", "stop_admitted": False}
        direct = row.get("moving")
        if direct is not None:
            current_direct = points_mask(world["agentview"], array(direct))
            # This is a fresh independently observed real SAM door. Dense
            # boundary reuse has already required exact RGB and depth parity.
            masks["agentview"], faces["agentview"] = current_direct, direct
            evidence["agentview"]["reacquired_current_independent_SAM"] = True
        if faces["agentview"] is not None:
            transferred, face, support = match_current_door_across_views(
                world["agentview"], masks["agentview"], world["wrist"], anchor)
            evidence["wrist"]["same_current_cross_view_support"] = support
            if face is not None:
                masks["wrist"], faces["wrist"] = transferred, face
                evidence["wrist"]["reacquired_same_current_measured_door"] = True
        if all(faces[view] is not None for view in faces):
            main, wrist = faces["agentview"], faces["wrist"]
            normal = np.asarray(main["normal_xy"])
            gap = abs(float((np.asarray(main["centre"][:2]) - wrist["centre"][:2]) @ normal))
            agreement = abs(float(normal @ wrist["normal_xy"]))
            if gap > .015 or agreement < np.cos(np.deg2rad(10)):
                for view in faces:
                    faces[view] = None
                    masks[view][:] = False
                    evidence[view]["dual_view_reason"] = "current_public_views_disagree"
        for view in previous:
            previous[view] = (images[view], world[view], masks[view]) if faces[view] is not None else None
        rows.append({"capture_id": row.get("capture_id"), "phase": row["phase"],
            "actual_control_index": row.get("actual_control_index"), "faces": faces,
            "evidence": evidence, "stop_admitted": False,
            "source_camera_distribution": [view for view in faces if faces[view] is not None]})
    result = {"version": "microwave-dual-dense-identity-observability/1-dev", "job": manifest["job"],
        "input": {"path": str(args.manifest.resolve()), "sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest()},
        "rows": rows, "private_labels_used": False, "physical_controls": 0,
        "train_allowed": False, "qualification": False, "runtime_default_changed": False}
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"path": str(args.output), "frames": len(rows),
        "plane_frames_by_camera": {view: sum(row["faces"][view] is not None for row in rows) for view in previous},
        "any_plane_frames": sum(bool(row["source_camera_distribution"]) for row in rows),
        "last_actual_controls": [{"control": row["actual_control_index"], "cameras": row["source_camera_distribution"]}
                                 for row in rows[-12:]]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
