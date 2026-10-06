# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Infrastructure retries retain attempts and never replace physical failures."""

import json
import sys
from types import ModuleType

import pytest

from scripts import probe_v5_grasp449_20261005 as probe


def run_probe(monkeypatch, tmp_path, outcomes, *, total=100, selected=1):
    import harness_v5_eval
    import rpent.utils.daemon
    import rpent.utils.rpc

    cases = [{"name": f"box_{i}", "category": "butter", "condition": "registered",
              "episode": {"suite": "libero_object", "task": 6, "seed": i}}
             for i in range(total)]
    plan = {"cases": cases, "conditions": {"registered": {
        "profile": "high_short", "mode": "direct", "max_chunks": 160, "overrides": {}}},
        "choice_package": str(tmp_path / "choices")}
    preflight = ModuleType("scripts.v5_probe_preflight")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(plan))
    preflight.load_pinned_manifest = lambda p: (p.resolve(), plan, {"libero_type": "standard"})
    preflight.validate_registered_states = lambda cases: None
    monkeypatch.setitem(sys.modules, "scripts.v5_probe_preflight", preflight)

    class Daemon:
        def __init__(self, **kwargs):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(rpent.utils.daemon, "ProcessDaemon", Daemon)
    monkeypatch.setattr(rpent.utils.rpc, "wait_for_ready", lambda *a, **kw: None)
    calls = []
    outcomes = iter(outcomes)

    def episode(args):
        calls.append(args)
        args.output_dir.mkdir(parents=True)
        outcome = next(outcomes)
        if outcome == "infra":
            raise RuntimeError("env_meta mismatch: diagnostic identity")
        receipt = {"tool": "grasp", "executed": True,
                   "grasp_verified": outcome == "success", "chunks": 10,
                   "verification": "verified" if outcome == "success" else "failed"}
        (args.output_dir / "choices.jsonl").write_text(json.dumps({"receipt": receipt}) + "\n")
        if outcome == "postphysics_infra":
            raise RuntimeError("RpcError('oracle.measure_grasp_hold unavailable')")
        return {"status": "completed", "termination_category": "budget_exhausted"}

    monkeypatch.setattr(harness_v5_eval, "run_episode", episode)
    output = tmp_path / "job123" / "part0"
    monkeypatch.setattr(sys, "argv", ["probe", "--manifest", str(manifest), "--output", str(output),
                                     "--shard-index", "0", "--shards", str(total // selected)])
    return output, calls


def test_transport_attempt_is_retained_and_same_state_gets_one_fresh_episode(monkeypatch, tmp_path):
    output, calls = run_probe(monkeypatch, tmp_path, ["infra", "success"])
    probe.main()
    assert len(calls) == 2
    assert calls[0].seed == calls[1].seed
    assert calls[0].output_dir != calls[1].output_dir
    failed = json.loads((output / "infrastructure_attempts.jsonl").read_text())
    assert failed["attempt_index"] == 0 and failed["failure_classification"] == "infrastructure_failure"
    completed = json.loads((output / "episodes.jsonl").read_text())
    assert completed["infrastructure_rerun"] is True and completed["visual_verified"] is True
    assert calls[0].output_dir.joinpath("private_grasp_diagnostic.json").is_file()


def test_physical_failure_remains_a_single_completed_attempt(monkeypatch, tmp_path):
    output, calls = run_probe(monkeypatch, tmp_path, ["physical_failure"])
    probe.main()
    assert len(calls) == 1
    assert (output / "infrastructure_attempts.jsonl").read_text() == ""
    failed = json.loads((output / "episodes.jsonl").read_text())
    assert failed["visual_verified"] is False and failed["first_receipt"]["verification"] == "failed"


def test_same_state_never_gets_a_third_attempt(monkeypatch, tmp_path):
    output, calls = run_probe(monkeypatch, tmp_path, ["infra", "infra"])
    with pytest.raises(RuntimeError, match="preserved diagnostic failures"):
        probe.main()
    assert len(calls) == 2
    assert len((output / "infrastructure_attempts.jsonl").read_text().splitlines()) == 2
    assert (output / "episodes.jsonl").read_text() == ""
    summary = json.loads((output / "summary.json").read_text())
    assert summary["infrastructure_cases"] == 1
    assert summary["infrastructure_attempts_in_this_shard"] == 2


def test_infrastructure_fault_after_physical_execution_is_not_reexecuted(monkeypatch, tmp_path):
    output, calls = run_probe(monkeypatch, tmp_path, ["postphysics_infra"])
    with pytest.raises(RuntimeError, match="preserved diagnostic failures"):
        probe.main()
    assert len(calls) == 1
    preserved = json.loads((output / "infrastructure_attempts.jsonl").read_text())
    assert preserved["physical_execution_before_infrastructure_failure"] is True
    assert preserved["retry_disposition"] == "not_reexecuted_after_physical_execution"
    assert preserved["eligible_physical_result"] is False
    assert (output / "episodes.jsonl").read_text() == ""


def test_third_infrastructure_failure_stops_full100_after_preserving_evidence(monkeypatch, tmp_path):
    output, calls = run_probe(monkeypatch, tmp_path, ["infra", "success", "infra", "success", "infra"],
                              selected=4)
    with pytest.raises(RuntimeError, match="exceed 2%"):
        probe.main()
    assert len(calls) == 5
    assert len((output / "infrastructure_attempts.jsonl").read_text().splitlines()) == 3
    assert len((output / "episodes.jsonl").read_text().splitlines()) == 2


def test_measurement_or_waypoint_failure_is_not_transport_failure():
    assert probe.infrastructure_failure({"first_receipt": {"verification": "failed",
        "failure_reason": "waypoint_not_reached"}}) is None
    assert probe.infrastructure_failure({"first_receipt": {"verification": "execution_error",
        "error": "ValueError: grasp object missing in close-up measurement"}}) is None
    assert probe.infrastructure_failure({"raised_error": "RpcError('oracle.measure_grasp_hold: ')"})
