"""Audit RPent's historical-ascent stop from explicitly saved first trials."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_trial(row):
    trace = Path(row["output_dir"]) / "choices.jsonl"
    if sha(trace) != row["choices_sha256"]:
        raise ValueError(f"saved choices changed: {trace}")
    choices = [json.loads(line) for line in trace.read_text().splitlines()]
    if len(choices) != 1:
        raise ValueError(f"not a registered first-decision trace: {trace}")
    primitive = row.get("rpent_pick_result") or {}
    chunks = [item for item in choices[0].get("motion_evidence", [])
              if item.get("name") == "vla_act_chunk"]
    identity = {"case": row["case"], "truth": row.get("true_sustained_grasp"),
                "recorded_visual": row.get("visual_verified"), "path": str(trace),
                "sha256": row["choices_sha256"], "public_pick": primitive}
    if not primitive:
        return {**identity, "status": "public_pick_not_used"}
    if not chunks:
        raise ValueError(f"registered public pick has no motion trace: {trace}")
    if len(chunks) != primitive["chunks_used"]:
        raise ValueError(f"public chunk count mismatch: {trace}")
    if any(item.get("instruction") != primitive["instruction"] for item in chunks):
        raise ValueError(f"mixed instruction chunks: {trace}")
    diag = primitive["diagnostics"]
    minimum = float(diag["start_eef_z"])
    historical_peak = minimum
    for item in chunks:
        z = float(item["final_eef_pos"][2])
        if z < minimum:
            minimum = historical_peak = z
        else:
            historical_peak = max(historical_peak, z)
    if abs(minimum - diag["min_eef_z"]) > .000051:
        raise ValueError(f"reconstructed descent minimum mismatch: {trace}")
    if abs(historical_peak - diag["post_min_peak_z"]) > .000051:
        raise ValueError(f"reconstructed historical peak mismatch: {trace}")
    final = chunks[-1]
    current_ascent = float(final["final_eef_pos"][2]) - minimum
    historical_ascent = historical_peak - minimum
    # Stored start/diagnostic values are rounded to 4 decimal places. Do not
    # classify threshold differences within 0.2 mm as supported discrepancies.
    margin = .0002
    lift_threshold = diag["lift_thresh"]
    native_stop = bool(primitive.get("terminated") or primitive.get("truncated"))
    historical_only_stop = bool(primitive["success"] and not native_stop
        and historical_ascent >= lift_threshold
        and current_ascent < lift_threshold - margin)
    return {**identity, "status": "complete", "native_stop": native_stop,
            "chunks": len(chunks), "current_ascent_m": current_ascent,
            "historical_ascent_m": historical_ascent,
            "minimum_eef_z": minimum, "current_eef_z": final["final_eef_pos"][2],
            "final_opening_m": final["gripper_opening"],
            "historical_only_stop": historical_only_stop,
            "last_chunk_dz_m": (final["final_eef_pos"][2] - chunks[-2]["final_eef_pos"][2])
                if len(chunks) > 1 else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    inputs, rows, seen = [], [], set()
    for path in args.ledger:
        lines = path.read_text().splitlines()
        inputs.append({"path": str(path), "sha256": sha(path), "rows": len(lines)})
        for line in lines:
            source = json.loads(line)
            identity = source["output_dir"]
            if identity in seen:
                raise ValueError(f"duplicate source trial: {identity}")
            seen.add(identity)
            rows.append({**inspect_trial(source), "cohort": path.parent.name})
    groups = defaultdict(Counter)
    for row in rows:
        key = (row["cohort"], row["case"]["group"], row["case"]["condition"])
        count = groups[key]
        count["trials"] += 1
        count[row["status"]] += 1
        count["true" if row["truth"] is True else "false" if row["truth"] is False else "unknown"] += 1
        if row.get("historical_only_stop"):
            count["historical_only_stop"] += 1
            count["historical_only_true" if row["truth"] is True else
                  "historical_only_false" if row["truth"] is False else "historical_only_unknown"] += 1
    report = {"scope": "CPU saved-trace diagnostic, no physics or qualification",
              "inputs": inputs, "script_sha256": sha(__file__),
              "total_trials": len(rows),
              "groups": [{"cohort": cohort, "class": group, "condition": condition, **dict(count)}
                         for (cohort, group, condition), count in sorted(groups.items())],
              "caveats": [
                  "current ascent uses the final Pi0 chunk, not the caller's later trial-lift position",
                  "a historical-only public stop is a hypothesis, not proven cause of physical failure",
                  "private truth is a saved diagnostic label; it never changes policy stopping",
                  "0.2mm uncertainty band excludes rounded-diagnostic threshold ambiguity",
                  "public opening/descent-ascent criteria do not establish target-object hold"],
              "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"scope": report["scope"], "total_trials": len(rows),
                      "public_pick_trials": sum(row["status"] == "complete" for row in rows),
                      "historical_only_stops": [row for row in report["groups"]
                                                if row.get("historical_only_stop")]}))


if __name__ == "__main__":
    main()
