"""Keep all functional moka layout outcomes, including no-motion bindings."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    p, d = k/n, 1+z*z/n
    centre = (p+z*z/(2*n))/d
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [centre-half, centre+half]


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan_path = args.root / "preparation/selection100.json"
    plan = json.loads(plan_path.read_text())
    planned = {row["name"]: row for row in plan["cases"]}
    if len(planned) != 100 or plan.get("confirmation"):
        raise ValueError("this report requires the declared hundred selection layouts")
    references, completed, infrastructure = [ref(plan_path)], {}, []
    for ledger in sorted(args.root.rglob("episodes.jsonl")):
        references.append(ref(ledger))
        raw = ledger.read_bytes()
        for number, line in enumerate(raw[:raw.rfind(b"\n")+1].splitlines(), 1):
            row = json.loads(line)
            name = row["case"]["name"]
            if row["case"] != planned.get(name):
                raise ValueError("case differs from registered layout")
            result = row.get("result", {})
            if result.get("infrastructure_failure") or result.get("status") != "completed":
                infrastructure.append({"case": name, "status": result.get("status"),
                                       "error": result.get("error"), "ledger": ref(ledger), "line": number})
                continue
            if name in completed:
                raise ValueError("duplicate functional outcome")
            receipt = row.get("first_receipt") or {}
            completed[name] = {"case": name, "layout_seed": row["case"].get("layout_seed"),
                "episode": row["case"]["episode"],
                "registered_layout_state": row["case"].get("registered_layout_state"),
                "state_sha256": row["case"]["state_sha256"],
                "official_on_subtask_success": row.get("official_subtask_success"),
                "public_placement_verdict": row.get("public_placement_verdict"),
                "native_original_success": result.get("official_success"),
                "verification": receipt.get("verification"), "failure_reason": receipt.get("failure_reason"),
                "executed": receipt.get("executed"), "chunks": receipt.get("chunks"),
                "stop": receipt.get("stop"), "wall_s": row.get("wall_s"),
                "native_stop_enabled": row.get("server_chunk_execution", {}).get("native_success_stops_chunk"),
                "requested_controls": row.get("server_chunk_execution", {}).get("requested_controls"),
                "ledger": ref(ledger), "line": number, "output_dir": row["output_dir"]}
    matrix = Counter()
    for row in completed.values():
        truth, public = row["official_on_subtask_success"], row["public_placement_verdict"]
        if not isinstance(truth, bool):
            matrix["truth_unknown"] += 1
        elif not isinstance(public, bool):
            matrix["public_unmeasured"] += 1
        else:
            matrix[("tp" if public else "fn") if truth else ("fp" if public else "tn")] += 1
    success = sum(row["official_on_subtask_success"] is True for row in completed.values())
    known = sum(isinstance(row["official_on_subtask_success"], bool) for row in completed.values())
    args.output.mkdir(parents=True, exist_ok=False)
    ledger = args.output / "attempts.jsonl"
    ledger.write_text("".join(json.dumps(row) + "\n" for row in completed.values()))
    report = {"planned": 100, "completed": len(completed), "pending": 100-len(completed),
              "on_successes": success, "known_truth": known,
              "success_over_registered": success / 100 if len(completed) == 100 else None,
              "observed_success_over_completed": success / len(completed) if completed else None,
              "wilson95_known_truth": wilson(success, known),
              "truth_unknown": len(completed)-known, "confusion": dict(matrix),
              "verifier_precision": matrix["tp"]/(matrix["tp"]+matrix["fp"]) if matrix["tp"]+matrix["fp"] else None,
              "verifier_recall": matrix["tp"]/(matrix["tp"]+matrix["fn"]) if matrix["tp"]+matrix["fn"] else None,
              "agreement_over_known_truth": (matrix["tp"]+matrix["tn"])/known if known else None,
              "binding_no_execution": sum(row["executed"] is False for row in completed.values()),
              "failure_reasons": dict(Counter(str(row["failure_reason"]) for row in completed.values())),
              "stops": dict(Counter(str(row["stop"]) for row in completed.values())),
              "references": references, "generator": ref(Path(__file__)), "attempts": ref(ledger),
              "infrastructure_attempts": infrastructure, "selection_only": True,
              "truth_label": "saved original On subpredicate after transfer; native success separate",
              "unknowns_retained_in_registered_denominator": True, "training_allowed": False,
              "internal_gate_not_evaluated_on_selection": True}
    manifest = args.output / "manifest.json"
    manifest.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("completed", "pending", "on_successes", "known_truth",
                       "confusion", "binding_no_execution", "agreement_over_known_truth")}))
    print(json.dumps(ref(manifest)))


if __name__ == "__main__":
    main()
