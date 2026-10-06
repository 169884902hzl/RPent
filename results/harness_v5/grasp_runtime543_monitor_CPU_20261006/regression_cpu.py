"""Pure synthetic ledger checks; no simulation or model execution."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts/summarize_v5_grasp543_20261006.py"
spec = importlib.util.spec_from_file_location("summary543", SCRIPT)
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def fixture(root, cohort="independent_confirmation_synthetic", count=1, repeated=False):
    cases = [{"name": f"synthetic_{index}", "condition": "test", "group": "frypan",
              "state_sha256": hashlib.sha256(str(0 if repeated else index).encode()).hexdigest(),
              "episode": {"suite": "libero_90", "task": 18, "seed": index},
              "private_original_goal_predicates": [["on", "target", "stove"]]}
             for index in range(count)]
    plan = {"cohort": cohort, "cases": cases, "conditions": {"test": {}}}
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(plan))
    return manifest, summary.sha(manifest), cases


def attempt(case, output, index=0, physical=True, truth=True, verdict=True, infra=False):
    receipt = {"executed": physical, "grasp_verified": verdict, "stop": "synthetic"}
    return {"case": copy.deepcopy(case), "output_dir": str(output / case["name"]),
            "attempt_index": index, "first_receipt": receipt,
            "physical_execution_observed": physical, "true_sustained_grasp": truth,
            "visual_verified": verdict is True,
            "infrastructure_error": "TimeoutError(synthetic)" if infra else None,
            "case_had_infrastructure_failure": infra, "result": {"status": "synthetic"}}


def ledger(root, filename, rows):
    root.mkdir(parents=True, exist_ok=True)
    path = root / filename
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


checks = []
with tempfile.TemporaryDirectory(prefix="grasp543_synthetic_") as temp:
    base = Path(temp)

    root = base / "postphysics"
    root.mkdir()
    manifest, digest, cases = fixture(root)
    first = attempt(cases[0], root / "run", truth=None, infra=True)
    first["error_stage"] = "private_metrology"
    first["first_receipt"] = {}
    first["public_receipt_before_private_metrology"] = {"executed": True, "grasp_verified": True}
    first["visual_verified"] = False
    better = attempt(cases[0], root / "run", index=1)
    episodes = ledger(root / "run", "episodes.jsonl", [better])
    infrastructure = ledger(root / "run", "infrastructure_attempts.jsonl", [first])
    report, selected, roles = summary.summarize([manifest], [digest],
                                              [("episodes", episodes), ("infrastructure", infrastructure)])
    assert selected[0]["sustained_posttrial_grasp"] is None
    assert selected[0]["public_grasp_verdict"] is True
    assert roles[1]["role"] == "development_physical_repeat"
    assert report["retry_policy_violations"]
    checks.append("postphysics_unknown_retained_not_replaced_by_later_success")

    root = base / "recovered"
    root.mkdir()
    manifest, digest, cases = fixture(root)
    failed = attempt(cases[0], root / "run", physical=False, truth=None, infra=True)
    retry = attempt(cases[0], root / "run", index=1)
    retry["case_had_infrastructure_failure"] = True
    infrastructure = ledger(root / "run", "infrastructure_attempts.jsonl", [failed])
    episodes = ledger(root / "run", "episodes.jsonl", [retry])
    events = ledger(root, "infrastructure_cases.jsonl", [
        {"case": cases[0]["name"], "manifest_sha256": digest, "planned_cases": 1,
         "infrastructure_failure": True},
        {"case": cases[0]["name"], "manifest_sha256": digest, "planned_cases": 1,
         "infrastructure_failure": False}])
    report, selected, roles = summary.summarize([manifest], [digest],
        [("episodes", episodes), ("infrastructure", infrastructure), ("infrastructure", events)])
    infra = report["infrastructure_by_manifest"][digest]
    assert len(selected) == 1 and selected[0]["attempt_index"] == 1
    assert infra["unique_affected_cases"] == 1 and infra["recovered_cases"] == [cases[0]["name"]]
    assert infra["retry_invocations"] == 1 and not report["retry_policy_violations"]
    checks.append("prephysics_once_retry_retains_infrastructure_fault_after_recovery")

    root = base / "subtask"
    root.mkdir()
    manifest, digest, cases = fixture(root)
    row = attempt(cases[0], root / "run", truth=False)
    row["private_original_task_status_after"] = {
        "goals": [["on", "target", "stove"]], "satisfied": [True], "done": True}
    episodes = ledger(root / "run", "episodes.jsonl", [row])
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes)])
    assert selected[0]["official_on_subtask_success"] is True
    assert selected[0]["official_original_task_done"] is True
    assert selected[0]["sustained_posttrial_grasp"] is False
    assert selected[0]["sustained_during_complete_subtask"] is None
    checks.append("official_On_success_does_not_replace_sustained_grasp_truth")

    root = base / "unmeasured"
    root.mkdir()
    manifest, digest, cases = fixture(root)
    row = attempt(cases[0], root / "run", verdict=None)
    episodes = ledger(root / "run", "episodes.jsonl", [row])
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes)])
    metrics = next(iter(report["by_manifest_condition_group"].values()))
    assert sum(metrics["confusion"].values()) == 0 and metrics["confusion"]["fn"] == 0
    assert metrics["known_truth_public_unmeasured"] == 1
    assert metrics["verifier_agreement"]["best_case_rate"] == 1
    checks.append("null_public_verdict_stays_unmeasured_not_FN")

    root = base / "selection"
    root.mkdir()
    manifest, digest, cases = fixture(root, "original_method_selection_correlated_resets", 100, True)
    episodes = ledger(root / "run", "episodes.jsonl", [attempt(case, root / "run") for case in cases])
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes)])
    metrics = next(iter(report["by_manifest_condition_group"].values()))
    assert metrics["planned_correlated_repeat_requests"] == 99
    assert metrics["analysis_roles"] == ["selection"]
    assert not metrics["distinct_registered_confirmation_states"]
    assert metrics["single_class_threshold_evidence"] is None
    checks.append("correlated_selection_resets_are_not_independent_confirmation")

    root = base / "unknown_coverage"
    root.mkdir()
    manifest, digest, cases = fixture(root, count=100)
    rows = [attempt(case, root / "run") for case in cases]
    rows[-1]["true_sustained_grasp"] = None
    rows[0]["first_receipt"]["grasp_verified"] = False
    episodes = ledger(root / "run", "episodes.jsonl", rows)
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes)])
    metrics = next(iter(report["by_manifest_condition_group"].values()))
    assert metrics["truth_coverage"]["unknown_after_physics"] == 1
    assert metrics["physical_success"]["worst_case_rate"] == .99
    assert metrics["verifier_agreement"]["worst_case_rate"] == .98
    assert metrics["single_class_threshold_evidence"] == "supported_by_worst_case_bounds"
    assert report["full_six_class_qualification"] == "not_evaluated"
    checks.append("unknown_outcome_does_not_add_100_percent_truth_coverage_gate")

    try:
        summary.summarize([manifest], ["0" * 64], [])
    except ValueError as error:
        assert "SHA mismatch" in str(error)
    else:
        raise AssertionError("changed manifest accepted")
    checks.append("manifest_identity_is_pinned")

result = {"synthetic_data_only": True, "checks": checks, "passed": len(checks),
          "summary_script_sha256": summary.sha(SCRIPT), "python": sys.executable,
          "new_physical_trials": 0, "new_training_rows": 0}
(Path(__file__).parent / "regression_results.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
