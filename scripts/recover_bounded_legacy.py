"""Collect saved legacy physical outcomes without rerunning or changing them.

The old wrapper exited on NoLegalCandidate after the historical harness had
already written result.json in finally. These saved failures stay failures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def recover(roots):
    rows = []
    for root in roots:
        for payload_path in sorted(root.glob("*/legacy_payload.json")):
            payload = json.loads(payload_path.read_text())
            result_path = payload_path.parent/"legacy/result.json"
            if not result_path.is_file():
                continue
            result = json.loads(result_path.read_text())
            if "official_success" not in result or result.get("infrastructure_failure"):
                continue
            if result.get("status") != "completed" and result.get("termination_category") != "no_legal_candidate":
                continue
            source = Path(payload["source"])
            budget = payload_path.parent/"legacy_result.json"
            wrapper = json.loads(budget.read_text()) if budget.is_file() else {}
            rows.append({"case": payload["case"], "arm": "v5_expert", "status": "physical_result",
                "success": bool(result["official_success"]), "decisions": result.get("decisions"),
                "wall_s": result.get("wall_s"),
                "sim_steps": wrapper.get("public_execution_budget", {}).get("used_sim_steps"),
                "failure_phase": result.get("termination_category"), "legacy_error": result.get("error"),
                "legacy_source": str(source), "source_files": [
                    {"path": str(source/name), "sha256": hashlib.sha256((source/name).read_bytes()).hexdigest()}
                    for name in ("harness_v5_eval.py", "robots/libero/v5_runtime.py", "robots/libero/v5_state.py", "robots/libero/v5_oracle_policy.py")],
                "recovered_from": {"path": str(result_path), "sha256": hashlib.sha256(result_path.read_bytes()).hexdigest()},
                "training": False})
    identities = [(r["case"]["name"], r["arm"]) for r in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("recovery inputs contain duplicate physical trials")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = recover(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row)+"\n")
    print(json.dumps({"n": len(rows), "success": sum(r["success"] for r in rows), "no_reruns": True}))


if __name__ == "__main__":
    main()
