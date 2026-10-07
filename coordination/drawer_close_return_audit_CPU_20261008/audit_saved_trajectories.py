"""Count already-attained endpoints lost later using explicit original ledgers."""

import argparse
import ast
from collections import Counter
import hashlib
import json
from math import sqrt
from pathlib import Path


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(reference):
    path = Path(reference["path"])
    if identity(path)["sha256"] != reference["sha256"]:
        raise ValueError(f"Pinned original input changed: {path}")
    return path


def wilson(k, n):
    z = 1.959963984540054
    centre = (k/n + z*z/(2*n))/(1+z*z/n)
    half = z*sqrt(k/n*(1-k/n)/n + z*z/(4*n*n))/(1+z*z/n)
    return [centre-half, centre+half]


def status(score):
    return (score.get("label") or {}).get("satisfied")


def method_identity(reference, name):
    path = pinned(reference)
    text = path.read_text()
    tree = ast.parse(text)
    node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
    code = "\n".join(text.splitlines()[node.lineno-1:node.end_lineno]) + "\n"
    return {"source": identity(path), "entry": name, "line": node.lineno,
            "function_sha256": hashlib.sha256(code.encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = json.loads(args.inputs.read_text())
    records, summaries = [], []
    for run in inputs["runs"]:
        plan = json.loads(pinned(run["manifest"]).read_text())
        registered = {case["name"]: case for case in plan["cases"]}
        runtime = method_identity(run["runtime"], "drawer_public_stop")
        pinned(run["verifier"])
        counters = {kind: Counter() for kind in ("drawer_open", "drawer_close")}
        seen = set()
        for reference in run["original_ledgers"]:
            path = pinned(reference)
            for number, line in enumerate(path.read_text().splitlines(), 1):
                raw = json.loads(line)
                case, first = raw["case"], raw["first_attempt"]
                if case["name"] not in registered or case["name"] in seen:
                    raise ValueError("Original row missing or duplicated in the registered plan")
                seen.add(case["name"])
                if case["state_sha256"] != registered[case["name"]]["state_sha256"]:
                    raise ValueError("Original row has another registered state")
                scores = first["contact_evidence"]["private_fixture_scores"]
                if any(s["source"] != "simulation_diagnostic_only" or s["used_for_control"] for s in scores):
                    raise ValueError("Private diagnostics were used for runtime control")
                chunks = [s for s in scores if s["phase"] == "after_actual_chunk"]
                true = [s["chunk"] for s in chunks if status(s) is True]
                losses = [{"chunk_0based": s["chunk"], "previous_qpos": chunks[i-1]["label"]["joint_qpos"],
                           "current_qpos": s["label"]["joint_qpos"]}
                          for i, s in enumerate(chunks) if i and status(chunks[i-1]) is True and status(s) is False]
                phases = ["after_public_stop_before_recovery", "after_fixture_release",
                          "after_measured_contact_clearance", "after_view_retreat_attempt"]
                phase_status = {phase: [status(s) for s in scores if s["phase"] == phase] for phase in phases}
                previous = status(chunks[-1]) if chunks else None
                recovery_losses = []
                for phase in phases:
                    for score in [s for s in scores if s["phase"] == phase]:
                        if previous is True and status(score) is False:
                            recovery_losses.append(phase)
                        previous = status(score)
                final = first["private_after"]["satisfied"]
                samples = first.get("verification_measurements", {}).get("drawer_public_stop", [])
                public = [{"after_chunks": s["chunk"], "verified": s["verified"],
                           "private_requested_endpoint_at_same_saved_chunk": status(chunks[s["chunk"]-1]),
                           "signed_extension_m": s["evidence"].get("measured_signed_extension_m"),
                           "reason": s["evidence"].get("reason"),
                           "source_step": s["measurement"].get("source_step")}
                          for s in samples]
                public_stop = first["receipt"].get("stop") == "measured_fixture_endpoint"
                category = ("final_endpoint_retained" if final else "never_attained_requested_endpoint" if not true
                            else "endpoint_lost_during_contact" if losses else
                            "endpoint_lost_" + recovery_losses[0] if recovery_losses else "endpoint_loss_unlocalized")
                g = counters[case["type"]]
                g["registered_trials"] += 1
                g["ever_attained_endpoint"] += bool(true)
                g["final_endpoint_true"] += bool(final)
                g["contact_true_to_false_cases"] += bool(losses)
                g["contact_true_to_false_events"] += len(losses)
                g["post_contact_true_to_false_cases"] += bool(recovery_losses)
                g["any_saved_endpoint_loss_cases"] += bool(losses or recovery_losses)
                g["public_stop_cases"] += public_stop
                g["stop_already_false_cases"] += bool(public_stop and chunks and status(chunks[-1]) is False)
                g[category] += 1
                records.append({"job": run["job"], "case": case["name"], "episode": case["episode"],
                                "type": case["type"], "registered_state_sha256": case["state_sha256"],
                                "raw_ledger": reference, "raw_line_1based": number,
                                "first_true_chunk_0based": true[0] if true else None,
                                "actual_chunks": len(chunks),
                                "chunks_after_first_attained_endpoint": len(chunks)-true[0]-1 if true else None,
                                "contact_endpoint_loss_events": losses,
                                "recovery_endpoint_loss_phases": recovery_losses,
                                "stage_status": phase_status, "public_samples": public,
                                "public_stop": public_stop, "final_endpoint_true": final,
                                "failure_category": category,
                                "registered_prompt": case["subtask_prompt"],
                                "post_contact_recovery": first["receipt"].get("post_contact_recovery"),
                                "receipt_stop": first["receipt"].get("stop")})
        if seen != set(registered):
            raise ValueError("Every original registered row must be retained")
        groups = {}
        for kind, values in counters.items():
            n = values["registered_trials"]
            groups[kind] = {**values,
                            "final_endpoint_Wilson95": wilson(values["final_endpoint_true"], n),
                            "saved_endpoint_loss_Wilson95": wilson(values["any_saved_endpoint_loss_cases"], n)}
        summaries.append({"job": run["job"], "manifest": run["manifest"],
                          "original_ledgers": run["original_ledgers"],
                          "public_stop_function": runtime, "by_type": groups,
                          "reused_formal_report": run["existing_formal_report"],
                          "reused_stage_evidence": run["existing_stage_evidence"]})
    evidence = args.output / "per_trial.jsonl"
    evidence.write_text("".join(json.dumps(row) + "\n" for row in records))
    report = {"scope": "Same20 original development selection paired across4319 and4327, not40 independent states",
              "inputs": identity(args.inputs), "producer": identity(__file__), "runs": summaries,
              "per_trial": identity(evidence), "sample_count": len(records), "new_physics": 0,
              "GPU_started": False, "private_used_for_control": False, "source_modified": False,
              "limitations": ["Labels only at the end of each5-control chunk and named recovery phases; intra-chunk transient losses remain unknown.",
                              "Release EEF trajectories were not saved; first saved loss phase does not establish a contact cause.",
                              "Selection records and their failures retained; this audit does not establish independent qualification."]}
    output = args.output / "report.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": identity(output), "runs": summaries}, indent=2))


if __name__ == "__main__":
    main()
