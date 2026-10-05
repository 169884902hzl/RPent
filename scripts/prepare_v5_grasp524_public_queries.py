"""Register uniform offline SAM queries on all explicit original moka frames.

Does not load any private contact/hold label, issue RPC, launch GPU jobs or
change runtime. Selection is category-based and exhaustive across both arms,
including missing/negative/positive/pregrasp frames without outcome filtering.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


QUERIES = ("silver moka coffee pot", "moka pot", "coffee pot", "silver octagonal coffee maker")
QUERY_GRADIENT = (("silver moka coffee pot", .5),
                  ("silver octagonal coffee maker", .35), ("coffee pot", .25))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def descriptor(path):
    return {"path": str(path), "sha256": sha(path)}


def artifact(output, name, step):
    if Path(name).name != name:
        raise ValueError("artifact name must be a base filename")
    return output / name / f"{step:02d}{Path(name).suffix}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--case-name")
    parser.add_argument("--source-step", type=int, action="append")
    parser.add_argument("--query-gradient", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha(args.manifest) != args.manifest_sha256:
        raise ValueError("explicit original smoke manifest changed")
    plan = json.loads(args.manifest.read_text())
    registered = {case["name"]: case for case in plan["cases"]}
    if bool(args.case_name) != bool(args.source_step):
        parser.error("explicit case-name and source-step must be supplied together")
    queries = QUERY_GRADIENT if args.query_gradient else tuple((query, .35) for query in QUERIES)
    frames, sources, cases, counts = [], [], [], Counter()
    for ledger in args.ledger:
        data = ledger.read_bytes()
        if data and not data.endswith(b"\n"):
            raise ValueError("only immutable closed ledgers accepted")
        rows = [json.loads(line) for line in data.splitlines() if line.strip()]
        sources.append({**descriptor(ledger), "closed_rows": len(rows)})
        for row in rows:
            case = row["case"]
            if registered.get(case["name"]) != case:
                raise ValueError("closed case differs from explicit original registration")
            if case["object_category"] != "moka pot":
                continue
            if args.case_name and case["name"] != args.case_name:
                continue
            if case["episode"]["suite"] not in {"libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}:
                raise ValueError("original task data only")
            if case["name"] in cases:
                raise ValueError("duplicate original case")
            cases.append(case["name"])
            output = Path(row["output_dir"])
            if sha(output / "choices.jsonl") != row["choices_sha256"]:
                raise ValueError("closed choices SHA changed")
            states_path = output / "states.json"
            states = json.loads(states_path.read_text())
            steps = {step["step_idx"]: step for step in states["steps"]}
            # Read only the public measurement/capture branch from each sample.
            # Neither private_contact_clear_instant nor any later hold is used.
            samples = row["first_attempt"]["contact_evidence"]["private_frame_sync"]["samples"]
            for sample in samples:
                step_id = sample["source_step"]
                if args.source_step and step_id not in set(args.source_step):
                    continue
                step = steps[step_id]
                declared = set(step["artifacts"])
                for camera in ("agentview", "wrist"):
                    names = (f"{camera}_high.png", f"{camera}_metadata.json", f"{camera}_world_high.npz")
                    if not set(names).issubset(declared):
                        raise ValueError("public original frame artifacts are missing")
                    view = sample["per_view"][camera]
                    masks = [descriptor(artifact(output, name, step_id)) for name in sorted(declared)
                             if name.startswith(f"v6_sam_{camera}_") and name.endswith(".npz")]
                    frames.append({"frame_id": f"{case['name']}:{step_id}:{camera}",
                                   "case": case["name"], "episode": case["episode"], "condition": case["condition"],
                                   "camera": camera, "source_step": step_id, "phase": sample["phase"],
                                   "image": descriptor(artifact(output, names[0], step_id)),
                                   "camera_metadata": descriptor(artifact(output, names[1], step_id)),
                                   "world": descriptor(artifact(output, names[2], step_id)),
                                   "states_manifest": descriptor(states_path), "declared_sam_masks": masks,
                                   "original_public_target_measurement": view["measurement"],
                                   "original_public_target_points": view["points"],
                                   "original_public_missing_reason": view["missing_reason"],
                                   "queries": [{"text_prompt": text, "min_score": score} for text, score in queries]})
                    counts[f"{camera}_frames"] += 1
                    counts[f"{camera}_original_target_points_present"] += int(view["points"] is not None)
                    counts[f"{camera}_original_target_points_missing"] += int(view["points"] is None)
    expected_cases = {case["name"] for case in registered.values() if case["object_category"] == "moka pot"}
    if args.case_name:
        expected_cases = {args.case_name}
        if {frame["source_step"] for frame in frames} != set(args.source_step):
            raise ValueError("all explicitly requested diagnostic steps must exist")
    if set(cases) != expected_cases or len(frames) != len({frame["frame_id"] for frame in frames}):
        raise ValueError("all registered original moka arms must be present exactly once")
    result = {"version": "original-public-SAM-query-pilot/1", "manifest": descriptor(args.manifest),
              "ledgers": sources, "cases": cases, "frames": frames, "counts": dict(counts),
              "total_images": len(frames), "total_queries": len(frames) * len(queries),
              "queries": [{"text_prompt": text, "min_score": score} for text, score in queries],
              "sampling": ("explicit parent-requested diagnostic steps (pregrasp, first public miss and two previously identified private diagnostic frames); script never reads contact/hold labels"
                           if args.case_name else "every saved sample in both original moka arms, both cameras; no contact/hold label selection"),
              "private_labels_in_request": False, "private_truth_cannot_select_runtime_query": True,
              "diagnostic_only": True, "qualification": False, "confirmation": False,
              "new_training_rows": 0, "runtime_verdict_or_controls_changed": False,
              "interpretation": ("Existing main/retry/low-score query gradient applied identically to both cameras. Original secondary only used primary wording at .35; this diagnostic does not reproduce that policy or change runtime."
                                 if args.query_gradient else "Uniform .35 score isolates query wording; it is not the actual main-view .5 primary runtime policy."),
              "next_required_instrumentation": ["record original query/image SHA, raw result score/mask SHA and each geometry rejection",
                                                 "record camera capture sim_time without new motion/capture",
                                                 "missing target remains null, never accept unrelated nearby-object masks"]}
    args.output.mkdir(parents=True, exist_ok=False)
    destination = args.output / "queries.json"
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"manifest": descriptor(destination), "total_images": result["total_images"],
                      "total_queries": result["total_queries"], "counts": dict(counts)}))


if __name__ == "__main__":
    main()
