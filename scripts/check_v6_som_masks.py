"""Check a seeded, view-balanced sample against SAM on original saved RGB."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import random
import sys

import numpy as np

from robots.libero.v5_runtime import segmentation_prompt
from rpent.robots.components.sam3_client import Sam3Client
from rpent.utils.daemon import ProcessDaemon, pick_free_port
from rpent.utils.rpc import wait_for_ready
from rpent.utils.rpc.http_rpc import HttpRpcClient


def overlap(box, mask):
    """Report mask IoU, mask coverage and bbox IoU without conflating them."""
    x0, y0, x1, y1 = box
    intersection = int(mask[y0:y1, x0:x1].sum())
    box_area = (x1 - x0) * (y1 - y0)
    mask_area = int(mask.sum())
    rows, cols = np.nonzero(mask)
    if not len(rows):
        return {"mask_iou": 0, "mask_coverage": 0, "bbox_iou": 0}
    reference = [int(cols.min()), int(rows.min()), int(cols.max()) + 1, int(rows.max()) + 1]
    bbox_intersection = max(0, min(x1, reference[2]) - max(x0, reference[0])) * max(0, min(y1, reference[3]) - max(y0, reference[1]))
    bbox_area = (reference[2] - reference[0]) * (reference[3] - reference[1])
    return {"mask_iou": intersection / max(1, box_area + mask_area - intersection),
            "mask_coverage": intersection / max(1, mask_area),
            "bbox_iou": bbox_intersection / max(1, box_area + bbox_area - bbox_intersection),
            "sam_bbox": reference, "mask_area": mask_area}


def load_measurement_mask(record, *, view, step):
    """Use the registered instance at this exact view and decision frame."""
    if record["camera"] != view or record["source_step"] != step:
        raise ValueError("SAM measurement is from another view or frame")
    path = Path(record["path"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("registered SAM measurement mask changed")
    with np.load(path) as stored:
        return stored["array"].astype(bool)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=360)
    parser.add_argument("--reference", choices=("rerun_sam", "recorded_measurement"), default="rerun_sam")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    unique = {}
    for image in manifest["image_files"]:
        unique.setdefault((image["image_sha256"], image["view"]), image)
    rng = random.Random(args.seed)
    sample = []
    for view in ("agentview", "wrist"):
        pool = [image for image in unique.values() if image["view"] == view]
        if len(pool) < 25:
            raise ValueError(f"fewer than 25 unique {view} frames")
        sample.extend(rng.sample(pool, 25))
    (args.output / "sample.json").write_text(json.dumps(sample, indent=2) + "\n")
    port = pick_free_port()
    daemon = ProcessDaemon(name="v6_som_sam", cmd=[sys.executable, "-m", "robots.libero.v5_sam3_server", "--port", str(port), "--parent-watch"],
                           log_path=str(args.output / "sam.log"))
    frames = []
    try:
        if args.reference == "rerun_sam":
            daemon.start()
            rpc = HttpRpcClient(f"http://127.0.0.1:{port}")
            wait_for_ready(rpc, daemon=daemon, timeout_s=300)
        with (args.output / "checks.jsonl").open("x") as log:
            for image_index, image in enumerate(sample):
                image_path = Path(image["original_image"])
                if hashlib.sha256(image_path.read_bytes()).hexdigest() != image["image_sha256"]:
                    raise ValueError("original image changed")
                episode = Path(image["episode"])
                event = next(json.loads(line) for line in (episode / "choices.jsonl").read_text().splitlines()
                             if json.loads(line)["decision"] == image["decision"])
                entities = {e["id"]: e for e in event["post_measurements" if image["post"] else "measurements"]}
                query_cache, checks = {}, []
                encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
                for mark_index, mark in enumerate(image["marks"]):
                    name = entities[mark["id"]]["name"]
                    prompt = segmentation_prompt(name)
                    record = image.get("sam_measurement_masks", {}).get(mark["id"])
                    if args.reference == "recorded_measurement":
                        masks = [load_measurement_mask(record, view=image["view"], step=image["frame_step"])] if record else []
                    else:
                        if prompt not in query_cache:
                            query_cache[prompt] = rpc.call("sam3.segment_all", kwargs={"image_base64": encoded,
                                                           "text_prompt": prompt, "min_score": .2}, timeout_s=120)
                        masks = [Sam3Client._decode_result(item).mask for item in query_cache[prompt]["instances"]]
                    if any(mask.shape != (image["height"], image["width"]) for mask in masks if mask is not None):
                        raise ValueError("SAM mask and image dimensions differ")
                    options = [(overlap(mark["box_xyxy"], mask), mask) for mask in masks if mask is not None]
                    if options:
                        metrics, mask = max(options, key=lambda pair: pair[0]["mask_iou"])
                        mask_path = args.output / f"mask_{image_index:02d}_{mark_index:02d}.npz"
                        np.savez_compressed(mask_path, mask=mask)
                        detail = {**metrics, "mask": str(mask_path), "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest()}
                    else:
                        detail = {"mask_iou": 0, "mask_coverage": 0, "bbox_iou": 0, "reason": "no_SAM_mask"}
                    checks.append({**mark, "category": name, "query": prompt,
                                   "reference": args.reference,
                                   "measurement_mask": record if args.reference == "recorded_measurement" else None,
                                   "derived_part": bool(entities[mark["id"]].get("part_of")), **detail})
                frame = {"image": image, "checks": checks,
                         "all_marks_mask_iou_ge_05": bool(checks) and all(c["mask_iou"] >= .5 for c in checks)}
                frames.append(frame)
                log.write(json.dumps(frame) + "\n")
                log.flush()
    finally:
        if args.reference == "rerun_sam":
            daemon.stop()
    checks = [check for frame in frames for check in frame["checks"]]
    passed = sum(c["mask_iou"] >= .5 for c in checks)
    report = {"sampled_images": len(frames), "sample_seed": args.seed, "marks": len(checks),
              "mask_iou_ge_05_count": passed, "mask_iou_ge_05_fraction": passed / max(1, len(checks)),
              "bbox_iou_ge_05_fraction": sum(c["bbox_iou"] >= .5 for c in checks) / max(1, len(checks)),
              "all_marks_pass_image_fraction": sum(f["all_marks_mask_iou_ge_05"] for f in frames) / max(1, len(frames)),
              "admission_passed": len(frames) == 50 and passed / max(1, len(checks)) >= .9,
              "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
              "mask_selection": "same_category_max_mask_iou" if args.reference == "rerun_sam" else "registered_current_measurement_instance",
              "reference": args.reference, "failure_preserved": True,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
