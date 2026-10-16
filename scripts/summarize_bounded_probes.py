"""Recount bounded-skill development probes without dropping failed routes."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics


def wilson(success, n):
    if not n:
        return None
    z = 1.959963984540054
    p = success/n
    center = (p+z*z/(2*n))/(1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [center-half, center+half]


def distribution(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"n": 0, "median": None, "p90": None, "max": None}
    at = .9*(len(values)-1)
    low = math.floor(at)
    high = math.ceil(at)
    return {"n": len(values), "median": statistics.median(values),
            "p90": values[low]+(values[high]-values[low])*(at-low), "max": values[-1]}


def motion(paths):
    rows, sources = [], []
    for path in paths:
        raw = path.read_bytes()
        sources.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
        for row in json.loads(raw):
            details = row["details"]
            complete = not row.get("error")
            if row["method"].startswith("smooth"):
                complete = complete and all(d.get("stop_reason") == "endpoint" and
                    d.get("endpoint_error_m", 1.) <= .012 for d in details)
            else:
                complete = complete and row["metrics"].get("max_waypoint_residual_m", 1.) <= .02
            rows.append({"seed": row["seed"], "sequence": row["sequence"], "method": row["method"],
                "complete": complete, "steps": row["steps"], "metrics": row["metrics"],
                "stop_reasons": [d.get("stop_reason", "legacy_distance_report") for d in details],
                "record": str(path.parent/f"seed{row['seed']}_sequence{row['sequence']}_{row['method']}.json")})
    groups = defaultdict(list)
    for row in rows:
        groups[row["method"]].append(row)
    summary = {}
    for name, group in groups.items():
        summary[name] = {"n": len(group), "complete": sum(r["complete"] for r in group),
            "stop_reasons": dict(Counter(s for r in group for s in r["stop_reasons"])),
            "metrics": {key: distribution([r["metrics"].get(key) for r in group]) for key in (
                "jerk_rms_m_s3", "waypoint_stops", "commanded_segment_stops", "path_length_m",
                "path_to_chord_ratio", "max_tracking_error_m", "max_waypoint_residual_m")}}
    lookup = {(r["seed"], r["sequence"], r["method"]): r for r in rows}
    if len(lookup) != len(rows):
        raise ValueError("duplicate motion state/method")
    paired = {}
    for baseline in ("legacy_move_to", "legacy_move", "smooth_k1"):
        pairs = [(r, lookup[(r["seed"], r["sequence"], baseline)]) for r in groups["smooth_k4"]
                 if (r["seed"], r["sequence"], baseline) in lookup]
        paired[baseline] = {"n": len(pairs), "complete_improved": sum(a["complete"] and not b["complete"] for a,b in pairs),
            "complete_regressed": sum(b["complete"] and not a["complete"] for a,b in pairs),
            "jerk_delta": distribution([a["metrics"]["jerk_rms_m_s3"]-b["metrics"]["jerk_rms_m_s3"] for a,b in pairs])}
    return {"sources": sources, "summary": summary, "paired_k4_minus": paired, "rows": rows,
        "limitations": ["Motion diagnostics are not task-success trials.",
            "Legacy tracking error is per-command target residual; smooth error is timed-reference residual.",
            "Measured stops use a 5mm/s trough; commanded stops are a separate count.",
            "All executed routes remain in aggregates, including incomplete ones."]}


def feasibility(paths):
    rows, sources = [], []
    for path in paths:
        raw = path.read_bytes()
        sources.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
        for line in raw.splitlines():
            row = json.loads(line)
            if row.get("status") != "physical_result":
                continue
            row["record"] = str(path)
            # Keep the registered case/name; correct only this report's category.
            category = row["case"]["category"]
            row["report_category"] = "plate_push" if category == "plate_transfer" else category
            rows.append(row)
    groups = defaultdict(list)
    identities = set()
    for row in rows:
        ep = row["case"]["episode"]
        key = (ep["suite"], ep["task"], ep["seed"], row["arm"])
        if key in identities:
            raise ValueError("repeated feasibility trial; select a specific source cohort")
        identities.add(key)
        groups[(row["arm"], row["report_category"])].append(row)
    summary = []
    for (arm, category), group in sorted(groups.items()):
        success = sum(r["success"] for r in group)
        summary.append({"arm": arm, "category": category, "n": len(group), "success": success,
            "rate": success/len(group), "wilson95": wilson(success,len(group)),
            "decisions": distribution([r.get("decisions") for r in group]),
            "sim_steps": distribution([r.get("sim_steps") for r in group]),
            "wall_s": distribution([r.get("wall_s") for r in group]),
            "failure_phases": dict(Counter(r.get("failure_phase") for r in group if not r["success"]))})
    return {"sources": sources, "summary": summary, "rows": rows, "training": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("motion", "feasibility"))
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = motion(args.input) if args.mode == "motion" else feasibility(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
