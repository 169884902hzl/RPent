"""Attach synchronized saved dual images using only an explicit file index.

This is alignment of original captured frames, not a stochastic Pi05 replay.
Rows with no exact state match or no synchronized camera pair are quarantined.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.v6_som import render_pair


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def match_frame(event: dict, steps: dict, *, post: bool) -> tuple[dict, dict]:
    """Check logged robot state against its explicitly measured capture step."""
    measurements = event["post_measurements" if post else "measurements"]
    robot = event["post_robot_measurement" if post else "robot_measurement"]
    key = "post_frame_step" if post else "decision_frame_step"
    step = event.get(key)
    method = "explicit_decision_frame"
    if step is None:
        step = max((m["source_step"] for m in measurements), default=None)
        method = "newest_measurement_source_plus_robot_match"
    if step not in steps:
        raise ValueError("no registered frame for decision state")
    frame = steps[step]
    state = frame["state"]
    delta = float(np.max(np.abs(np.asarray(state["robot0_eef_pos"]) - robot["eef_xyz"])))
    opening = sum(abs(x) for x in state["robot0_gripper_qpos"])
    opening_delta = abs(opening - robot["gripper_opening"])
    # Logged robot values are float32, saved capture state is float64.
    if delta > 1e-6 or opening_delta > 1e-6:
        raise ValueError(f"robot/frame mismatch: eef={delta}, opening={opening_delta}")
    return frame, {"association": method, "max_eef_error_m": delta,
                   "gripper_opening_error_m": opening_delta,
                   "simulation_replay_performed": False,
                   "saved_synchronized_frame": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--index-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--visible-component-filter-v1", action="store_true",
                        help="Remove small disconnected RGB-D support speckles; keep SAM references")
    args = parser.parse_args()
    if sha(args.index) != args.index_sha256:
        raise ValueError("explicit input index changed")
    indexed = json.loads(args.index.read_text())["training"]["files"]
    args.output.mkdir(parents=True, exist_ok=False)
    counts, by_bucket, sources, pictures = Counter(), {}, [], []
    episode_cache, pair_cache = {}, {}
    with (args.output / "train.jsonl").open("x") as kept, \
            (args.output / "premature_finish_negative.jsonl").open("x") as negatives, \
            (args.output / "rejected.jsonl").open("x") as rejected:
        for entry in indexed:
            if not entry.get("admitted") or entry["bucket"] not in ("train", "auxiliary", "premature_finish_negative"):
                continue
            path = Path(entry["path"])
            if sha(path) != entry["sha256"]:
                raise ValueError(f"registered input changed: {path}")
            sources.append(entry)
            episode = path.parent
            if episode not in episode_cache:
                states_path, trace_path = episode / "states.json", episode / "choices.jsonl"
                steps = {s["step_idx"]: s for s in json.loads(states_path.read_text())["steps"]}
                contexts = {}
                for event in (json.loads(line) for line in trace_path.read_text().splitlines()):
                    for post in (False, True):
                        state = event["post_request" if post else "request"]["context"]
                        contexts.setdefault(state, []).append((event, post))
                episode_cache[episode] = (steps, contexts, sha(states_path), sha(trace_path))
            steps, contexts, states_sha, trace_sha = episode_cache[episode]
            for line_number, line in enumerate(path.read_text().splitlines(), 1):
                original = json.loads(line)
                bucket = entry["bucket"]
                counts["input_rows"] += 1
                by_bucket.setdefault(bucket, Counter())["input"] += 1
                try:
                    row = original["row"] if bucket == "premature_finish_negative" else original
                    if row.get("schema_version") != "entities-plan-receipt/3.1":
                        raise ValueError("old schema")
                    if bucket == "premature_finish_negative":
                        finish = original["finish_code"]
                        criteria = row["request"]["questions"]["action"]["criteria"]
                        if (criteria.get(finish) != "finish()"
                                or finish not in row["evaluated_actions"]
                                or finish in row["acceptable_actions"]):
                            raise ValueError("finish probe is not an explicit tested negative")
                    if not 10 <= row["init_state_index"] <= 39 or not row["scene_id"].startswith("original/"):
                        raise ValueError("training episode outside original init10..39")
                    if "sim_truth" in row["request"]["state"]:
                        raise ValueError("truth coordinate in request")
                    matches = contexts.get(row["request"]["state"], [])
                    # Same textual state may occur at multiple decisions. It
                    # must still refer to this exact recorded decision step.
                    matches = [(event, post) for event, post in matches if event["decision"] == row["step"]]
                    if not matches:
                        raise ValueError("request state does not match logged pre/post decision")
                    aligned = []
                    for event, post in matches:
                        try:
                            frame, evidence = match_frame(event, steps, post=post)
                            aligned.append((event, post, frame, evidence))
                        except ValueError:
                            pass
                    if len({frame["step_idx"] for _, _, frame, _ in aligned}) != 1:
                        raise ValueError("no unique synchronized pre/post frame")
                    event, post, frame, evidence = aligned[0]
                    identity = hashlib.sha256(str(episode).encode()).hexdigest()[:16]
                    pair_key = (episode, event["decision"], post)
                    if pair_key not in pair_cache:
                        pair = render_pair(episode, frame["step_idx"], frame["artifacts"],
                                           event["post_measurements" if post else "measurements"],
                                           args.output / "images" / identity / f"d{event['decision']:04d}_{'post' if post else 'pre'}",
                                           visible_component_filter_v1=args.visible_component_filter_v1,
                                           perception_evidence=(event["post_perception_measurement_evidence" if post else "perception_measurement_evidence"]
                                                                if event.get("post_perception_measurement_evidence" if post else "perception_measurement_evidence")
                                                                and any("sam_mask_files" in v for v in event["post_perception_measurement_evidence" if post else "perception_measurement_evidence"].values()) else None))
                        pair_cache[pair_key] = pair
                        pictures.extend({"episode": str(episode), "decision": event["decision"], "post": post,
                                         "frame_step": frame["step_idx"], **view} for view in pair["views"])
                    row["media_pair"] = pair_cache[pair_key]
                    row["image_alignment"] = {**evidence, "states_sha256": states_sha,
                                              "choices_sha256": trace_sha, "state_time": "after_action" if post else "before_action",
                                              "state_text_sha256": hashlib.sha256(row["request"]["state"].encode()).hexdigest()}
                    row["image_source_row"] = {"path": str(path), "sha256": entry["sha256"], "line": line_number}
                    if bucket == "premature_finish_negative":
                        negatives.write(json.dumps(original, ensure_ascii=False) + "\n")
                        negatives.flush()
                        counts["negative_with_dual_images"] += 1
                    else:
                        kept.write(json.dumps(row, ensure_ascii=False) + "\n")
                        kept.flush()
                        counts["regular_with_dual_images"] += 1
                    counts["with_dual_images"] += 1
                    by_bucket[bucket]["with_dual_images"] += 1
                except (ValueError, KeyError, FileNotFoundError) as error:
                    counts["rejected_rows"] += 1
                    counts[str(error)] += 1
                    by_bucket[bucket]["rejected"] += 1
                    rejected.write(json.dumps({"source": str(path), "line": line_number,
                                               "reason": str(error)}, ensure_ascii=False) + "\n")
    manifest = {"schema_version": "entities-plan-receipt/3.1", "counts": dict(counts),
                "by_bucket": {k: dict(v) for k, v in by_bucket.items()},
                "image_coverage": counts["with_dual_images"] / max(1, counts["input_rows"]),
                "input_index": {"path": str(args.index), "sha256": args.index_sha256},
                "input_files": sources, "image_files": pictures,
                "train": {"path": str(args.output / "train.jsonl"), "sha256": sha(args.output / "train.jsonl"),
                          "rows": counts["regular_with_dual_images"]},
                "premature_finish_negative": {
                    "path": str(args.output / "premature_finish_negative.jsonl"),
                    "sha256": sha(args.output / "premature_finish_negative.jsonl"),
                    "rows": counts["negative_with_dual_images"],
                    "format": "source_request_sha256, finish_code, row with unchanged labels and attached media"},
                "rejected": {"path": str(args.output / "rejected.jsonl"), "sha256": sha(args.output / "rejected.jsonl")},
                "projector_sha256": sha(Path(__file__).resolve().parents[1] / "robots/libero/v6_som.py"),
                "visible_component_filter_v1": args.visible_component_filter_v1,
                "sam_overlap_check": "pending", "text_corruption": "pending_shared_Codex2_rule",
                "full_training_admission": False, "new_independent_decision_states": 0}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: manifest[k] for k in ("counts", "by_bucket", "image_coverage")}))


if __name__ == "__main__":
    main()
