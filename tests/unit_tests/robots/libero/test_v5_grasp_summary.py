"""Partial grasp manifests and unavailable Slurm accounting retain honest results."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import summarize_v5_grasp449_20261005 as summary


def case(index):
    return {"name": f"trial_{index}", "condition": "control", "group": "frypan",
            "episode": {"suite": "libero_10", "task": 2, "seed": index}}


def plan(cases):
    return {"cases": cases, "conditions": {"control": {"overrides": {}}},
            "groups": {group: [] for group in ("bottle", "bowl", "box", "frypan", "moka_pot", "mug")},
            "truth_protocol": {"minimum_first_trials_per_class": 100}}


def record(trial, truth=True):
    return {"case": trial, "true_sustained_grasp": truth, "visual_verified": True,
            "grasp_attempted": True, "first_receipt": {"verification": "measured"},
            "wall_s": 1, "chunks": 1, "executed_vla_actions": 5}


def run_summary(tmp_path, monkeypatch, trials, rows):
    manifest, ledger, output = (tmp_path / name for name in ("manifest.json", "episodes.jsonl", "report.json"))
    manifest.write_text(json.dumps(plan(trials)))
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))
    monkeypatch.setattr(sys, "argv", ["summary", "--manifest", str(manifest),
                                      "--ledger", str(ledger), "--output", str(output)])
    summary.main()
    return json.loads(output.read_text())


def test_pan_only_smoke_does_not_report_unplanned_classes_or_qualify(tmp_path, monkeypatch):
    trials = [case(i) for i in range(5)]
    report = run_summary(tmp_path, monkeypatch, trials, [record(trial) for trial in trials])
    assert report["complete"] is True
    assert set(report["by_condition_group"]) == {"control/frypan"}
    method = report["sustained_truth_methods"]["control"]
    assert set(method["by_class"]) == {"frypan"}
    assert method["by_class"]["frypan"]["true_success_rate"] == 1
    assert method["meets_user_grasp_gate"] is False
    assert report["qualifying_conditions"] == []


def test_zero_planned_has_no_success_rate_or_complete_truth():
    assert summary.summarize([], 0)["visual_success_over_all_planned"] is None
    assert summary.summarize([], 0)["contact_supported_lift_over_all_planned"] is None
    metrics = summary.truth_metrics([], 0)
    assert metrics["true_success_rate"] is None
    assert metrics["complete_truth_protocol"] is False


def test_selected_grasp_without_measured_handle_is_not_contact_execution():
    # Reduced from 3604 measured_pan_handle trial0: the tool was selected,
    # but missing SAM geometry prevented entry into the Pi0 contact stage.
    row = record(case(0), truth=False)
    row.update(visual_verified=False, executed_vla_actions=0,
               first_receipt={"tool": "grasp", "executed": False,
                              "verification": "unverified", "failure_reason": "visible_handle_not_measured"})
    metrics = summary.truth_metrics([row], 1)
    assert metrics["first_grasp_attempts"] == 1
    assert metrics["contact_executed"] == 0
    assert metrics["true_successes"] == 0
    counts = summary.summarize([row], 1)["counts"]
    assert counts["grasp_attempted"] == 1
    assert counts["contact_executed"] == 0


@pytest.mark.parametrize("actions,primitive,prompt,expected", [
    (85, {"name": "pick", "chunks_used": 17, "success": True}, "pick up the frying pan", True),
    (800, {"name": "pick", "chunks_used": 160, "success": False}, "pick up the frying pan", True),
    (0, None, "pick up the frying pan", False),  # Prompt saved before a failed call.
    (0, {"name": "pick", "chunks_used": 1}, "pick up the frying pan", False),
    (5, None, "pick up the frying pan", True),  # Actions happened before result/error recording.
    (None, {"name": "pick", "chunks_used": 17}, "pick up the frying pan", True),
    (None, {"name": "pick", "chunks_used": 0}, "pick up the frying pan", False),
    (None, None, "pick up the frying pan", False),
    (None, {"name": "pick", "chunks_used": 17}, None, False),
])
def test_contact_execution_uses_physical_action_evidence(actions, primitive, prompt, expected):
    row = {"grasp_attempted": True, "first_receipt": {"tool": "grasp", "executed": True}}
    if actions is not None:
        row["executed_vla_actions"] = actions
    if primitive is not None:
        row["rpent_pick_result"] = primitive
    if prompt is not None:
        row["contact_prompt"] = prompt
    assert summary.contact_executed(row) is expected


def test_numeric_exploratory_threshold_never_authorizes_qualification(tmp_path, monkeypatch):
    trials = [case(i) for i in range(100)]
    report = run_summary(tmp_path, monkeypatch, trials, [record(trial) for trial in trials])
    method = report["sustained_truth_methods"]["control"]
    # Preserve legacy fields for consumers while explicitly separating the
    # numeric result from new-state confirmation and qualification audit.
    assert method["meets_user_grasp_gate"] is True
    assert report["qualifying_conditions"] == ["control"]
    assert "numeric exploratory thresholds only" in report["qualification_field_semantics"]
    assert report["qualification_authorized"] is False
    assert method["qualification_authorized"] is False


def test_tool_selection_cannot_supply_100_executed_contacts_for_threshold(tmp_path, monkeypatch):
    trials = [case(i) for i in range(100)]
    rows = [record(trial) for trial in trials]
    rows[0]["executed_vla_actions"] = 0
    report = run_summary(tmp_path, monkeypatch, trials, rows)
    method = report["sustained_truth_methods"]["control"]
    assert method["first_grasp_attempts"] == 100
    assert method["contact_executed"] == 99
    assert method["meets_user_grasp_gate"] is False
    assert report["qualifying_conditions"] == []
    assert report["qualification_authorized"] is False


@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_unknown_trial_cannot_pass_truth_protocol(tmp_path, monkeypatch, missing):
    trials = [case(i) for i in range(2)]
    rows = [record(trials[0])]
    if not missing:
        rows.append(record(trials[1], truth=None))
    report = run_summary(tmp_path, monkeypatch, trials, rows)
    method = report["sustained_truth_methods"]["control"]
    assert method["known_truth"] == 1
    assert method["true_successes"] == 1
    assert method["complete_truth_protocol"] is False
    assert method["meets_user_grasp_gate"] is False
    assert report["complete"] is (not missing)
    if not missing:
        assert method["confusion"]["unknown_truth"] == 1
        assert method["failure_counts"]["private_truth_unavailable"] == 1


@pytest.mark.parametrize("problem", [None, "missing", "unknown", "wrong_shard"])
def test_report_launcher_uses_explicit_ledgers_without_compute_sacct(tmp_path, problem):
    repo = Path(__file__).resolve().parents[4]
    root = tmp_path / "installation"
    source = root / "report_source"
    (source / "scripts").mkdir(parents=True)
    (source / "scripts/summarize_v5_grasp449_20261005.py").write_text(
        (repo / "scripts/summarize_v5_grasp449_20261005.py").read_text())
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    base = root / "results/harness_v5/grasp459_bound_safe_retry1_20261005"
    (base / "preparation").mkdir(parents=True)
    trials = [case(i) for i in range(18)]
    (base / "preparation/full.json").write_text(json.dumps(plan(trials)))
    for part, trial in enumerate(trials):
        if problem == "missing" and part == 17:
            continue
        directory = base / f"full_job3550/part{part}"
        directory.mkdir(parents=True)
        if problem == "wrong_shard" and part < 2:
            trial = trials[1 - part]
        truth = None if problem == "unknown" and part == 17 else True
        (directory / "episodes.jsonl").write_text(json.dumps(record(trial, truth)) + "\n")
    # A broken Slurm accounting client must neither run nor suppress physical results.
    binary_dir = root / "bin"
    binary_dir.mkdir()
    marker = root / "sacct_called"
    sacct = binary_dir / "sacct"
    sacct.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 1\n")
    sacct.chmod(0o755)
    launcher = tmp_path / "report.sbatch"
    launcher.write_text((repo / "scripts/run_v5_grasp459_report.sbatch").read_text().replace(
        "ROOT=/public/home/sunyihan/rpent_libero_eval", f"ROOT='{root}'"))
    result = subprocess.run(["bash", str(launcher)], capture_output=True, text=True, env={
        **os.environ, "PATH": f"{binary_dir}:{os.environ['PATH']}", "SLURM_JOB_ID": "9000",
        "GRASP_FORMAL_ARRAY_ID": "3550", "GRASP_REPORT_SOURCE": str(source)})
    output = base / "report_job9000"
    report = json.loads((output / "report.json").read_text())
    audit = json.loads((output / "shard_accounting.json").read_text())
    assert not marker.exists()
    assert audit["accounting"] is None
    assert len(audit["shards"]) == 18
    assert result.returncode == (0 if problem is None else 1), result.stderr
    assert report["recorded"] == (17 if problem == "missing" else 18)
    if problem == "missing":
        assert audit["missing_ledgers"][0]["part"] == 17
        assert report["complete"] is False
    elif problem == "unknown":
        assert audit["shards"][17]["unknown_truth"] == 1
        assert report["sustained_truth_methods"]["control"]["complete_truth_protocol"] is False
    elif problem == "wrong_shard":
        assert not audit["shards"][0]["complete"]
        assert not audit["shards"][1]["complete"]
