"""Confirmation gates require pinned unseen states and executed physical records."""

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

from scripts import summarize_v5_grasp497_confirmation as summary


def digest(key):
    return hashlib.sha256(json.dumps(key).encode()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value) + "\n")


def write_ledger(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


@pytest.fixture
def package_factory(tmp_path, monkeypatch):
    def make(change_cases=None):
        prior_key = ("libero_goal", 0, 0)
        cases = []
        for group_id, group in enumerate(summary.GROUPS):
            for index in range(100):
                key = ("libero_90", group_id * 10 + index // 30, 10 + index % 30)
                cases.append({"name": f"{group}_{index}", "group": group, "category": group,
                              "episode": dict(zip(("suite", "task", "seed"), key)),
                              "state_sha256": digest(key), "source": "official_original_LIBERO90"})
        if change_cases:
            change_cases(cases, prior_key)
        prior = tmp_path / "discovery.json"
        write_json(prior, {"cases": [{"episode": dict(zip(("suite", "task", "seed"), prior_key))}]})
        pool_path = tmp_path / "pool.json"
        pool = {"source_manifest": {"path": str(prior), "sha256": summary.sha(prior)},
                "prior_cases": 1, "cases": cases}
        write_json(pool_path, pool)
        pool_sha = summary.sha(pool_path)
        monkeypatch.setattr(summary, "POOL_SHA", pool_sha)
        validated_states, verified_assets = [], []
        def state_sha_for(*key):
            validated_states.append(key)
            return digest(key)
        monkeypatch.setattr(summary, "make_official_state_validator", lambda value:
                            (state_sha_for, lambda case: verified_assets.append(case["name"])))
        manifest_paths, ledger_paths, all_rows = [], [], []
        for part, groups in enumerate((summary.GROUPS[:4], ("frypan",), ("moka_pot",))):
            chosen = [{**copy.deepcopy(case), "condition": "confirm_" + case["group"]}
                      for case in cases if case["group"] in groups]
            manifest = tmp_path / f"manifest{part}.json"
            write_json(manifest, {"cohort": "independent_confirmation_test",
                                  "pool_manifest": {"path": str(pool_path), "sha256": pool_sha},
                                  "conditions": {"confirm_" + group: {} for group in groups},
                                  "frozen_class_recipes": {group: "fixed_before_execution" for group in groups},
                                  "cases": chosen})
            rows = []
            for case in chosen:
                directory = tmp_path / "episodes" / case["name"]
                directory.mkdir(parents=True)
                choices = directory / "choices.jsonl"
                choices.write_text('{"selected":"grasp","receipt":{"executed":true}}\n')
                rows.append({"case": case, "output_dir": str(directory), "choices_sha256": summary.sha(choices),
                             "true_sustained_grasp": True, "visual_verified": True,
                             "grasp_attempted": True, "executed_vla_actions": 55,
                             "contact_prompt": "pick up the selected object",
                             "rpent_pick_result": {"chunks_used": 11}, "first_receipt": {"tool": "grasp"}})
            ledger = tmp_path / f"ledger{part}.jsonl"
            write_ledger(ledger, rows)
            manifest_paths.append(manifest)
            ledger_paths.append(ledger)
            all_rows.append(rows)
        return {"pool": pool_path, "manifests": manifest_paths, "ledgers": ledger_paths, "rows": all_rows,
                "validated_states": validated_states, "verified_assets": verified_assets}
    return make


def evaluate(package, manifests=None, ledgers=None):
    return summary.summarize_confirmation(package["pool"], manifests or package["manifests"],
                                          ledgers or package["ledgers"])


def test_complete_six_class_confirmation_passes_pinned_state_and_record_audit(package_factory):
    package = package_factory()
    report = evaluate(package)
    assert report["qualification_authorized"] is True
    assert report["qualification_passed"] is True
    assert report["overall"]["recorded"] == 600
    assert report["overall"]["contact_executed"] == 600
    assert len(package["validated_states"]) == 601
    assert package["verified_assets"]
    assert report["qualification_reasons"] == []
    for group in summary.GROUPS:
        assert report["class_state_audits"][group]["unique_raw_state_hashes"] == 100
        assert report["by_class"][group]["wilson_95CI"] == summary.wilson(100, 100)


def test_four_class_package_reports_results_without_full_gate_authorization(package_factory):
    package = package_factory()
    report = evaluate(package, manifests=package["manifests"][:1], ledgers=package["ledgers"][:1])
    assert report["complete"] is True
    assert report["overall"]["true_successes"] == 400
    assert report["qualification_authorized"] is False
    assert report["qualification_passed"] is False
    assert report["by_class"]["frypan"]["true_success_rate"] is None


@pytest.mark.parametrize("problem", ["missing_trial", "missing_ledger", "unknown_truth", "no_contact", "infra", "missing_choices"])
def test_unfinished_or_unverified_confirmation_is_not_qualified(package_factory, problem):
    package = package_factory()
    row = package["rows"][0][0]
    if problem == "missing_trial":
        package["rows"][0].pop(0)
    elif problem == "missing_ledger":
        package["ledgers"][2].unlink()
    elif problem == "unknown_truth":
        row["true_sustained_grasp"] = None
    elif problem == "no_contact":
        row["executed_vla_actions"] = 0
    elif problem == "infra":
        row["raised_error"] = "RPC connection failed"
    elif problem == "missing_choices":
        (Path(row["output_dir"]) / "choices.jsonl").unlink()
    if problem != "missing_ledger":
        write_ledger(package["ledgers"][0], package["rows"][0])
    report = evaluate(package)
    assert report["qualification_authorized"] is False
    assert report["qualification_passed"] is False
    assert report["qualification_reasons"]
    if problem == "unknown_truth":
        assert report["overall"]["known_truth"] == 599
        assert report["overall"]["true_success_rate"] == 1
        assert report["overall"]["success_over_planned"] == 599 / 600
        assert report["overall"]["failure_counts"] == {"private_truth_unavailable": 1}
    elif problem == "no_contact":
        assert report["overall"]["first_grasp_attempts"] == 600
        assert report["overall"]["contact_executed"] == 599
        assert report["overall"]["contact_not_executed"] == 1


@pytest.mark.parametrize("problem", ["pool_sha", "choices_sha", "duplicate_row", "unregistered_case", "discovery_sha"])
def test_changed_identity_is_rejected_instead_of_rejudged(package_factory, problem):
    package = package_factory()
    row = package["rows"][0][0]
    if problem == "pool_sha":
        package["pool"].write_text(package["pool"].read_text() + " ")
    elif problem == "choices_sha":
        (Path(row["output_dir"]) / "choices.jsonl").write_text('{"different":true}\n')
    elif problem == "duplicate_row":
        package["rows"][0].append(row)
        write_ledger(package["ledgers"][0], package["rows"][0])
    elif problem == "unregistered_case":
        row["case"]["episode"]["seed"] = 0
        write_ledger(package["ledgers"][0], package["rows"][0])
    elif problem == "discovery_sha":
        source = json.loads(package["pool"].read_text())["source_manifest"]["path"]
        Path(source).write_text('{"cases":[]}\n')
    with pytest.raises(ValueError):
        evaluate(package)


@pytest.mark.parametrize("problem", ["old_tuple", "old_raw_hash", "class_tuple_repeat", "class_raw_repeat", "actual_state_changed"])
def test_confirmation_state_independence_is_not_inferred_from_pool_counts(package_factory, problem):
    def change(cases, old_key):
        if problem == "old_tuple":
            cases[0]["episode"] = dict(zip(("suite", "task", "seed"), old_key))
            cases[0]["state_sha256"] = digest(old_key)
        elif problem == "old_raw_hash":
            cases[0]["state_sha256"] = digest(old_key)
        elif problem == "class_tuple_repeat":
            cases[1]["episode"] = copy.deepcopy(cases[0]["episode"])
        elif problem == "class_raw_repeat":
            cases[1]["state_sha256"] = cases[0]["state_sha256"]
        else:
            cases[0]["state_sha256"] = "f" * 64
    package = package_factory(change)
    with pytest.raises(ValueError):
        evaluate(package)


def test_cross_class_state_reuse_is_disclosed_without_inventing_independence(package_factory):
    def change(cases, old_key):
        pan = next(case for case in cases if case["group"] == "frypan")
        moka = next(case for case in cases if case["group"] == "moka_pot")
        moka["episode"] = copy.deepcopy(pan["episode"])
        moka["state_sha256"] = pan["state_sha256"]
    report = evaluate(package_factory(change))
    assert report["qualification_passed"] is True
    assert report["cross_class_shared_scene_tuples"] == 1
    assert report["cross_class_shared_raw_state_hashes"] == 1
    assert report["cross_class_raw_state_reuse"][0]["classes"] == ["frypan", "moka_pot"]
    assert "pooled independence is not assumed" in report["ci_scope"]


def test_confusion_denominators_are_true_positive_and_negative_populations(package_factory):
    package = package_factory()
    rows = package["rows"][0]
    rows[0]["true_sustained_grasp"] = False  # FP, denominator one true failure.
    rows[1]["visual_verified"] = False  # FN, denominator 599 true successes.
    write_ledger(package["ledgers"][0], rows)
    overall = evaluate(package)["overall"]
    assert overall["false_positive_count"] == 1
    assert overall["false_positive_denominator_true_failures"] == 1
    assert overall["false_positive_rate"] == 1
    assert overall["false_negative_count"] == 1
    assert overall["false_negative_denominator_true_successes"] == 599
    assert overall["false_negative_rate"] == 1 / 599


@pytest.mark.parametrize("problem", ["overall_success", "class_success", "agreement"])
def test_complete_confirmation_can_fail_numeric_gate(package_factory, problem):
    package = package_factory()
    if problem == "overall_success":
        all_rows = [row for rows in package["rows"] for row in rows]
        for index, group in enumerate(summary.GROUPS):
            chosen = [row for row in all_rows if row["case"]["group"] == group]
            for row in chosen[:6 if index < 5 else 1]:
                row["true_sustained_grasp"] = row["visual_verified"] = False
    elif problem == "class_success":
        for row in package["rows"][0][:11]:
            row["true_sustained_grasp"] = row["visual_verified"] = False
    else:
        for row in package["rows"][0][:31]:
            row["visual_verified"] = False
    for path, rows in zip(package["ledgers"], package["rows"]):
        write_ledger(path, rows)
    report = evaluate(package)
    assert report["qualification_authorized"] is True
    assert report["qualification_passed"] is False
    reason = {"overall_success": "overall_confirmed_success_below_95_percent_of_planned_trials",
              "class_success": "class_confirmed_success_below_90_percent_of_planned_trials",
              "agreement": "verifier_agreement_below_95_percent"}[problem]
    assert report["qualification_reasons"] == [reason]


def test_cli_writes_a_new_confirmation_report_from_explicit_inputs(package_factory, monkeypatch, tmp_path):
    package = package_factory()
    output = tmp_path / "report.json"
    argv = ["confirmation", "--pool", str(package["pool"])]
    for path in package["manifests"]:
        argv.extend(["--manifest", str(path)])
    for path in package["ledgers"]:
        argv.extend(["--ledger", str(path)])
    monkeypatch.setattr(sys, "argv", argv + ["--output", str(output)])
    summary.main()
    assert json.loads(output.read_text())["qualification_passed"] is True
    with pytest.raises(FileExistsError):
        summary.main()
