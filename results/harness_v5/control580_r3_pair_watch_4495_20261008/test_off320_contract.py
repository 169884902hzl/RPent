"""Fixed budget overlay and passive score counts; physical smoke is separate."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
import sys

import pytest

from scripts.prepare_v5_temporal_control_capture_20261007 import COLLECTOR, OFF320_SERVER, off320_driver

ROOT = Path(__file__).resolve().parents[3]


def collector_module():
    module = ModuleType("off320_collector_test")
    exec(compile(COLLECTOR, "collector.py", "exec"), module.__dict__)
    return module


def test_fixed_320_controls_and_boundary(monkeypatch, tmp_path):
    module = collector_module()
    original = ROOT / "tests/unit_tests/robots/libero/test_v5_temporal_control_capture.py"
    spec = importlib.util.spec_from_file_location("original_capture_tests", original)
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    original_run = module.run_phases
    module.run_phases = lambda *args, **kwargs: original_run(*args, **kwargs, fixed_off_chunks=320)
    directory = tmp_path / "case"
    directory.mkdir()
    row, events, captures = helpers.fake_phases(module, monkeypatch, directory, preserve=True)
    assert sum(name == "off" for name, _ in events) == 320
    assert sum(name == "hold" for name, _ in events) == 24
    assert len(captures) == 330
    assert row["off_contact"]["executed_control_actions"] == 1600
    assert module.RUN_PROGRESS["actual_controls"] == 2400
    row["private_scores"] = {}
    (directory / "episode.json").write_text(json.dumps(row))
    assert module.validate_physical_output(tmp_path, {"name": "case"},
        preserve_pre_off_contact=True, fixed_off_chunks=320)["completed_public_off_chunk_rows"] == 320
    with pytest.raises(RuntimeError, match="completed physical capture"):
        module.validate_physical_output(tmp_path, {"name": "case"}, preserve_pre_off_contact=True)


def test_budget_scope_installed_before_initial_private_label(monkeypatch):
    events = []

    class Base:
        def stove_chunk_start(self, phase, max_chunks):
            assert max_chunks == 160
            self._stove_chunk_scope = {"phase": phase, "max_chunks": max_chunks,
                "max_controls": max_chunks * 5, "chunks_requested": 0, "executed_controls": 0}
            events.append(("start", phase))

    class Scored(Base):
        def _write_private_score(self, scope, timing):
            events.append(("private_score", scope, timing))

    inherited = ModuleType("stove564_probe_env")
    inherited.ScoredStoveProbeFacade = Scored
    parent = ModuleType("robots.libero.v5_stove_probe_env")
    parent.StoveProbeFacade = Base
    monkeypatch.setitem(sys.modules, "stove564_probe_env", inherited)
    monkeypatch.setitem(sys.modules, "robots.libero.v5_stove_probe_env", parent)
    module = ModuleType("off320_server_test")
    exec(compile(OFF320_SERVER, "server.py", "exec"), module.__dict__)
    facade = module.Off320StoveProbeFacade()
    on = facade.stove_chunk_start("on", 160)
    off = facade.stove_chunk_start("off", 320)
    assert on["max_controls"] == 800 and off["max_controls"] == 1600
    assert events[-1][1] == off and events[-1][2] == "before_phase"
    with pytest.raises(ValueError, match="budget changed"):
        facade.stove_chunk_start("off", 160)


def test_private_ledger_has_distinct_phase_budgets(tmp_path):
    parent_path = ROOT / "results/harness_v5/stove568_public_stop_selection_CPU_20261006/probe_public_red_recovery.py"
    source = off320_driver(parent_path.read_text(), parent_path.parent)
    module = ModuleType("off320_driver_test")
    exec(compile(source, "driver.py", "exec"), module.__dict__)
    rows = [{"phase": phase, "chunk_index": index, "actual_controls": index * 5,
        "status": "scored"} for phase, count in (("on", 160), ("off", 320))
        for index in range(count + 1)]
    path = tmp_path / "labels_chunk.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    (tmp_path / "public_red_chunks.jsonl").write_text("{}\n")
    label = tmp_path / "stage_labels.json"
    label.write_text(json.dumps({"requested_predicates": {"turn_on": {"satisfied": True}}}))
    episode = {"captures": {"after_setup": {"labels": {"path": str(label)}}}}
    assert Path(module.postcollection_score(episode, tmp_path)["path"]).exists()
    path.write_text("".join(json.dumps(row) + "\n" for row in rows[:-1]))
    with pytest.raises(RuntimeError, match="unknown private scores"):
        module.postcollection_score(episode, tmp_path)
