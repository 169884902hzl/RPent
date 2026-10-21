"""Close strict N1 pairs with independently hashed complete initial states."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
import pickle
from pathlib import Path
import sys

import numpy as np


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def wilson(k, n):
    z = 1.959963984540054
    d = 1 + z*z/n
    middle = (k/n + z*z/(2*n))/d
    width = z*math.sqrt(k*(n-k)/n**3 + z*z/(4*n*n))/d
    return [middle-width, middle+width]


def four_stage(timing):
    if "four_stage_s" in timing:
        return timing["four_stage_s"]
    phases = dict.fromkeys(("perception", "candidates", "decision", "execution"), 0.)
    for root, values in timing["main_thread_exclusive_by_root_s"].items():
        for category, seconds in values.items():
            phase = ("perception" if category.startswith("perception.") else
                "decision" if root.startswith("decision.") else
                "candidates" if category.startswith(("planning.", "private_labels.")) else "execution")
            phases[phase] += seconds
    return phases


def arm(directory, index, digest):
    pointer = directory / f"closed_{index:03d}.json"
    if not pointer.exists():
        return None
    p = json.loads(pointer.read_bytes())
    path = Path(p["summary"])
    assert ref(path)["sha256"] == p["sha256"]
    data = json.loads(path.read_bytes())
    assert data["status"] == "physical_result"
    if data.get("evaluation") == "hybrid_repair":
        return {"continuation_pilot": True, "summary": ref(path), "result": data}
    initial = path.parent / "private_initial_physics.pkl"
    actual = digest(pickle.loads(initial.read_bytes()))
    assert actual == data["initial_physics_sha256"]
    common = data["common_initial"]
    for key in ("expected_complete_initial_sha256", "actual_complete_initial_sha256",
                "post_public_refresh_complete_sha256"):
        assert common[key] == actual, (path, key)
    loops = [json.loads(line) for line in (path.parent / "loops.jsonl").read_text().splitlines()]
    return {"case": data["case"], "source_commit": data["source_commit"],
        "success": data["success"], "initial_physics_sha256": actual,
        "initial_artifact": ref(initial), "summary": ref(path),
        "loops": ref(path.parent / "loops.jsonl"), "wall_s": data["wall_s"],
        "decisions": data["decisions"], "sim_steps": data["sim_steps"],
        "stop_reason": data["stop_reason"], "four_stage_s": four_stage(data["timings"]),
        "oracle_successor_legal_s": data["timings"].get("oracle_successor_legal_s"),
        "loop_s": [loop["loop_s"] for loop in loops], "candidate_ids": data["candidate_ids"],
        "loop_four_stage_s": [four_stage(loop['timings']) for loop in loops],
        "loop_oracle_successor_s": [loop['timings'].get('oracle_successor_legal_s',
            sum(seconds for category, seconds in loop['timings']['main_thread_exclusive_by_root_s']
                .get('decision.oracle', {}).items() if category.startswith('planning.'))) for loop in loops],
        "skills": [[receipt["skill"] for receipt in loop["receipts"]] for loop in loops],
        "segmentation_wrapper_calls": data["timings"]["calls"].get("perception.segmentation:call", 0)}


def metrics(rows, name):
    arms = [row[name] for row in rows]
    n = len(arms)
    loops = [value for arm in arms for value in arm["loop_s"]]
    success = sum(arm["success"] for arm in arms)
    return {"n": n, "success": success, "wilson95": wilson(success, n),
        "wall_median_s": float(np.median([a["wall_s"] for a in arms])),
        "wall_total_s": sum(a["wall_s"] for a in arms),
        "decision_loop_median_s": float(np.median(loops)),
        "decision_loop_p90_s": float(np.quantile(loops, .9)), "loops": len(loops),
        "decisions_median": float(np.median([a["decisions"] for a in arms])),
        "steps_median": float(np.median([a["sim_steps"] for a in arms])),
        "per_decision_four_stage_s": {phase: {
            'median': float(np.median([loop[phase] for arm in arms for loop in arm['loop_four_stage_s']])),
            'p90': float(np.quantile([loop[phase] for arm in arms for loop in arm['loop_four_stage_s']], .9))}
            for phase in ('perception', 'candidates', 'decision', 'execution')},
        "oracle_successor_per_decision_s": {
            'median': float(np.median([value for arm in arms for value in arm['loop_oracle_successor_s']])),
            'p90': float(np.quantile([value for arm in arms for value in arm['loop_oracle_successor_s']], .9))},
        "phase_total_s": {phase: sum(a["four_stage_s"][phase] for a in arms)
            for phase in ("perception", "candidates", "decision", "execution")}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--count", type=int, default=32)
    p.add_argument("--allow-partial", action="store_true")
    a = p.parse_args()
    sys.path.insert(0, str(a.source))
    from robots.libero.bounded_hybrid_diagnostic import snapshot_digest
    a.output.mkdir(parents=True, exist_ok=False)
    rows, missing, pilots = [], [], []
    for index in range(a.count):
        before, after = arm(a.before, index, snapshot_digest), arm(a.after, index, snapshot_digest)
        if before is None or after is None:
            missing.append(index)
            continue
        if before.get("continuation_pilot") or after.get("continuation_pilot"):
            assert before.get("continuation_pilot") and after.get("continuation_pilot")
            pilots.append({"index": index, "before": before, "after": after,
                "scope": "VLA continuation pilot; excluded from bounded whole-episode metrics"})
            continue
        assert before["case"] == after["case"]
        assert before["initial_physics_sha256"] == after["initial_physics_sha256"]
        rows.append({"index": index, "case": before["case"]["name"],
            "category": before["case"].get("category", before["case"]["episode"]["suite"]),
            "before": before, "after": after,
            "improved": not before["success"] and after["success"],
            "regressed": before["success"] and not after["success"],
            "candidate_ids_changed": before["candidate_ids"] != after["candidate_ids"],
            "skill_sequence_changed": before["skills"] != after["skills"]})
    if missing and not a.allow_partial:
        raise RuntimeError(f"missing pairs: {missing}")
    assert rows
    path = a.output / "paired_states.jsonl"
    path.write_text("".join(json.dumps(row, sort_keys=True)+"\n" for row in rows))
    pilot_path = a.output / "continuation_pilots.json"
    pilot_path.write_text(json.dumps(pilots, indent=2)+"\n")
    groups = defaultdict(list)
    for row in rows:
        groups[row["category"]].append(row)
    result = {"scope": "N1, complete physics/controller/RNG matched; development, not training",
        "registered": a.count, "closed": len(rows)+len(pilots),
        "paired": len(rows), "missing": missing, "continuation_pilots": ref(pilot_path),
        "before": metrics(rows, "before"), "after": metrics(rows, "after"),
        "improvements": [r["case"] for r in rows if r["improved"]],
        "regressions": [r["case"] for r in rows if r["regressed"]],
        "skill_sequence_changes": sum(r["skill_sequence_changed"] for r in rows),
        "categories": {k: {"before": metrics(v, "before"), "after": metrics(v, "after")}
            for k, v in groups.items()}, "rows": ref(path), "training": False}
    (a.output / "manifest.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({k: result[k] for k in ("paired", "missing", "before", "after", "improvements", "regressions")}))


if __name__ == "__main__":
    main()
