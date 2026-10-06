"""The diagnostic stove probe preserves fixed actions and current measurements."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

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


def test_full_chunk_macro_scopes_end_on_error_and_are_independent(monkeypatch, tmp_path):
    from contextlib import nullcontext
    from scripts import probe_v5_stove521_endpoint as probe

    registered = plan()
    registered.update(version="original-stove-control-measurement/2-fullchunks-dev",
                      diagnostic_server_module="robots.libero.v5_stove_probe_env",
                      full_chunk_diagnostic_scope=True)
    validate_manifest(registered)
    calls = []
    active = []

    class Rpc:
        def call(self, name, *, kwargs=None, timeout_s=None):
            calls.append((name, kwargs))
            if name.endswith("_start"):
                active.append(kwargs["phase"])
            elif name.endswith("_end"):
                return {"phase": active.pop(), "actual_controls": 800}

    def contact(prompt, *_):
        assert len(active) == 1
        if prompt == "turn on the stove":
            raise RuntimeError("saved failed contact")
        return {"executed": True, "chunks": 160}

    executor = SimpleNamespace(
        motion_evidence=[], vla_act=contact, capture=lambda: None,
        scene=SimpleNamespace(refresh=lambda _: None),
        p=SimpleNamespace(env=SimpleNamespace(complete_skill=nullcontext,
            _native_terminated=True, truncated=False), release=lambda: None), retreat=lambda: None)
    monkeypatch.setattr(probe, "capture_measurements", lambda *_, **__: {})
    result = run_phases(executor, None, Rpc(), registered["cases"][0], registered, tmp_path)
    assert active == []
    assert [args["phase"] for name, args in calls if name.endswith("_start")] == ["on", "off"]
    assert result["phases"][1]["first_attempt"]["status"] == "execution_error"
    assert result["phases"][1]["first_attempt"]["chunk_completion_scope"]["phase"] == "on"
    assert result["phases"][2]["first_attempt"]["chunk_completion_scope"]["phase"] == "off"


def test_directed_control_protocol_requires_explicit_feature_queries():
    from scripts.probe_v5_stove521_endpoint import CONTROL_FEATURE_QUERIES

    registered = plan()
    registered.update(version="original-stove-control-measurement/3-directed-control-dev",
        diagnostic_server_module="robots.libero.v5_stove_probe_env", full_chunk_diagnostic_scope=True,
        stove_control_features_v1=True, control_feature_queries=dict(CONTROL_FEATURE_QUERIES))
    validate_manifest(registered)
    registered["control_feature_queries"]["tip"] = "unregistered query"
    with pytest.raises(ValueError, match="explicit registered feature queries"):
        validate_manifest(registered)


def test_optional_direction_sampling_adds_before_contact_without_using_truth_to_choose_actions(monkeypatch, tmp_path):
    from contextlib import nullcontext
    from scripts import probe_v5_stove521_endpoint as probe

    registered = plan()
    registered["stove_control_features_v1"] = True
    observations, contacts = [], []
    monkeypatch.setattr(probe, "capture_measurements",
        lambda *args, **kwargs: observations.append(args[-1].name) or {})
    executor = SimpleNamespace(motion_evidence=[],
        vla_act=lambda *args: contacts.append(args) or {"executed": True}, capture=lambda: None,
        scene=SimpleNamespace(refresh=lambda _: None), retreat=lambda: None,
        p=SimpleNamespace(release=lambda: None,
            env=SimpleNamespace(complete_skill=nullcontext, _native_terminated=True, truncated=False)))
    run_phases(executor, None, None, registered["cases"][0], registered, tmp_path)
    assert observations == ["pre_recovery", "post_recovery", "before_contact", "pre_recovery", "post_recovery",
                            "before_contact", "pre_recovery", "post_recovery"]
    assert contacts == [("turn on the stove", 160, "chunk_budget"), ("turn off the stove", 160, "chunk_budget")]


def test_duplicate_control_masks_are_one_binding_but_distinct_controls_remain_ambiguous():
    from scripts.probe_v5_stove521_endpoint import bind_current_control_features, CONTROL_FEATURE_QUERIES
    from robots.libero.v5_state import Entity

    shell = Entity("e1", "stove", (0., 0., 1.), (-.1, -.1, .98), (.1, .1, 1.01), source_step=3)
    cloud = np.array([(x, y, 1.03) for x in np.linspace(.05, .09, 20) for y in np.linspace(.04, .07, 10)])
    mask = np.zeros((64, 64), bool); mask[10:30, 10:30] = True
    record = lambda: {"cloud": {"path": "explicit-current-control.npz", "sha256": "registered"}}
    candidates = {role: [] for role in ("control", *CONTROL_FEATURE_QUERIES)}
    candidates["control"] = [{"points": cloud, "mask": mask, "record": record()},
                             {"points": cloud.copy(), "mask": mask.copy(), "record": record()}]
    result = bind_current_control_features(candidates, shell, (.3, .3, 1.5), source_step=3, camera="wrist")
    assert result["valid_control_candidates"] == 1 and result["control_pose"] is not None
    assert result["directed_lever"] is None and result["endpoint_state"] == "unmeasured"
    second_mask = np.zeros_like(mask); second_mask[35:55, 35:55] = True
    candidates["control"].append({"points": cloud - [.1, .1, 0.], "mask": second_mask, "record": record()})
    ambiguous = bind_current_control_features(candidates, shell, (.3, .3, 1.5), source_step=3, camera="wrist")
    assert ambiguous["control_pose"] is None and ambiguous["reason"] == "multiple_valid_current_controls"


@pytest.mark.parametrize("missing_tip_mask", [False, True])
def test_capture_saves_same_capture_two_view_clouds_and_keeps_truth_out_of_public_packet(monkeypatch, tmp_path, missing_tip_mask):
    from io import BytesIO
    from PIL import Image
    from scripts import probe_v5_stove521_endpoint as probe
    from robots.libero.v5_state import Entity
    from rpent.robots.components.sam3_client import Sam3Client

    shell = Entity("e1", "stove", (0., 0., 1.), (-.1, -.1, .98), (.1, .1, 1.03), source_step=3)
    yy, xx = np.mgrid[.04:.07:32j, .05:.09:32j]
    world = np.stack((xx, yy, np.full_like(xx, 1.03)), axis=-1)
    image = BytesIO(); Image.fromarray(np.full((32, 32, 3), 30, np.uint8)).save(image, format="PNG")
    metadata = np.eye(4); metadata[:3, 3] = [.3, .3, 1.5]
    calls = []

    def load(name, *, step):
        assert step == 3
        return {"extrinsic_cam2world": metadata.tolist()} if name.endswith(".json") else world

    def query(name, *, kwargs, timeout_s):
        calls.append(kwargs["text_prompt"])
        mask = None if missing_tip_mask and kwargs["text_prompt"] == "stove switch lever tip" else np.ones((32, 32), bool)
        return {"instances": [{"mask": mask}]}

    executor = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=3, load=load,
        load_bytes=lambda *args, **kwargs: image.getvalue())), scene=SimpleNamespace(entities={shell.id: shell}))
    monkeypatch.setattr(probe, "public_observation", lambda _: {"src": "perception"})
    monkeypatch.setattr(probe, "private_labels", lambda *args: {"scope": "diagnostic_labels_only", "qpos": [123.]})
    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda item: SimpleNamespace(mask=item["mask"], score=.8)))
    registered = plan(); registered.update(stove_control_features_v1=True,
                                           control_feature_queries=dict(probe.CONTROL_FEATURE_QUERIES))
    refs = probe.capture_measurements(executor, SimpleNamespace(call=query), None,
        registered["cases"][0], registered, tmp_path / "capture", capture=False)
    packet = json.loads(Path(refs["public_measurements"]["path"]).read_text())
    assert "qpos" not in json.dumps(packet)
    assert json.loads(Path(refs["labels"]["path"]).read_text())["qpos"] == [123.]
    assert packet["control_parent_binding"]["parent"] == "e1"
    assert calls == (registered["control_queries"] + list(probe.CONTROL_FEATURE_QUERIES.values())) * 2
    for camera, view in packet["views"].items():
        measured = view["control_features"]
        assert measured["source_step"] == 3 and measured["camera"] == camera and measured["parent"] == "e1"
        assert measured["endpoint_state"] == "unmeasured"
        assert measured["directed_lever"] is None and measured["stove_reference"] is None
        assert len(view["queries"]) == 6
        for query_record in view["queries"]:
            for instance in query_record["instances"]:
                if instance.get("reason") == "current_feature_mask_missing_or_wrong_shape":
                    assert missing_tip_mask and query_record["feature_role"] == "tip"
                    continue
                assert Path(instance["mask"]["path"]).is_file() and Path(instance["cloud"]["path"]).is_file()
