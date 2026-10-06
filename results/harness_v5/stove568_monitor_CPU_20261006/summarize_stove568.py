"""Summarize five explicit original probes without changing their records."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics


STAGES = ("before_setup", "after_setup", "before_off", "after_contact", "after_release", "after_retreat")
EXPECTED_MANIFEST = "532114119d4aaa72e46a92772a6f05710e30c4de0bb454f3c7c2de26c740cc09"


def ref(path):
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def error_kind(row):
    errors = [row.get("error", "")] + [row.get(k, {}).get("error", "") for k in ("off_contact", "release_only", "retreat_only")]
    text = " ".join(errors)
    if "servo did not reach measured waypoint" in text:
        return "recoverable_motion_waypoint_failure"
    if any(s in text for s in ("RpcError", "TimeoutError", "ConnectionError", "Connection refused", "private scores", "scoring")):
        return "rpc_service_or_scoring_infrastructure"
    if row.get("status") == "probe_error":
        return "unclassified_probe_error_requires_inspection"
    return None


def summarize_case(root, index):
    directory = root / f"part{index}" / f"libero_goal_t7_s{index}"
    paths = {k: directory / name for k, name in {
        "episode": "episode.json", "private_chunks": "labels_chunk.jsonl",
        "public_chunks": "public_red_chunks.jsonl", "private_scores": "postcollection_private_scores.json"}.items()}
    result = {"seed": index, "case": f"libero_goal_t7_s{index}", "output_dir": str(directory)}
    if not paths["episode"].exists():
        result.update(status="running_or_pending", private_rows=len(read_rows(paths["private_chunks"])) if paths["private_chunks"].exists() else 0,
            public_rows=len(read_rows(paths["public_chunks"])) if paths["public_chunks"].exists() else 0)
        return result
    row = json.loads(paths["episode"].read_text())
    result.update(original_status=row["status"], original_infrastructure_flag=row.get("infrastructure_failure", False),
        wall_s=row["wall_s"], classified_execution_error=error_kind(row), evidence={k: ref(p) for k, p in paths.items() if p.exists()})
    private = read_rows(paths["private_chunks"])
    public = read_rows(paths["public_chunks"])
    private_by_index = {x["chunk_index"]: x for x in private if x["phase"] == "off"}
    scores = json.loads(paths["private_scores"].read_text()) if paths["private_scores"].exists() else None
    capture_refs = row.get("captures", {})
    for stage in STAGES:
        for role, reference in capture_refs.get(stage, {}).items():
            if isinstance(reference, dict) and "path" in reference and "sha256" in reference:
                actual = ref(Path(reference["path"]))
                if actual["sha256"] != reference["sha256"]:
                    raise ValueError(f"stage capture SHA mismatch: {stage}/{role}")
    stage_labels = scores["stage_labels"] if scores else {s: json.loads(Path(capture_refs[s]["labels"]["path"]).read_text()) for s in STAGES if s in capture_refs}
    result["stages"] = {s: {"turn_on": a["requested_predicates"]["turn_on"]["satisfied"],
        "turn_off": a["requested_predicates"]["turn_off"]["satisfied"],
        "joint_qpos": a["requested_predicates"]["turn_off"]["joint_qpos"]} for s, a in stage_labels.items()}
    result.update(private_rows=len(private), public_rows=len(public), contact_chunks=row.get("off_contact", {}).get("chunks"),
        off_controls=row.get("off_contact", {}).get("executed_control_actions"), stage_count=len(stage_labels),
        public_stop_selected=sum(x["stop_decision"]["stop"] for x in public))
    result["ledger_complete"] = (len(private) == 322 and len(public) == 160 and len(stage_labels) == 6
        and all([x["chunk_index"] for x in private if x["phase"] == phase] == list(range(161)) for phase in ("on", "off")))
    curves = [x for x in private if x["phase"] == "off" and x["status"] == "scored"]
    true_chunks = [x["chunk_index"] for x in curves if x["turn_off_satisfied"]]
    result["off_first_satisfied_chunk"] = min(true_chunks) if true_chunks else None
    result["off_satisfied_chunks"] = len(true_chunks)
    measured = Counter()
    confusion = Counter()
    raw_refs = 0
    missing_raw = []
    for observation in public:
        label = private_by_index[observation["chunk_index"]]["turn_off_satisfied"]
        for camera, view in observation["views"].items():
            available = view.get("surface_pixels", 0) >= 100 and view.get("red_fraction") is not None
            measured[camera + (":measured" if available else ":missing")] += 1
            if available:
                dark = view["red_fraction"] <= 0
                confusion[("tp" if label else "fp") if dark else ("fn" if label else "tn")] += 1
            for role in ("raw_rgb", "raw_world"):
                reference = view.get(role)
                if reference:
                    raw_refs += 1
                    if not Path(reference["path"]).is_file():
                        missing_raw.append(reference["path"])
    result.update(public_camera_measurement_counts=dict(measured), public_dark_vs_private_off=dict(confusion), raw_image_world_refs=raw_refs,
        raw_refs_exist=not missing_raw, missing_raw_refs=missing_raw, raw_ref_sha_scope="observer recorded digests; monitor checks existence, not large pixel/point-cloud digest replay")
    stages = result["stages"]
    result["release_lost_off"] = stages["after_contact"]["turn_off"] and not stages["after_release"]["turn_off"]
    result["retreat_lost_off"] = stages["after_release"]["turn_off"] and not stages["after_retreat"]["turn_off"]
    kind = result["classified_execution_error"]
    if kind:
        result["failure_category"] = kind
    elif stages["after_retreat"]["turn_off"]:
        result["failure_category"] = "retained_off_after_retreat"
    elif result["release_lost_off"]:
        result["failure_category"] = "off_lost_during_release"
    elif result["retreat_lost_off"]:
        result["failure_category"] = "off_lost_during_retreat"
    elif true_chunks:
        result["failure_category"] = "off_reached_then_lost_before_contact_end"
    else:
        result["failure_category"] = "off_never_reached"
    result["status"] = "complete" if result["ledger_complete"] else "incomplete_preserved"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    identity = ref(args.manifest)
    if identity["sha256"] != EXPECTED_MANIFEST:
        raise ValueError("probe manifest changed")
    cases = [summarize_case(args.root, i) for i in range(5)]
    completed = [x for x in cases if x["status"] != "running_or_pending"]
    summary = {"version": "stove568-monitor/1", "scope": "original five selection states; not confirmation or final evaluation",
        "manifest": identity, "original_states": 5, "completed_cells": len(completed), "all_ledgers_complete": len(completed) == 5 and all(x["ledger_complete"] for x in completed),
        "failure_counts": dict(Counter(x["failure_category"] for x in completed)),
        "stage_off_counts": {s: sum(x["stages"].get(s, {}).get("turn_off", False) for x in completed) for s in STAGES},
        "stage_denominator": len(completed), "median_wall_s": statistics.median(x["wall_s"] for x in completed) if completed else None,
        "public_rows": sum(x.get("public_rows", 0) for x in cases), "private_rows": sum(x.get("private_rows", 0) for x in cases),
        "public_stop_enabled": False, "private_labels_control_execution": False, "cases": cases}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output / "per_case.jsonl").write_text("".join(json.dumps(x) + "\n" for x in cases))
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}))


if __name__ == "__main__":
    main()
