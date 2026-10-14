"""Describe selection-only public pad evidence without choosing a threshold."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics


def pin(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def distribution(values):
    values = sorted(values)
    if not values:
        return {"n": 0}
    return {"n": len(values), "min": values[0], "median": statistics.median(values),
            "p90": values[round((len(values) - 1) * .9)], "max": values[-1]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("summary_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = json.loads((args.summary_dir / "summary.json").read_text())
    plan = json.loads(Path(summary["plan"]["path"]).read_text())
    if plan.get("confirmation") or plan.get("training_allowed"):
        raise ValueError("only the registered selection pool may inform verifier development")
    rows_path = args.summary_dir / "rows.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text().splitlines() if line.strip()]
    inputs, cached, details = {}, {}, []
    groups = defaultdict(lambda: defaultdict(list))
    evidence_counts = Counter()
    for index in rows:
        path = Path(index["input"])
        if path not in cached:
            inputs[str(path)] = pin(path)
            if inputs[str(path)]["sha256"] != index["input_sha256"]:
                raise ValueError("physical input ledger changed")
            cached[path] = path.read_bytes().splitlines()
        raw = json.loads(cached[path][index["line"] - 1])
        measured = (raw.get("first_attempt") or {}).get("verification_measurements") or {}
        pair = measured.get("independent_grasp") or {}
        frames = []
        label = "unknown" if index["registered_v3"] is None else str(index["registered_v3"])
        for frame_no, frame in enumerate(pair.get("frames", [])):
            pad_evidence = frame.get("public_finger_pad_regions") or {}
            by_pad = defaultdict(list)
            count_by_pad = defaultdict(list)
            inward_by_pad = defaultdict(list)
            inward_counts = defaultdict(list)
            for camera, view in pad_evidence.get("per_view", {}).items():
                if not view.get("current_target_points"):
                    continue
                for pad in view.get("pads", []):
                    distance = pad.get("target_surface_min_distance_m")
                    if isinstance(distance, (float, int)):
                        by_pad[pad["geom_name"]].append(distance)
                        count_by_pad[pad["geom_name"]].append(pad["points_within_measured_tolerance"])
                        groups[(index["category"], index["method"], label)][camera + ":" + pad["geom_name"]].append(distance)
                    inward = pad.get("target_surface_min_inward_face_distance_m")
                    if isinstance(inward, (float, int)):
                        inward_by_pad[pad["geom_name"]].append(inward)
                        inward_counts[pad["geom_name"]].append(pad["points_near_inward_face"])
                        groups[(index["category"], index["method"], label)][camera + ":inward:" + pad["geom_name"]].append(inward)
            nearest = {key: min(values) for key, values in by_pad.items()}
            joint = pad_evidence.get("finger_joint_qpos_m")
            item = {"frame": frame_no, "source_step": frame.get("source_step"),
                    "opening_m": frame.get("opening_m"), "finger_joint_qpos_m": joint,
                    "pad_min_distance_across_fresh_views_m": nearest,
                    "points_within_original_measured_tolerance_by_pad": dict(count_by_pad),
                    "two_pads_measured": len(nearest) == 2,
                    "public_finger_pad_regions": pad_evidence}
            if inward_by_pad:
                nearest_inward = {key: min(values) for key, values in inward_by_pad.items()}
                item["inward_face_min_distance_across_fresh_views_m"] = nearest_inward
                item["points_near_inward_face_by_pad"] = dict(inward_counts)
                if len(nearest_inward) == 2:
                    groups[(index["category"], index["method"], label)]["farthest_inward_face"].append(max(nearest_inward.values()))
            if len(nearest) == 2:
                largest = max(nearest.values())
                item["farthest_pad_min_distance_m"] = largest
                groups[(index["category"], index["method"], label)]["farthest_pad"].append(largest)
            frames.append(item)
        evidence_counts[(label, str(index["public"]), str(len(frames)),
                         str(all(f["two_pads_measured"] for f in frames) if frames else False))] += 1
        details.append({"case": index["case"], "input": index["input"], "line": index["line"],
                        "category": index["category"], "method": index["method"],
                        "registered_v3": index["registered_v3"], "old_public_verdict": index["public"],
                        "frames": frames, "coupled_lift_evidence": pair.get("coupled_lift_evidence"),
                        "empty_aperture_evidence": pair.get("empty_aperture_evidence"),
                        "training_allowed": False})
    report = {"input_rows": pin(rows_path), "source": pin(Path(__file__)),
              "n": len(rows), "registered_n": summary["registered_n"],
              "complete": summary["complete"], "selection_only": True,
              "threshold_selected": False, "public_verdict_unchanged": True,
              "qualification_allowed": False, "inputs": list(inputs.values()),
              "coverage": [{"truth": key[0], "public": key[1], "frame_count": int(key[2]),
                            "two_pads_measured_in_all_frames": key[3] == "True", "n": count}
                           for key, count in evidence_counts.items()],
              "distance_distributions": [{"category": key[0], "method": key[1], "truth": key[2],
                                          "features": {name: distribution(values) for name, values in group.items()}}
                                         for key, group in groups.items()]}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in details))
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "inputs"}, indent=2))


if __name__ == "__main__":
    main()
