"""Public fixture cleanup must precede the unchanged expert and model binding."""

import base64
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_oracle_policy import OriginalOraclePolicy
from robots.libero.v5_runtime import MeasuredScene
from robots.libero.v5_state import Candidate, Entity
from robots.libero.v5_subtasks import subtask_prompt


def saved_scene():
    path = Path(__file__).resolve().parents[4] / "coordination/drawer_public_identity_hold_CPU_20261008/diagnosis4533/final_public.json"
    frame = json.loads(path.read_text())
    scene = MeasuredScene.__new__(MeasuredScene)
    scene.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=frame["source_step"]))
    scene.entities = {
        eid: Entity(**{key: item for key, item in value["current"].items() if key in Entity.__dataclass_fields__})
        for eid, value in frame["entities"].items()
    }
    scene.fixture_alias_history = []
    scene.perception_evidence = {eid: value["perception_evidence"] for eid, value in frame["entities"].items()}
    return scene


def test_saved_public_failure_is_resolved_for_both_default_consumers():
    scene = saved_scene()
    before = dict(scene.entities)
    policy = OriginalOraclePolicy(None)
    label = "white_cabinet_1_top_side"
    axes = ((1., 0., 0.), (0., -1., 0.))
    assert policy.bind(label, list(scene.entities.values()), "put the bowl on top of the cabinet", axes,
                       source_reference=False) is None
    scene.canonicalize_fixture_fragments({}, "agentview")
    assert set(before) - set(scene.entities) == {"e107", "e110", "e40", "e86"}
    target = policy.bind(label, list(scene.entities.values()), "put the bowl on top of the cabinet", axes,
                         source_reference=False)
    assert target.id == "e104" and target is before["e104"]
    assert subtask_prompt(Candidate("vla_subtask", "e15", "e104", "on"), scene.entities) == "put the bowl on the cabinet top surface"
    assert all(scene.entities[eid] is before[eid] for eid in scene.entities)
    assert scene.fixture_alias_history[-1]["private_truth_used"] is False


@pytest.mark.parametrize("condition", ["stale_drawer", "second_parent", "missing_drawer"])
def test_runtime_cleanup_keeps_unproven_fragment(condition):
    scene = saved_scene()
    if condition == "stale_drawer":
        scene.entities["e47"] = replace(scene.entities["e47"], source_step=0)
    elif condition == "second_parent":
        scene.entities["other_parent"] = replace(scene.entities["e12"], id="other_parent")
    else:
        del scene.entities["e47"]
    scene.canonicalize_fixture_fragments({}, "agentview")
    assert "e107" in scene.entities


def test_runtime_mask_overlap_is_only_saved_metadata():
    scene = saved_scene()
    mask = np.asarray([[True, True], [False, True]])
    scene.canonicalize_fixture_fragments({"e107": mask, "e47": mask}, "agentview")
    overlap = scene.fixture_alias_history[-1]["aliases"][0]["same_capture_sam_masks"]
    assert overlap == {"camera": "agentview", "source_step": 5, "iou": 1.}
    assert "e107" not in scene.entities


@pytest.mark.parametrize("enabled", [False, True])
def test_actual_refresh_queries_drawer_and_runs_cleanup_only_when_enabled(monkeypatch, enabled):
    from rpent.robots.components.sam3_client import Sam3Client

    world = np.ones((12, 12, 3))
    state = SimpleNamespace(latest_step=1, load_bytes=lambda name: name.encode(),
                            load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else world)
    queries = []
    def call(method, kwargs, **unused):
        queries.append((base64.b64decode(kwargs["image_base64"]).decode(), kwargs["text_prompt"]))
        return {"instances": []}
    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda value: SimpleNamespace(mask=value["mask"])))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=call), 0,
                          dual_view_fusion_v1=False, fixture_fragment_alias_v1=enabled)
    scene.refresh(["cabinet"])
    assert any(query in ("open drawer of the small cabinet", "drawer") for _, query in queries) is enabled
    assert ("drawer" in scene.vocabulary) is enabled
    assert len(scene.fixture_alias_history) == int(enabled)
