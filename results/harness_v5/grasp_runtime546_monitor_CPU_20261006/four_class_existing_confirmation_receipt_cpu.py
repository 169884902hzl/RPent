"""Merge existing pinned confirmation evidence; no labels or physics rerun."""

import hashlib
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


BASE = Path(sys.argv[1])
OUT = Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("grasp_summary", BASE / "scripts/summarize_v5_grasp543_20261006.py")
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)
inputs = []


def pinned(relative, digest, jsonl=False):
    path = BASE / relative
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        raise ValueError(f"pinned evidence changed: {path}")
    inputs.append({"path": str(path), "sha256": actual})
    return ([json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            if jsonl else json.loads(path.read_text()))


canonical = pinned("results/harness_v5/grasp492_first4_confirmation_20261005/preparation/full.json",
                   "dfa8c31e0568d52e9ffb19ca4d7d338284eb08460aa6424e523d9fe012a67ac9")
existing = pinned("results/harness_v5/grasp_complete3616_3619_CPU_20261005/report/report.json",
                  "37d95fd22d585774ad9895a48c45723ac264b3186e658d373159373db9de13e0")
receipt = pinned("results/harness_v5/grasp_runtime542_preflight_CPU_20261006/receipt_final.json",
                 "01b4574cff2211d660d8b4e87d8ee5e678afb0e88bd8c1fbb3f03a5d519f15a3")
box_mug = pinned("results/harness_v5/grasp_runtime542_preflight_CPU_20261006/first_physical_cases_final.jsonl",
                 "bf3d04442f9494d31ee6a5b890ebbfd3ff8636a27868b7f2c002836cefcb2add", True)
meta = pinned("results/harness_v5/grasp492_first4_confirmation_20261005/full_job3619/part3/episodes.jsonl",
              "5f3cb5b1fc393ebab232c09c7739d9933f560fbd55045e14c286d36f2d9805b9", True)
binding = pinned("results/harness_v5/grasp502_mug_meta_retry_20261005/retry_job3628/part3/episodes.jsonl",
                 "0c5ee547ac9bb6e1f79894774e29b509c033c0941a1aca182785ab734aec4906", True)
source_by_job = {
    "3619": "source_v5_grasp492_first4_confirmation_20261005",
    "3636": "source_v5_grasp510_box_remaining_20261005",
    "3631": "source_v5_grasp507_mug_private_binding_retry_20261005",
    "3642": "source_v5_grasp512_mug_unvisited_resume_20261005",
}
planned = {case["name"]: case for case in canonical["cases"]}
first = []
for row in existing["records"]:
    if row["arm_kind"] != "confirmation" or row["class"] not in ("bottle", "bowl"):
        continue
    first.append({"case": row["trial_name"], "group": row["class"], "state_sha256": row["state_sha256"],
                  "job": row["job"], "source_stratum": source_by_job["3619"],
                  "truth": row["truth"], "verifier": row["visual"], "infrastructure_failure": False,
                  "input": {"path": row["ledger"], "line": row["ledger_line"]}})
for row in box_mug:
    first.append({"case": row["case"], "group": row["group"], "state_sha256": row["state_sha256"],
                  "job": row["job"], "source_stratum": source_by_job[row["job"]],
                  "truth": row["true_sustained_grasp"],
                  "verifier": row.get("final_public_verifier_receipt_value")
                              if row["final_public_verifier_receipt_available"] else None,
                  "raw_exported_visual_verified": row["visual_verified"],
                  "infrastructure_failure": any(marker in (row.get("raised_error") or "")
                                                for marker in summary.INFRASTRUCTURE_MARKERS),
                  "input": row["input"]})
assert len(first) == len(planned) == 400 and len({row["case"] for row in first}) == 400
for row in first:
    case = planned[row["case"]]
    assert (row["group"], row["state_sha256"]) == (case["group"], case["state_sha256"])

prephysics = []
for kind, rows, source, job in (("zero_physics_infrastructure", meta, source_by_job["3619"], "3619_3"),
                               ("zero_physics_private_binding_development_error", binding,
                                "source_v5_grasp502_mug_meta_retry_20261005", "3628_3")):
    for row in rows:
        assert row["case"] == planned[row["case"]["name"]] and not summary.physically_executed(row)
        prephysics.append({"case": row["case"]["name"], "group": row["case"]["group"],
                           "source_stratum": source, "job": job, "role": kind,
                           "infrastructure_failure": summary.infrastructure_failure(row),
                           "error": row.get("raised_error") or (row.get("first_receipt") or {}).get("error")})


def metrics(rows, extra):
    n = len(rows)
    known = sum(row["truth"] is not None for row in rows)
    confusion = Counter({key: 0 for key in ("TP", "TN", "FP", "FN")})
    for row in rows:
        truth, verdict = row["truth"], row["verifier"]
        if truth is not None and verdict is not None:
            confusion["TP" if truth and verdict else "FN" if truth else "FP" if verdict else "TN"] += 1
    paired = sum(confusion.values())
    faults = {row["case"] for row in [*rows, *extra] if row["infrastructure_failure"]}
    return {"first_physical": n, "unique_state_sha256": len({row["state_sha256"] for row in rows}),
            "truth_success": sum(row["truth"] is True for row in rows),
            "truth_failure": sum(row["truth"] is False for row in rows), "truth_unknown": n-known,
            "physical_success": summary.bounded_metric(sum(row["truth"] is True for row in rows), known, n),
            "confusion": dict(confusion), "verifier_unmeasured": sum(row["verifier"] is None for row in rows),
            "paired_truth_and_verifier": paired,
            "verifier_agreement": summary.bounded_metric(confusion["TP"]+confusion["TN"], paired, n),
            "infrastructure_unique_affected_cases": len(faults), "infrastructure_affected_cases": sorted(faults),
            "postphysical_infrastructure_invocations": sum(row["infrastructure_failure"] for row in rows),
            "prephysical_infrastructure_invocations": sum(row["infrastructure_failure"] for row in extra),
            "prephysical_private_binding_development_errors": sum(row["role"].endswith("development_error") for row in extra)}


classes = {}
for group in ("bottle", "bowl", "box", "mug"):
    rows = [row for row in first if row["group"] == group]
    extra = [row for row in prephysics if row["group"] == group]
    assert len(rows) == len({row["state_sha256"] for row in rows}) == 100
    classes[group] = metrics(rows, extra)
    classes[group]["infrastructure_rate_over_registered_100"] = classes[group]["infrastructure_unique_affected_cases"]/100
strata = defaultdict(list)
for row in first:
    strata[(row["group"], row["source_stratum"])].append(row)
for row in prephysics:
    strata.setdefault((row["group"], row["source_stratum"]), [])
report = {"scope": "existing first-four-class canonical confirmation receipt; reuse pinned formal labels, no physics or truth re-evaluation",
          "canonical_manifest": inputs[0], "reused_formal_reports": inputs[1:4], "inputs": inputs,
          "producer": {"path": str(Path(__file__).resolve()), "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
          "by_class": classes,
          "by_class_source": {f"{group}/{source}": metrics(rows, [row for row in prephysics
                                if row["group"] == group and row["source_stratum"] == source])
                              for (group, source), rows in sorted(strata.items())},
          "all_four_descriptive": metrics(first, prephysics),
          "box_resume": {"first_prefix": 48, "remaining_original_registered": 52},
          "mug_resume": {"first_prefix": 21, "remaining_original_registered": 79},
          "unknown_policy": "two postphysics metrology-unknown cases retained; unavailable final receipts remain null; no false/FN replacement",
          "infrastructure_policy": "RPC/env-meta markers counted by unique canonical case and OR retained after recovery; zero-motion private-binding ValueError shown separately",
          "source_scope": "old first-grasp recipes and verifiers only; do not inherit new runtime, independent-verifier, public-pose-return or SOURCE545/546 qualification",
          "interval_scope": "Wilson is descriptive over known labels only; point bounds use all first physical cases; no 100-percent truth coverage admission gate",
          "qualification_authorized": False, "full_six_class_qualification": "not_evaluated",
          "new_physical_trials": 0, "new_model_calls": 0, "new_training_rows": 0}
for arm in existing["arms"]:
    if arm["arm_kind"] == "confirmation":
        actual = classes[arm["class"]]
        assert actual["truth_success"] == arm["truth_success"]
        assert actual["confusion"] == {key: arm["confusion"][key] for key in ("TP", "TN", "FP", "FN")}
for group in receipt["first_physical_confirmation_summary"]:
    assert classes[group["group"]]["truth_success"] == group["physical_truth_successes"]
    assert classes[group["group"]]["confusion"] == group["confusion"]
OUT.mkdir(parents=True, exist_ok=False)
(OUT/"report.json").write_text(json.dumps(report, indent=2)+"\n")
(OUT/"first_physical_cases.jsonl").write_text("".join(json.dumps(row)+"\n" for row in first))
(OUT/"zero_physics_attempts.jsonl").write_text("".join(json.dumps(row)+"\n" for row in prephysics))
print(json.dumps({"report": str(OUT/"report.json"), "sha256": hashlib.sha256((OUT/"report.json").read_bytes()).hexdigest(),
                  "by_class": classes, "source_counts": {key: value["first_physical"] for key,value in report["by_class_source"].items()}}, indent=2))
