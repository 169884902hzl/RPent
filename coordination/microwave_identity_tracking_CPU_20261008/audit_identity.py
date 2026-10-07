"""Explicit saved public trajectory diagnostic; never runs robot controls."""

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from robots.libero.v5_microwave_capture import points_mask
from robots.libero.v5_microwave_identity import track_measured_door


def checked(record):
    path = Path(record["path"])
    if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("registered public input changed: " + str(path))
    return path


def array(record):
    with np.load(checked(record), allow_pickle=False) as saved:
        if len(saved.files) != 1:
            raise ValueError("one public array required")
        return saved[saved.files[0]]


def run(args):
    manifest = json.loads(args.manifest.read_text())
    if manifest["private_labels_included"] is not False:
        raise ValueError("public-only diagnostic input required")
    previous = None
    rows = []
    fixed_anchor = manifest["fixed_anchor"]
    initialized = False
    for row in manifest["rows"]:
        started = time.perf_counter()
        rgb = np.asarray(Image.open(checked(row["artifacts"]["rgb"])).convert("RGB"))
        world = array(row["artifacts"]["world"])
        robot = array(row["robot_mask"]).astype(bool) if row.get("robot_mask") else None
        measured = row.get("moving")
        record = {"phase": row["phase"], "block": row["block"], "source_step": row["source_step"],
                  "original_SAM_plane_available": measured is not None,
                  "robot_mask_measured": robot is not None}
        if previous is None and measured and (not initialized or args.reseed_independent_SAM):
            cloud = array(measured)
            mask = points_mask(world, cloud)
            previous = (rgb, world, mask)
            record.update(reason="initialized_from_original_independent_SAM_plane", tracked_plane=measured,
                          reacquisition_from_current_independent_SAM=bool(initialized))
            initialized = True
        elif previous:
            mask, face, evidence = track_measured_door(previous[0], rgb, previous[1], world, previous[2],
                                                       fixed_anchor, robot_mask=robot)
            record.update(evidence, tracked_plane=face)
            if face:
                # Refresh real mask support only when the original SAM plane
                # contains a majority of identity-tracked current depth points.
                if measured:
                    direct = points_mask(world, array(measured))
                    intersection = int((mask & direct).sum())
                    overlap = intersection / max(1, int(mask.sum()))
                    record["independent_SAM_overlap_of_track"] = overlap
                    if overlap >= .55:
                        mask = direct
                        record["refreshed_from_independent_SAM"] = True
                previous = (rgb, world, mask)
            else:
                previous = None
                record["identity_lost_no_unobserved_bridge"] = True
                if measured and args.reseed_independent_SAM:
                    previous = (rgb, world, points_mask(world, array(measured)))
                    record["reacquired_same_frame_independent_SAM_for_next_capture"] = True
        else:
            record.update(reason="identity_lost_no_unobserved_bridge", tracked_plane=None)
        record["wall_s"] = time.perf_counter() - started
        rows.append(record)
    result = {"version": "microwave-public-identity-observability/1-dev", "input": {
        "path": str(args.manifest.resolve()), "sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest()},
        "rows": rows, "reseed_from_current_independent_SAM": args.reseed_independent_SAM,
        "physical_controls": 0, "private_labels_used": False,
        "qualification": False, "training_allowed": False}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"path": str(args.output), "tracked_planes": sum(r.get("tracked_plane") is not None for r in rows),
                      "rows": len(rows), "final": rows[-6:]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reseed-independent-SAM", action="store_true")
    run(parser.parse_args())
