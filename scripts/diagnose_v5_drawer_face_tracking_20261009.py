"""Compare tracked public face displacement with existing selection fits."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from robots.libero.v5_drawer_face_tracking import track_face


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load_map(path):
    with np.load(path) as data:
        return data[data.files[0]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for ledger in args.ledger:
        for raw in ledger.read_text().splitlines():
            row = json.loads(raw)
            attempt = row.get("first_attempt") or {}
            measured = attempt.get("verification_measurements") or {}
            before = measured.get("articulation", {}).get("before")
            captures = measured.get("drawer_public_stop") or []
            if before is None:
                continue
            root = Path(row["output_dir"])
            for capture in captures:
                after = capture.get("measurement") or {}
                step = after.get("source_step")
                if step is None:
                    continue
                views = {}
                for camera in ("agentview", "wrist"):
                    initial = before.get("source_step", 0)
                    paths = [root / f"{camera}_high.png" / f"{t:02d}.png" for t in (initial, step)]
                    paths += [root / f"{camera}_world_high.npz" / f"{t:02d}.npz" for t in (initial, step)]
                    if not all(p.is_file() for p in paths):
                        views[camera] = {"status": "unmeasured", "reason": "saved_public_image_missing"}
                        continue
                    value = track_face(np.asarray(Image.open(paths[0]).convert("RGB")), load_map(paths[2]),
                                       np.asarray(Image.open(paths[1]).convert("RGB")), load_map(paths[3]), before)
                    value["inputs"] = list(map(ref, paths))
                    if value["status"] == "measured" and after.get("moving"):
                        axis = np.asarray(before["outward_axis_xy"])
                        gap = (np.asarray(after["moving"]["centre"])[:2]
                               - np.asarray(value["tracked_face_centre_m"])[:2]) @ axis
                        value.update(current_fit_identity_gap_m=float(gap),
                                     current_fit_matches_tracked_face=bool(abs(gap) <= .015))
                    views[camera] = value
                records.append({"episode": row["case"]["episode"], "mode": row["case"]["mode"],
                                "chunk": capture["chunk"], "source_step": step,
                                "existing_public_verdict": capture.get("verified"), "views": views})
    path = args.output / "public_correspondences.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in records))
    cameras = [v for row in records for v in row["views"].values()]
    summary = {"source": ref(Path(__file__)), "tracker": ref(Path(track_face.__code__.co_filename)),
               "inputs": list(map(ref, args.ledger)), "records": len(records),
               "camera_correspondences_measured": sum(v["status"] == "measured" for v in cameras),
               "identity_mismatch": sum(v.get("current_fit_matches_tracked_face") is False for v in cameras),
               "private_labels_read": False, "physical_actions": 0, "runtime_enabled": False,
               "output": ref(path)}
    (args.output / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
