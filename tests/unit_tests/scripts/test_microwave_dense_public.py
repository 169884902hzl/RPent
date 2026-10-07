"""Dense metrology must preserve all controls even when private done is true."""

import json
from types import SimpleNamespace

import numpy as np

from scripts import probe_v5_microwave_dense_public as dense
from scripts.probe_v5_skill501_original import complete_probe_chunk, diagnostic_json


def test_observations_and_private_labels_cannot_shorten_a_five_action_chunk(tmp_path, monkeypatch):
    spec = {"kind": "articulate", "object_category": "microwave", "mode": "close",
            "object_symbol": "microwave_1", "episode": {"suite": "libero_90", "task": 33, "seed": 0}}
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"cohort": "development", "cases": [spec],
                               "training_allowed": False, "qualification_authorized": False}))
    probe = SimpleNamespace(ORIGINAL_SUITES={"libero_90"}, complete_probe_chunk=complete_probe_chunk,
                            diagnostic_json=diagnostic_json)
    observed, labels = [], []
    def capture(facade, observation, output, control):
        observed.append(control)
        return {"capture_id": "test:" + str(control), "source": "perception", "actual_control_index": control}
    monkeypatch.setattr(dense, "capture_public", capture)
    accounting = {"chunks_requested": 0, "requested_controls": 0, "executed_controls": 0,
                  "external_truncation": False, "raw_native_success_controls": 0}
    actions = []
    def step(action):
        actions.append(np.asarray(action).tolist())
        return {"states": np.zeros(8)}, 0., True, False, {}
    def truth(spec):
        labels.append(len(actions))
        return {"satisfied": True, "joint_qpos": [[0.]]}
    facade = SimpleNamespace(step=step, skill_truth=truth, _skill_chunk_accounting=accounting)
    original_step = facade.step
    dense.install_dense_capture(probe, plan, tmp_path / "output")
    requested = np.arange(35).reshape(5, 7)
    probe.complete_probe_chunk(facade, requested)
    assert actions == requested.tolist()
    assert observed == labels == [1, 2, 3, 4, 5]
    assert accounting["executed_controls"] == 5
    assert facade.step is original_step
    public = [json.loads(line) for line in (tmp_path / "output/public_captures.jsonl").read_text().splitlines()]
    assert all("private_fixture_label" not in row for row in public)


def test_capture_fault_is_retained_and_does_not_change_requested_controls(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"cohort": "development", "cases": [{"kind": "articulate",
        "object_category": "microwave", "episode": {"suite": "libero_90"}}],
        "training_allowed": False, "qualification_authorized": False}))
    def fail(*args):
        raise RuntimeError("camera transport failed")
    monkeypatch.setattr(dense, "capture_public", fail)
    probe = SimpleNamespace(ORIGINAL_SUITES={"libero_90"}, complete_probe_chunk=complete_probe_chunk,
                            diagnostic_json=diagnostic_json)
    accounting = {"chunks_requested": 0, "requested_controls": 0, "executed_controls": 0,
                  "external_truncation": False, "raw_native_success_controls": 0}
    facade = SimpleNamespace(step=lambda a: ({"states": np.zeros(8)}, 0., False, False, {}),
        skill_truth=lambda spec: {"satisfied": False}, _skill_chunk_accounting=accounting)
    dense.install_dense_capture(probe, plan, tmp_path / "output")
    probe.complete_probe_chunk(facade, np.zeros((5, 7)))
    records = [json.loads(line) for line in (tmp_path / "output/public_captures.jsonl").read_text().splitlines()]
    assert len(records) == accounting["executed_controls"] == 5
    assert all(row["capture_error"] is not None for row in records)
