"""Service faults preserve their attempts without retrying physical misses."""

import io
import json

import pytest

from robots.libero.v5_env_client import V5SkillEnvClient
from rpent.utils.rpc.rpc_client import RpcError
from scripts import probe_v5_skill501_original as probe


def registered_case():
    return {"name": "case0", "state_sha256": "a" * 64,
            "episode": {"suite": "libero_90", "task": 7, "seed": 13}}


def test_probe_original90_metadata_matches_connector_without_relaxing_identity():
    meta = probe.probe_env_meta("libero_90", 7, 13, 10000)
    class RPC:
        def call(self, method, **kwargs):
            if method == "env.get_env_meta":
                return meta
            if method == "env.reset":
                return {"step": 0}, {}
            pytest.fail(method)
    expected = {key: value for key, value in meta.items() if key != "original90_grasp_diagnostic_v1"}
    assert V5SkillEnvClient(RPC(), expected_meta=expected).last_obs == {"step": 0}
    assert "original90_grasp_diagnostic_v1" not in expected
    assert "original90_grasp_diagnostic_v1" not in probe.probe_env_meta("libero_goal", 7, 13, 10000)


def test_rpc_fault_restarts_once_and_preserves_original_then_same_state_retry(tmp_path):
    events, ledger = [], io.StringIO()
    def attempt(case, condition, output):
        events.append(("attempt", case["state_sha256"], output.name))
        if len(events) == 1:
            raise RpcError("oracle.snapshot", "HTTP request failed: connection reset")
        return {"status": "first_attempt_recorded", "setup": [], "first_attempt": None}
    row = probe.run_case_attempts(registered_case(), {}, tmp_path, attempt,
                                 lambda: events.append(("restart",)), ledger)
    attempts = [json.loads(line) for line in ledger.getvalue().splitlines()]
    assert events == [("attempt", "a" * 64, "attempt0"), ("restart",),
                      ("attempt", "a" * 64, "attempt1")]
    assert attempts[0]["status"] == "infrastructure_error"
    assert attempts[0]["eligible_physical_result"] is False
    assert attempts[1]["infrastructure_retry"] is True
    assert row["case_had_infrastructure_failure"] and not row["physical_failures_retried"]
    assert row["eligible_physical_result"] and len(row["attempts"]) == 2
    assert (tmp_path / "attempt0/private_skill_diagnostic.json").is_file()


def test_negative_physics_receipt_does_not_retry(tmp_path):
    calls, ledger = [], io.StringIO()
    def attempt(*args):
        calls.append(True)
        return {"status": "first_attempt_recorded", "first_attempt": {
            "receipt": {"verification": "failed", "grasp_verified": False}}}
    row = probe.run_case_attempts(registered_case(), {}, tmp_path, attempt,
                                 lambda: pytest.fail("physical miss must not restart"), ledger)
    assert len(calls) == 1 and len(row["attempts"]) == 1
    assert not row["case_had_infrastructure_failure"]


def test_rpc_execution_receipt_retries_but_program_error_is_not_physics(tmp_path):
    calls, ledger = [], io.StringIO()
    def attempt(*args):
        calls.append(True)
        return {"status": "setup_execution_error", "setup": [{"receipt": {
            "verification": "execution_error", "error": "RpcError: vla.predict: service died"}}]}
    row = probe.run_case_attempts(registered_case(), {}, tmp_path, attempt, lambda: None, ledger)
    assert len(calls) == 2 and row["status"] == "infrastructure_error"
    assert not row["eligible_physical_result"]
    assert probe.error_record(ValueError("invalid mode"), stage="first_attempt")["failure_category"] == "development_error"


def test_late_private_rpc_fault_preserves_prior_executed_evidence():
    row = {"status": "first_attempt_recorded", "first_attempt": {"receipt": {"executed": True}}}
    class RPC:
        def call(self, *args, **kwargs):
            raise RpcError("oracle.snapshot", "service unavailable")
    assert not probe.private_result_call(row, "after_first_attempt_snapshot", RPC(), "oracle.snapshot")
    assert row["first_attempt"]["receipt"]["executed"]
    assert row["infrastructure_failure"]


def test_fault_rate_keeps_recovered_faults_and_stops_only_above_two_percent():
    assert probe.infrastructure_status(2, 100, 2)["status"] == "running"
    status = probe.infrastructure_status(3, 100, 3)
    assert status["status"] == "infrastructure_stop"
    assert status["infrastructure_failure_rate"] == .03
    assert status["faults_are_model_results"] is False


def test_late_private_fault_does_not_repeat_an_executed_first_attempt(tmp_path):
    calls = []
    def attempt(*args):
        calls.append(True)
        return {"status": "probe_error", "error_stage": "private_metrology",
                "infrastructure_failure": True,
                "first_attempt": {"physically_executed": True,
                                  "receipt": {"executed": True, "place_verified": False}}}
    row = probe.run_case_attempts(registered_case(), {}, tmp_path, attempt,
                                 lambda: pytest.fail("must not reexecute after a label RPC fault"), io.StringIO())
    assert len(calls) == 1 and len(row["attempts"]) == 1
    assert row["instrument_fault_after_execution"] and not row["eligible_physical_result"]
    saved = json.loads((tmp_path / "attempt0/private_skill_diagnostic.json").read_text())
    assert saved["instrument_fault_after_execution"]


def test_manifest_fault_ledger_uses_full_denominator_and_unique_cases(tmp_path):
    row = {"case": registered_case(), "output_dir": "part0/case0",
           "case_had_infrastructure_failure": True}
    status = probe.record_manifest_infrastructure(tmp_path, "b" * 64, 52, row)
    assert status["infrastructure_failure_rate"] == 1 / 52
    assert status["status"] == "running" and status["planned_cases"] == 52
    status = probe.record_manifest_infrastructure(tmp_path, "b" * 64, 52, row)
    assert status["infrastructure_cases"] == 1 and status["completed_cases"] == 1
    row = {**row, "case": {**row["case"], "name": "case1"}}
    assert probe.record_manifest_infrastructure(tmp_path, "b" * 64, 52, row)["status"] == "infrastructure_stop"
