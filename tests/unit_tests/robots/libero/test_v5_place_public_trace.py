"""The public trace preserves provenance and does not serialize private state."""

import inspect
import json
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_place_public_trace import PublicPlacementTrace, original_placement_trace
from robots.libero.v5_runtime import MeasuredScene, V5Executor
from robots.libero.v5_state import Entity, Candidate


class State:
    latest_step = 4

    def __init__(self, root):
        self.root = root

    def artifact_path(self, name, *, step):
        if step is None:
            return self.root / name
        return self.root / name / (f"{step:02d}" + (".npz" if name.endswith("npz") else ".json"))

    def exists(self, name, *, step):
        return self.artifact_path(name, step=step).exists()

    def save(self, name, value, *, step):
        path = self.artifact_path(name, step=step)
        path.parent.mkdir(parents=True, exist_ok=True)
        if name.endswith("npz"):
            np.savez_compressed(path, array=value)
        elif name.endswith("jsonl"):
            path.write_text("".join(json.dumps(item) + "\n" for item in value))
        else:
            path.write_text(json.dumps(value))
        return path


def test_trace_marks_cached_clouds_and_reads_only_robot_proprioception(tmp_path):
    state = State(tmp_path)
    bowl = Entity("e1", "bowl", (0., 0., 1.), (-.05, -.05, .98), (.05, .05, 1.02),
                  source_step=2, visible=False)
    points = np.asarray([[0., 0., 1.]])
    scene = SimpleNamespace(entities={bowl.id: bowl}, measurement_views={}, perception_evidence={},
        measurement_clouds_by_view={bowl.id: {"agentview": {"xyz_world": points, "src": "perception",
                                  "source_step": 2, "object_id": bowl.id}}},
        measurement_clouds={bowl.id: points})
    executor = SimpleNamespace(scene=scene, toolkit=SimpleNamespace(_state=state),
        p=SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.1]), _last_obs_gripper=.03,
                          env=SimpleNamespace(raw_obs=lambda: {"robot0_eef_quat": [1., 0., 0., 0.],
                                                               "sim_truth": "must not serialize"})),
        held=bowl.id, held_offset=np.array([0., 0., .1]))
    trace = PublicPlacementTrace(executor)
    trace.action = Candidate("place", bowl.id, "e2", "on")
    ref = trace.save("test")
    value = json.loads(open(ref["path"]).read())
    assert value["entities"][bowl.id]["fused_cloud"]["current"] is False
    assert value["entities"][bowl.id]["fused_cloud"]["source_step"] == 2
    assert value["entities"][bowl.id]["per_view"]["agentview"]["current"] is False
    assert value["held_offset_m"] == [0., 0., .1]
    assert value["training_allowed"] is False
    assert "sim_truth" not in json.dumps(value)
    assert (tmp_path / "place_trace_index.jsonl").exists()
    assert json.loads((tmp_path / "place_trace_index.jsonl").read_text()) == ref


def test_probe_hooks_keep_constructor_signature_and_restore_methods():
    methods = (V5Executor.__init__, MeasuredScene.refresh, V5Executor.execute)
    signature = inspect.signature(V5Executor)
    with original_placement_trace():
        assert inspect.signature(V5Executor) == signature
        assert V5Executor.execute is not methods[-1]
    assert (V5Executor.__init__, MeasuredScene.refresh, V5Executor.execute) == methods


def test_runtime_only_observer_does_not_add_capture_query_or_cleanup(monkeypatch):
    calls = []
    scene = MeasuredScene.__new__(MeasuredScene)
    scene.fixture_fragment_alias_v1 = True
    scene.record_sam_masks_v6 = True
    scene.fixture_alias_history = [{"aliases": []}]
    scene.entities = {"e1": SimpleNamespace(name="bowl")}
    state = SimpleNamespace(latest_step=1, save=lambda *args, **kwargs: calls.append("save"))
    scene.toolkit = SimpleNamespace(_state=state)
    def initialize(self, *args, **kwargs):
        self.scene = scene
        self.held = "e1"
        self.toolkit = SimpleNamespace(_state=state)
        self.p = SimpleNamespace(move_to=lambda *args, **kwargs: calls.append("move") or {"steps_used": 7})
        self.capture = lambda: pytest.fail("runtime-only observer must not capture")
    def refresh(self, names, **kwargs):
        calls.append(tuple(names))
    def execute(self, action, card=None):
        self.scene.refresh(["bowl"])
        return self.p.move_to([0., 0., 1.])
    monkeypatch.setattr(V5Executor, "__init__", initialize)
    monkeypatch.setattr(MeasuredScene, "refresh", refresh)
    monkeypatch.setattr(V5Executor, "execute", execute)
    monkeypatch.setattr(PublicPlacementTrace, "save", lambda self, phase: calls.append(phase))
    with original_placement_trace(observe_runtime_only=True):
        executor = V5Executor()
        result = executor.execute(Candidate("place", "e1", "e2", "on"))
    assert result == {"steps_used": 7}
    assert calls.count("move") == 1
    assert ("bowl",) in calls and not any(isinstance(value, tuple) and "drawer" in value for value in calls)
    assert calls.count("before_existing_carry_segment") == calls.count("after_existing_carry_segment") == 1
