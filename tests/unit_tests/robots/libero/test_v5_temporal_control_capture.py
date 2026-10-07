"""The paired collector must preserve contact without weakening exit evidence."""

from contextlib import nullcontext
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from scripts.prepare_v5_temporal_control_capture_20261007 import COLLECTOR


@pytest.fixture
def collector():
    module = ModuleType("control_capture_test")
    exec(compile(COLLECTOR, "capture_control_sequence.py", "exec"), module.__dict__)
    return module


def fake_phases(collector, monkeypatch, tmp_path, *, preserve=False, fail_last_capture=False):
    from scripts import probe_v5_stove521_endpoint as inherited

    events, captures = [], []
    executor = SimpleNamespace(motion_evidence=[])
    position = np.array([.2, .3, 1.])

    def step(action):
        events.append(("hold", action.tolist()))

    def release():
        events.append(("release", None))
        return {"executed": True}

    def retreat():
        events.append(("retreat", None))

    executor.p = SimpleNamespace(
        _last_obs_eef_pos=position, _last_obs_gripper=.03,
        _step_env=step, release=release,
        env=SimpleNamespace(complete_skill=nullcontext, _native_terminated=True, truncated=False))
    executor.retreat = retreat

    def contact(prompt, chunks, stop):
        assert prompt == "turn off the stove" and chunks == 1 and stop == "chunk_budget"
        events.append(("off", None))
        executor.motion_evidence.append({"executed_action_count": 5})
        return {"chunks": 1}

    executor.vla_act = contact

    def setup(*_, **kwargs):
        assert kwargs["phase"] == "on" and kwargs["chunks"] == 160
        events.append(("on", None))
        return {"fixed_prefix_completed": True, "executed_control_actions": 800}

    monkeypatch.setattr(inherited, "fixed_contact", setup)

    def capture(*args, **kwargs):
        directory = args[5]
        if fail_last_capture and directory.name == "chunk160":
            raise OSError("last public frame write failed")
        captures.append((directory.name, kwargs.get("measure_control", False)))
        events.append(("capture", directory.name))
        directory.mkdir(parents=True, exist_ok=False)
        public, private = directory / "public_measurements.json", directory / "labels.json"
        public.write_text(json.dumps({"source_step": len(captures)}))
        private.write_text("{}")
        refs = {"public_measurements": collector.identity(public), "labels": collector.identity(private),
                "source_step": len(captures)}
        return refs, {"source_step": len(captures), "public_measurements": refs["public_measurements"]}

    monkeypatch.setattr(collector, "capture_one", capture)
    oracle = SimpleNamespace(call=lambda *_, **__: {"actual_controls": 800})
    result = collector.run_phases(executor, None, oracle, {}, {}, tmp_path,
                                  preserve_pre_off_contact=preserve)
    return result, events, captures


@pytest.mark.parametrize("preserve,hold_count,capture_count,recovery_count", [
    (False, 36, 172, 2), (True, 24, 170, 1)])
def test_contact_preserving_mode_changes_only_the_pre_off_actions(
        collector, monkeypatch, tmp_path, preserve, hold_count, capture_count, recovery_count):
    result, events, captures = fake_phases(collector, monkeypatch, tmp_path, preserve=preserve)
    names = [name for name, _ in events]
    first_off = names.index("off")
    between = names[names.index("on") + 1:first_off]
    assert between == (["capture", "capture"] if preserve else
                       ["capture", "release", "retreat", "capture", *(["hold"] * 6),
                        "capture", *(["hold"] * 6), "capture"])
    assert names.count("hold") == hold_count
    assert names.count("release") == names.count("retreat") == recovery_count
    assert len(captures) == capture_count
    assert sum(measured for _, measured in captures) == 3
    assert names.count("off") == 160
    assert result["off_contact"]["executed_control_actions"] == 800
    assert collector.RUN_PROGRESS["actual_controls"] == 1600
    assert set(result["public_sequences"]) == ({"after_release", "after_retreat"} if preserve
                                              else {"before_off", "after_release", "after_retreat"})
    assert result["status"] == "fixed_public_control_sequence_recorded"


@pytest.mark.parametrize("preserve", [False, True])
def test_last_capture_failure_is_not_completed(collector, monkeypatch, tmp_path, preserve):
    with pytest.raises(RuntimeError, match="off execution/public capture failed"):
        fake_phases(collector, monkeypatch, tmp_path, preserve=preserve, fail_last_capture=True)
    partial = json.loads((tmp_path / "partial_collection.json").read_text())
    assert partial["status"] == "collecting"
    assert partial["off_contact"]["status"] == "execution_error"
    assert partial["off_contact"]["chunks"] == 160
    assert len((tmp_path / "public_red_chunks.jsonl").read_text().splitlines()) == 159


def test_saved_boundary_requires_the_registered_temporal_phases(collector, monkeypatch, tmp_path):
    directory = tmp_path / "test_case"
    directory.mkdir()
    row, _, _ = fake_phases(collector, monkeypatch, directory, preserve=True)
    row["private_scores"] = {}
    (directory / "episode.json").write_text(json.dumps(row))
    assigned = {"name": "test_case"}
    boundary = collector.validate_physical_output(tmp_path, assigned, preserve_pre_off_contact=True)
    assert boundary["completed_public_off_chunk_rows"] == 160
    with pytest.raises(RuntimeError, match="registered pre-off contact mode"):
        collector.validate_physical_output(tmp_path, assigned)


@pytest.mark.parametrize("parent_error", [RuntimeError("service startup fault"), None])
def test_startup_or_empty_parent_exit_cannot_return_success(
        collector, monkeypatch, tmp_path, parent_error):
    def parent_main():
        if parent_error is not None:
            raise parent_error

    probe = SimpleNamespace(__file__="pinned_parent.py", main=parent_main)
    plan = {"parent_manifest": {"path": "/pinned.json", "sha256": "pinned"},
            "preserve_pre_off_contact": True}
    assigned = {"name": "test_case", "parent_shard_index": 0}
    monkeypatch.setattr(collector, "load_inputs", lambda _: (plan, probe, assigned, {}))
    output = tmp_path / "physical"
    monkeypatch.setattr(collector.sys, "argv", ["collector", "--manifest", "/capture.json",
        "--manifest-sha256", "pinned", "--shard-index", "0", "--output", str(output)])
    with pytest.raises(RuntimeError, match="physical collector did not complete"):
        collector.main()
    row = json.loads((output / "collector_boundary.json").read_text())
    assert row["status"] == "startup_error"
    assert row["actual_contact_controls"] == 0
    assert row["physical_execution_started"] is False
