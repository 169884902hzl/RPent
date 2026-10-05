"""The diagnostic stove probe preserves fixed actions and current measurements."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from scripts.probe_v5_stove521_endpoint import control_geometry, run_phases, validate_manifest


def plan():
    root = Path(__file__).resolve().parents[4]
    return json.loads((root / "results/harness_v5/stove521_endpoint_original_20261005/preparation/stove_control.json").read_text())


def test_registered_protocol_is_explicit_original_states_and_fixed_budget():
    registered = plan()
    validate_manifest(registered)
    assert {case["episode"]["seed"] for case in registered["cases"]} == set(range(10))


def test_measured_control_orientation_is_translation_invariant_without_endpoint_claim():
    cloud = np.array([(x, .5 * x + y, z) for x in np.linspace(-.06, .06, 30)
                      for y in (-.003, .003) for z in (.95, .96)])
    measured = control_geometry(cloud)
    translated = control_geometry(cloud + (.3, -.2, .5))
    assert measured["endpoint_state"] == "unmeasured"
    assert abs(measured["orientation_deg_mod180"] - translated["orientation_deg_mod180"]) < 1e-10
    assert measured["axis_elongation_ratio"] > 10
    assert control_geometry(np.empty((0, 3)))["reason"] == "insufficient_current_depth"


def test_on_execution_error_is_preserved_and_off_still_uses_the_registered_command(monkeypatch, tmp_path):
    from contextlib import nullcontext
    from scripts import probe_v5_stove521_endpoint as probe

    calls = []

    def vla_act(prompt, chunks, stop):
        calls.append((prompt, chunks, stop))
        if len(calls) == 1:
            raise RuntimeError("preserved development contact error")
        return {"executed": True, "chunks": 160, "stop": "chunk_budget"}

    executor = SimpleNamespace(
        motion_evidence=[], vla_act=vla_act, capture=lambda: None,
        scene=SimpleNamespace(refresh=lambda names: None),
        p=SimpleNamespace(env=SimpleNamespace(complete_skill=nullcontext, _native_terminated=True, truncated=False),
                          release=lambda: {"steps_used": 20}), retreat=lambda: None)
    observations = []

    def save(*args, **kwargs):
        # Simulate an already latched native success; measurement truth is not
        # fed to the fixed sequence and cannot suppress the reverse-off skill.
        observations.append(args[-1].name)
        return {"public_measurements": {"sha256": "unchanged"}}

    monkeypatch.setattr(probe, "capture_measurements", save)
    result = run_phases(executor, None, None, plan()["cases"][0], plan(), tmp_path)
    assert calls == [("turn on the stove", 160, "chunk_budget"), ("turn off the stove", 160, "chunk_budget")]
    assert len(observations) == 6
    assert result["phases"][1]["first_attempt"]["status"] == "execution_error"
    assert result["phases"][2]["first_attempt"]["receipt"]["executed"] is True
    assert result["native_original_success_latched"] is True
