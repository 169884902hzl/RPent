"""Replay only saved original-task public RGB-D plane selection on the CPU."""

from dataclasses import fields
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw


def identity(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size}


def checked(ref):
    path = Path(ref["path"])
    if not path.is_absolute():
        raise ValueError("explicit public reference must be absolute")
    actual = identity(path)
    if actual["sha256"] != ref["sha256"]:
        raise ValueError("public evidence changed: " + str(path))
    return path


def entity(record, cls):
    return cls(**{field.name: record[field.name] for field in fields(cls) if field.name in record})


def current_bounds_mask(points, part):
    if part is None:
        return np.zeros(points.shape[:-1], bool)
    return ((points >= np.asarray(part["lower"]) - .005)
            & (points <= np.asarray(part["upper"]) + .005)).all(axis=-1)


def candidates(world, parent, anchored_part, current_part, front, vertical_face):
    points = np.asarray(world, dtype=float).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
    front = np.asarray(front)[:2]
    tangent = np.array((-front[1], front[0]))
    lower, upper = np.asarray(parent["lower"]), np.asarray(parent["upper"])
    corners = np.array([(x, y) for x in (lower[0], upper[0]) for y in (lower[1], upper[1])])
    side_lo, side_hi = np.min(corners @ tangent), np.max(corners @ tangent)
    edge = np.max(corners @ front)
    border_width = min(.025, (side_hi - side_lo) * .12)
    depth, side = points[:, :2] @ front, points[:, :2] @ tangent
    moving = points[(side >= side_lo + border_width) & (side <= side_hi - border_width)
                    & (points[:, 2] >= anchored_part["lower"][2] + .005)
                    & (points[:, 2] <= anchored_part["upper"][2] - .005)
                    & (depth >= edge - .03) & (depth <= edge + .35)]
    projection = moving[:, :2] @ front
    histogram, edges = np.histogram(projection, bins=np.arange(edge - .031, edge + .356, .004))
    rows = []
    for index in np.argsort(histogram)[-5:]:
        centre = (edges[index] + edges[index + 1]) / 2
        selected = moving[np.abs(projection - centre) <= .004]
        fit = vertical_face(selected) if len(selected) >= 30 else None
        accepted = fit is not None and abs(np.asarray(fit["normal_xy"]) @ front) >= .95
        row = {"bin_centre_m": float(centre), "bin_points": int(histogram[index]),
               "selected_points": len(selected), "orientation_accepted": bool(accepted),
               "fit": fit, "current_drawer_bounds_support": int(current_bounds_mask(selected, current_part).sum())}
        if len(selected):
            row["xyz_lower"] = np.min(selected, axis=0).tolist()
            row["xyz_upper"] = np.max(selected, axis=0).tolist()
        rows.append(row)
    valid = [row for row in rows if row["orientation_accepted"]]
    selected = max(valid, key=lambda row: row["selected_points"], default=None)
    return {"front_axis": list(front), "anchor_edge_m": float(edge),
            "moving_gate_depth_m": [float(edge - .03), float(edge + .35)],
            "anchored_z_band_m": [anchored_part["lower"][2] + .005, anchored_part["upper"][2] - .005],
            "candidate_planes": rows, "selected": selected}


def overlay(rgb, world, fit, parent, anchored_part, current_part, front, label):
    image = np.asarray(Image.open(rgb).convert("RGB"))
    if world.shape != (*image.shape[:2], 3):
        raise ValueError("saved original RGB-D pixel contract changed")
    finite = np.isfinite(world).all(axis=-1) & (np.abs(world).sum(axis=-1) > 1e-6)
    selected = np.zeros(image.shape[:2], bool)
    if fit:
        normal = np.asarray(fit["normal_xy"])
        selected = finite & (np.abs((world[..., :2] - fit["centre"][:2]) @ normal) <= .004)
        selected &= ((world[..., 2] >= anchored_part["lower"][2] + .005)
                     & (world[..., 2] <= anchored_part["upper"][2] - .005))
        selected &= ((world[..., 0] >= parent["lower"][0]) & (world[..., 0] <= parent["upper"][0]))
    current = finite & current_bounds_mask(world, current_part)
    coloured = image.copy()
    for mask, colour in ((selected, [255, 0, 0]), (current, [0, 255, 0]), (selected & current, [255, 255, 0])):
        coloured[mask] = (.5 * image[mask] + .5 * np.asarray(colour)).astype(np.uint8)
    result = Image.fromarray(coloured)
    draw = ImageDraw.Draw(result)
    draw.rectangle((0, 0, result.width, 55), fill="black")
    draw.text((8, 5), label, fill="white")
    draw.text((8, 25), "red=chosen moving plane; green=current public drawer bounds; yellow=overlap", fill="white")
    return result, {"selected_plane_pixels": int(selected.sum()), "current_drawer_bounds_pixels": int(current.sum()),
                    "overlap_pixels": int((selected & current).sum())}


def main():
    manifest_path, output = map(Path, sys.argv[1:])
    plan = json.loads(manifest_path.read_text())
    for ref in plan["source_files"]:
        checked(ref)
    from robots.libero.v5_fixture_parts import measured_drawer_faces
    from robots.libero.v5_state import Entity
    from robots.libero.v5_verification import vertical_face
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    pictures = []
    for case in plan["cases"]:
        parent = entity(case["anchor_parent"], Entity)
        part = entity(case["anchor_part"], Entity)
        row = {"case": case["case"], "diagnostic_private_endpoint_satisfied": case["endpoint_satisfied"],
               "recorded_public_verdict": case["recorded_public_verdict"], "recorded_extension_cm": case["recorded_extension_cm"],
               "public_entity_dxyz_cm": case["public_entity_dxyz_cm"], "phases": {}}
        for phase, inputs in case["frames"].items():
            worlds = {}
            for camera, refs in inputs.items():
                for ref in refs.values(): checked(ref)
                with np.load(refs["world"]["path"], allow_pickle=False) as archive:
                    worlds[camera] = archive["array"]
            joined = np.concatenate([world.reshape(-1, 3) for world in worlds.values()])
            fit, clouds = measured_drawer_faces(joined, parent, part, case["front_axis"])
            saved = case["recorded_endpoint"][phase]
            comparisons = {}
            for kind in ("frame", "moving"):
                old, now = saved.get(kind), fit.get(kind)
                comparisons[kind] = {"both_missing": old is None and now is None}
                if old and now:
                    comparisons[kind].update(points_equal=old["points"] == now["points"],
                        centre_max_abs_error_m=float(np.max(np.abs(np.asarray(old["centre"]) - now["centre"]))),
                        normal_max_abs_error=float(np.max(np.abs(np.asarray(old["normal_xy"]) - now["normal_xy"]))))
            current_part = case["public_part"][phase]
            analysis = candidates(joined, case["anchor_parent"], case["anchor_part"], current_part,
                                  case["front_axis"], vertical_face)
            row["phases"][phase] = {"replayed_fits": fit, "recorded_fit_comparison": comparisons,
                                     "selection_audit": analysis, "inputs": inputs}
            if case["render_overlay"]:
                for camera, refs in inputs.items():
                    per_view, _ = measured_drawer_faces(worlds[camera], parent, part, case["front_axis"])
                    picture, counts = overlay(refs["rgb"]["path"], worlds[camera], per_view.get("moving"),
                        case["anchor_parent"], case["anchor_part"], current_part, case["front_axis"],
                        f'{case["case"]} {phase} {camera}')
                    target = output / f'{case["case"]}_{phase}_{camera}_overlay.png'
                    picture.save(target)
                    row["phases"][phase].setdefault("overlays", {})[camera] = {**counts, **identity(target)}
                    pictures.append(picture.resize((512, 512)))
        rows.append(row)
    if pictures:
        montage = Image.new("RGB", (1024, ((len(pictures) + 1) // 2) * 512))
        for index, picture in enumerate(pictures): montage.paste(picture, ((index % 2) * 512, (index // 2) * 512))
        montage.save(output / "public_plane_binding_montage.png")
    report = {"manifest": identity(manifest_path), "records": rows, "simulator_started": False,
              "GPU_started": False, "runtime_changed": False, "private_coordinates_used": False,
              "private_labels_use": "endpoint booleans only, diagnostic comparison; never plane selection",
              "new_physical_trials": 0, "qualification_authorized": False}
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"records": len(rows), "output": str(output), "GPU_started": False, "simulator_started": False}))


if __name__ == "__main__":
    main()
