"""Exercise the launcher boundary against the actual job4463 ledger shape."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_boundary(tmp_path, row, *, startup=True):
    (tmp_path / "episodes.jsonl").write_text(json.dumps(row) + "\n")
    launcher = Path(__file__).with_name("run_smoke.sbatch").read_text()
    code = launcher.split("<<'PY'\n")[-1].rsplit("\nPY", 1)[0]
    return subprocess.run(
        [sys.executable, "-", str(tmp_path), "0"],
        input=code, text=True, capture_output=True,
        env={**os.environ, "MICROWAVE_REQUIRE_PHYSICAL_STARTUP": "1" if startup else "0"},
    )


def actual_row():
    path = Path(__file__).with_name("physical_exit_fixture4463.json")
    return json.loads(path.read_text())


def test_accepts_top_level_server_counts_from_actual_physical_ledger(tmp_path):
    result = run_boundary(tmp_path, actual_row())
    assert result.returncode == 0, result.stderr
    contract = json.loads((tmp_path / "physical_startup_contract.json").read_text())
    assert contract["requested_controls"] == 80
    assert contract["temporal_records"] == 9
    assert contract["physics_result_is_skill_qualification"] is False


@pytest.mark.parametrize("fault", ["zero_controls", "not_executed", "startup_error"])
def test_rejects_missing_physics_and_startup_error(tmp_path, fault):
    row = actual_row()
    if fault == "zero_controls":
        row["server_chunk_execution"]["requested_controls"] = 0
    elif fault == "not_executed":
        row["first_attempt"]["physically_executed"] = False
    else:
        row["status"] = "startup_error"
    result = run_boundary(tmp_path, row)
    assert result.returncode != 0
    assert not (tmp_path / "physical_startup_contract.json").exists()


def test_public_binding_failure_is_preserved_as_selection_outcome(tmp_path):
    row = actual_row()
    row.update(status="first_attempt_public_binding_missing", first_attempt=None,
               binding_error="current public microwave parent missing or ambiguous")
    result = run_boundary(tmp_path, row, startup=False)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "physical_startup_contract.json").exists()


def test_startup_cannot_pass_on_the_same_public_binding_failure(tmp_path):
    row = actual_row()
    row.update(status="first_attempt_public_binding_missing", first_attempt=None)
    result = run_boundary(tmp_path, row)
    assert result.returncode != 0
    assert not (tmp_path / "physical_startup_contract.json").exists()


def test_selection_still_fails_on_infrastructure_error(tmp_path):
    row = actual_row()
    row.update(status="infrastructure_error", first_attempt=None)
    result = run_boundary(tmp_path, row, startup=False)
    assert result.returncode != 0
