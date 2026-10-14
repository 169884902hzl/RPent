"""Summarize separately recorded v3r9 diagnostics without dropping nulls."""
import argparse
from collections import Counter
import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics


def pin(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def metric(k, n):
    if not n:
        return {"k": k, "n": n, "rate": None, "wilson95": None}
    p, z = k / n, 1.959963984540054
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"k": k, "n": n, "rate": p, "wilson95": [center - half, center + half]}


def confusion(rows, key):
    known = [r for r in rows if type(r[key]) is bool]
    paired = [r for r in known if type(r["public"]) is bool]
    counts = {name: sum(r[key] is a and r["public"] is b for r in paired)
              for name, a, b in [("tp", True, True), ("tn", False, False),
                                  ("fp", False, True), ("fn", True, False)]}
    correct = counts["tp"] + counts["tn"]
    return {**counts, "agreement_including_public_null": metric(correct, len(known)),
            "agreement_all_registered": metric(correct, len(rows)),
            "known_pair_agreement_secondary": metric(correct, len(paired)),
            "public_null_on_known_truth": len(known) - len(paired),
            "truth_unknown": len(rows) - len(known),
            "false_positive_rate": metric(counts["fp"], sum(r[key] is False for r in known)),
            "false_negative_rate": metric(counts["fn"], sum(r[key] is True for r in known))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("parent", type=Path)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    submitted = json.loads(args.submission.read_text())
    if "runs" in submitted:
        matches = [r for r in submitted["runs"] if Path(r["output"]) == args.parent]
        if len(matches) != 1:
            raise ValueError("submission must identify one exact run")
        submitted = matches[0]
    plan_path = Path(submitted["plan"]["path"])
    plan = json.loads(plan_path.read_text())
    if pin(plan_path)["sha256"] != submitted["plan"]["sha256"]:
        raise ValueError("plan changed")
    source = Path(plan["source_path"])
    truth_source = source / "robots/libero/v5_grasp_truth.py"
    registered = {c["name"] for c in plan["cases"]}
    rows, inputs = [], []
    for origin, job in [("startup", str(submitted["startup_job"]).split(";")[0]),
                        ("formal", str(submitted["formal_job"]).split(";")[0])]:
        for path in sorted((args.parent / f"job{job}").glob("part*/probe/episodes.jsonl")):
            data = path.read_bytes()
            input_pin = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}
            inputs.append({**input_pin, "origin": origin})
            for line_no, line in enumerate(data.splitlines(), 1):
                if not line.strip():
                    continue
                raw = json.loads(line)
                case = raw["case"]
                first = raw.get("first_attempt") or {}
                receipt = first.get("receipt") or {}
                truth = first.get("private_hold_truth_v3") or {}
                checks = truth.get("checks") or []
                reasons = sorted({c["unknown_reason"] for c in checks if c.get("unknown_reason")})
                failed = Counter()
                for c in checks:
                    if c.get("qualifies") is not False:
                        continue
                    if c.get("clearance_m", .03) < .03:
                        failed["lift_below_3cm"] += 1
                    if c.get("dual_finger_contact") is False:
                        failed["missing_dual_finger_contact"] += 1
                    if c.get("relative_com_displacement_m", 0) > .01:
                        failed["relative_tcp_slip_over_1cm"] += 1
                    if c.get("counterfactual_load_bearing_support") is True:
                        failed["external_load_bearing_support"] += 1
                public = receipt.get("grasp_verified")
                rows.append({"origin": origin, "input": str(path), "input_sha256": input_pin["sha256"],
                    "line": line_no, "row_sha256": hashlib.sha256(line).hexdigest(),
                    "case": case["name"], "method": case.get("condition"),
                    "category": case.get("object_category"), "type": case.get("type"),
                    "layout_seed": case.get("layout_seed"),
                    "state_sha256": raw.get("registered_state_sha256", case.get("state_sha256")),
                    "legacy": first.get("private_true_sustained_grasp"),
                    "exclusive_v2": (first.get("private_hold_truth_v2") or {}).get("success"),
                    "registered_v3": truth.get("success"), "unknown_reasons": reasons,
                    "failed_predicate_frames": dict(failed),
                    "public": public if type(public) is bool else None,
                    "public_raw": receipt.get("verification"), "failure_reason": receipt.get("failure_reason"),
                    "infrastructure_failure": bool(raw.get("infrastructure_failure")),
                    "physically_executed": first.get("physically_executed"),
                    "wall_s": raw.get("case_wall_s", raw.get("wall_s")),
                    "training_allowed": False, "new_diagnostic_replay": True})
    names = [r["case"] for r in rows]
    if len(names) != len(set(names)) or set(names) - registered:
        raise ValueError("duplicate/unregistered case; do not choose a preferred attempt")
    missing = sorted(registered - set(names))
    summary = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "registration_id": "grasp_truth_v3_1153_20261009", "classification": "new_diagnostic_replay_not_independent_confirmation",
        "qualification_allowed": False, "registered_n": len(registered), "recorded_n": len(rows),
        "missing_cases": missing, "complete": not missing, "plan": pin(plan_path),
        "submission": pin(args.submission),
        "source_identity": pin(source / "source_identity_v3r9.json"), "truth_source": pin(truth_source),
        "summary_source": pin(Path(__file__)), "inputs": inputs,
        "counts": {key: dict(Counter(str(r[key]) for r in rows))
                   for key in ("origin", "registered_v3", "exclusive_v2", "legacy", "public", "failure_reason")},
        "registered_v3_success_registered_denominator": metric(sum(r["registered_v3"] is True for r in rows), len(registered)),
        "registered_v3_verifier": confusion(rows, "registered_v3"),
        "legacy_verifier": confusion(rows, "legacy"),
        "unknown_reasons": dict(Counter(x for r in rows for x in r["unknown_reasons"])),
        "failed_predicate_cases": dict(Counter(x for r in rows for x in r["failed_predicate_frames"])),
        "median_wall_s": statistics.median(r["wall_s"] for r in rows if isinstance(r["wall_s"], (int, float))) if rows else None,
        "old_records_unchanged": True, "training_allowed": False}
    args.output.mkdir(exist_ok=False, parents=True)
    (args.output / "rows.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("inputs",)}, indent=2))


if __name__ == "__main__":
    main()
