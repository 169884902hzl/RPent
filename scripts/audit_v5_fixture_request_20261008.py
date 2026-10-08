"""Reconstruct the oversized request using its recorded public RGB-D evidence."""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
from transformers import AutoTokenizer

from robots.libero.v5_perception_geometry import (
    fixture_overlaps_work_surface, measured_work_surface,
)
from robots.libero.v5_state import (
    Candidate, Entity, CHOICE_INSTRUCTION, expand_receipt_metadata, receipt_lines, serialize,
)


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def entities(records):
    return [Entity(**{k: v for k, v in row.items() if k in Entity.__dataclass_fields__})
            for row in records]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = args.episode
    path = source / "rejected_request.json"
    request = json.loads(path.read_text())
    initial_path = source / "initial_measurements.json"
    initial = entities(json.loads(initial_path.read_text())["entities"])
    anchors = [e for e in initial if e.visible and not e.part_of
               and not e.name.startswith("area ")
               and e.name not in ("cabinet", "microwave", "stove", "drawer", "rack",
                                  "basket", "caddy", "table")]
    frame = source / "agentview_world_high.npz/00.npz"
    with np.load(frame) as archive:
        surface = measured_work_surface(archive["array"], anchors)
    if surface is None:
        raise ValueError("recorded initial RGB-D does not support a work surface")
    choices_path = source / "choices.jsonl"
    events = [json.loads(line) for line in choices_path.read_text().splitlines() if line.strip()]
    event = events[-1]
    def geometry_prefix(context):
        return context.split("\nrobot ", 1)[0]
    if geometry_prefix(event["post_request"]["context"]) != geometry_prefix(request["context"]):
        raise ValueError("last post-measurement geometry is not the rejected request")
    measured = entities(event["post_measurements"])
    removed = {e.id for e in measured if e.name in ("cabinet", "microwave", "stove", "drawer")
               and not fixture_overlaps_work_surface(e.lower, e.upper, surface)}
    removed.update(e.id for e in measured if e.part_of in removed)
    kept = {e.id: e for e in measured if e.id not in removed}
    invalidated = []
    for eid, entity in list(kept.items()):
        parent = kept.get(entity.part_of)
        if parent and not parent.visible and entity.visible:
            kept[eid] = replace(entity, visible=False)
            invalidated.append(eid)
    lines = request["context"].splitlines()
    frame_line = next(line for line in lines if line.startswith("rel frame="))
    axes = [json.loads(re.search(name + r"=(\[[^\]]+\])", frame_line)[1])
            for name in ("right_world", "front_world")]
    robot = event["post_robot_measurement"]
    geometry_lines = serialize(json.loads(lines[0][12:]), list(kept.values()),
        robot["gripper_opening"], None, [], view_axes=tuple(axes)).splitlines()
    # Keep recovery values verbatim; this audit does not replay their counters.
    robot_index = next(i for i, line in enumerate(lines) if line.startswith("robot "))
    tail = lines[robot_index:]
    receipts = expand_receipt_metadata([json.loads(line[8:]) for line in tail if line.startswith("receipt ")])
    compact = iter(receipt_lines(receipts))
    tail = [next(compact) if line.startswith("receipt ") else line for line in tail]
    tail = [line for line in tail if not re.search(r"(?:candidate|blocked) \w+\(([^)]*)\)", line)
            or not removed.intersection(re.search(r"\(([^)]*)\)", line)[1].split(","))]
    options = [option for option in request["options"]
               if not removed.intersection((Candidate.from_text(option).object, Candidate.from_text(option).target))]
    context = "\n".join(geometry_lines[:-1] + tail)
    sys.path.insert(0, str(args.package))
    import parallel_schema
    tokenizer = AutoTokenizer.from_pretrained(args.package, local_files_only=True)
    def tokens(text, options):
        keys = [f"C{i}" for i in range(len(options))]
        definition = {"action": {"type": "enum", "description": CHOICE_INSTRUCTION,
            "choices": keys, "choice_descriptions": dict(zip(keys, options))}}
        return len(parallel_schema.prepare_prompts(tokenizer, text, definition, 32768).full_ids[0])
    rebuilt = args.output / "request.json"
    rebuilt.write_text(json.dumps({**request, "context": context, "options": options}, indent=2) + "\n")
    report = {"before_tokens": tokens(request["context"], request["options"]),
        "after_tokens": tokens(context, options), "measured_support": surface,
        "removed_background_ids": sorted(removed), "invalidated_stale_parts": invalidated,
        "remaining_entities": len(kept), "retained_options": len(options),
        "admitted_after": tokens(context, options) <= 3072,
        "scope": "recorded public geometry rerender; no fresh perception or physical replay",
        "private_truth_used": False, "training_allowed": False,
        "inputs": [ref(p) for p in (path, initial_path, choices_path, frame)],
        "generator": ref(__file__), "output": ref(rebuilt)}
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
