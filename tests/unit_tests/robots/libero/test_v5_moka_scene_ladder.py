"""Opt-in moka queries preserve measured scene association and public format."""

import base64
import copy
import hashlib
import io
import json
import re
from types import SimpleNamespace

import imageio.v2 as imageio
import numpy as np
import pytest

from robots.libero.v5_moka_queries import MOKA_QUERY_LADDER
from robots.libero.v5_runtime import MeasuredScene
from robots.libero.v5_state import Entity, entity_record, serialize


def encoded_item(mask, score=.9):
    stream = io.BytesIO()
    imageio.imwrite(stream, mask.astype(np.uint8) * 255, format="png")
    return {"found": True, "score": score, "mask_shape": list(mask.shape),
            "mask_png_base64": base64.b64encode(stream.getvalue()).decode("ascii")}


class PublicState:
    """Implement the same explicit RGB-D/artifact surface used by scene.refresh."""

    def __init__(self, root):
        self.root = root
        self.latest_step = 2
        self.saved = {}
        row, col = np.mgrid[:20, :20]
        world = np.stack((.15 + col * .001, -.01 + row * .001,
                          1.00 + (row + col) * .001), axis=-1)
        self.pan_mask = np.zeros((20, 20), dtype=bool)
        self.pan_mask[:6] = True
        self.moka_mask = np.zeros((20, 20), dtype=bool)
        self.moka_mask[6:14] = True
        self.no_depth_mask = np.zeros((20, 20), dtype=bool)
        self.no_depth_mask[14:] = True
        world[:6, :, 0] -= .30
        world[:6, :, 2] -= .08
        world[self.no_depth_mask] = np.nan
        secondary = world.copy()
        secondary[..., 0] += .002
        self.worlds = {"agentview": world, "wrist": secondary}

    def load_bytes(self, name):
        return name.encode()

    def load(self, name):
        if name.endswith("_metadata.json"):
            return {"extrinsic_cam2world": np.eye(4)}
        return self.worlds[name.split("_world_")[0]]

    def artifact_path(self, name, *, step):
        return self.root / str(step) / name

    def save(self, name, value, *, step):
        path = self.artifact_path(name, step=step)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.saved[(step, name)] = copy.deepcopy(value)
        if name.endswith(".npz"):
            np.savez_compressed(path, array=value)
        elif name.endswith(".json"):
            def convert(item):
                return item.tolist() if isinstance(item, np.ndarray) else item.item()
            path.write_text(json.dumps(value, default=convert))
        else:
            path.write_bytes(value)
        return path


class SAM:
    def __init__(self, respond):
        self.respond, self.calls = respond, []

    def call(self, method, *, kwargs, timeout_s):
        # The integration may only use public segmentation RPCs. No oracle,
        # object symbols, simulator goals or coordinates can enter this seam.
        assert method == "sam3.segment_all"
        camera = base64.b64decode(kwargs["image_base64"]).decode().split("_high.png")[0]
        record = {"camera": camera, "query": kwargs["text_prompt"], "minimum_score": kwargs["min_score"]}
        self.calls.append(record)
        return self.respond(record)


def scene_for(state, rpc, enabled=None, *, dual=False):
    options = {"dual_view_fusion_v1": dual}
    if enabled is not None:
        options["moka_query_ladder_v1"] = enabled
    return MeasuredScene(SimpleNamespace(_state=state), rpc, 31, **options)


def events_in_public_artifacts(state):
    def walk(value):
        if isinstance(value, dict):
            if "event" in value:
                yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                yield from walk(child)
    return [event for (_, name), value in state.saved.items() if name.endswith(".json")
            for event in walk(value)]


@pytest.mark.parametrize("enabled", [None, False])
def test_default_and_explicit_disabled_keep_nonempty_no_depth_old_sam_path(tmp_path, enabled):
    state = PublicState(tmp_path)
    rpc = SAM(lambda _: {"instances": [encoded_item(state.no_depth_mask)]})
    scene = scene_for(state, rpc, enabled)
    scene.refresh(["moka pot"])
    assert rpc.calls == [{"camera": "agentview", "query": "silver moka coffee pot", "minimum_score": .5}]
    assert scene.calls == 1
    assert not scene.entities
    assert events_in_public_artifacts(state) == []


def test_nonempty_no_depth_falls_through_each_query_and_counts_requests_once(tmp_path):
    state = PublicState(tmp_path)
    def respond(call):
        mask = state.moka_mask if call["query"] == "coffee pot" else state.no_depth_mask
        return {"instances": [encoded_item(mask, .9 if mask is state.no_depth_mask else .3)]}
    rpc = SAM(respond)
    scene = scene_for(state, rpc, True)
    scene.refresh(["moka pot"])
    assert [(c["query"], c["minimum_score"]) for c in rpc.calls] == list(MOKA_QUERY_LADDER)
    events = events_in_public_artifacts(state)
    started = [e for e in events if e["event"] == "query_started"]
    assert scene.calls == len(rpc.calls) == len(started) == 3
    assert [(e["query"], e["minimum_score"]) for e in started] == list(MOKA_QUERY_LADDER)
    moka = next(iter(scene.entities.values()))
    assert moka.name == "moka pot" and moka.visible and re.fullmatch(r"e\d+", moka.id)
    assert moka.xyz[0] > .15


@pytest.mark.parametrize("placement", [False, True])
def test_pan_first_and_excluded_in_both_views_even_for_placement(tmp_path, placement):
    state = PublicState(tmp_path)
    def respond(call):
        if call["query"] == "black frying pan":
            mask = state.pan_mask
        elif call["query"] == "silver moka coffee pot":
            mask = state.pan_mask  # Nonempty, valid depth, but it is only the pan.
        elif call["query"] == "silver octagonal coffee maker":
            mask = state.no_depth_mask
        else:
            mask = state.pan_mask | state.moka_mask
        return {"instances": [encoded_item(mask)]}
    rpc = SAM(respond)
    scene = scene_for(state, rpc, True, dual=True)
    scene.vocabulary.add("frypan")
    kwargs = {}
    if placement:
        placed = Entity("e7", "moka pot", (.1, 0, 1.1), (.08, -.02, 1.05), (.12, .02, 1.15), visible=False)
        target = Entity("e8", "stove", (.16, 0, 1.), (.10, -.05, .90), (.23, .05, 1.1))
        scene.entities = {e.id: e for e in (placed, target)}
        kwargs["placement"] = (placed, target)
    scene.refresh(["moka pot"], **kwargs)
    for camera in ("agentview", "wrist"):
        per_view = [c for c in rpc.calls if c["camera"] == camera]
        assert per_view[0]["query"] == "black frying pan"
        assert [(c["query"], c["minimum_score"]) for c in per_view[1:]] == list(MOKA_QUERY_LADDER)
    assert scene.calls == len(rpc.calls) == 8  # Two pan RPCs plus six actual ladder requests.
    started = [e for e in events_in_public_artifacts(state) if e["event"] == "query_started"]
    assert len(started) == 6
    moka = next(e for e in scene.entities.values() if e.name == "moka pot")
    assert moka.visible and moka.xyz[0] > .15 and moka.lower[2] > .99
    assert set(scene.measurement_views[moka.id]) == {"agentview", "wrist"}
    assert scene.perception_evidence[moka.id]["fusion_version"] == "rgbd_dual_view/1"
    if placement:
        assert moka.id == placed.id and scene.entities[target.id] == target
    instance_events = [e for e in events_in_public_artifacts(state) if e["event"] == "instance"]
    assert any(e.get("reason") == "pan_exclusion" for e in instance_events)


def test_first_usable_query_keeps_fusion_neutral_ids_and_exact_131_text(tmp_path):
    scenes, states = [], []
    for enabled in (False, True):
        state = PublicState(tmp_path / str(enabled))
        rpc = SAM(lambda _: {"instances": [encoded_item(state.moka_mask)]})
        scene = scene_for(state, rpc, enabled, dual=True)
        scene.refresh(["moka pot"])
        states.append(state)
        scenes.append(scene)
    legacy, ladder = scenes
    assert [entity_record(e) for e in ladder.entities.values()] == [entity_record(e) for e in legacy.entities.values()]
    assert ladder.measurement_views == legacy.measurement_views
    instruction = "move the coffee pot onto the stove"
    assert serialize(instruction, list(ladder.entities.values()), .08, None, []) == serialize(
        instruction, list(legacy.entities.values()), .08, None, [])
    text = serialize(instruction, list(ladder.entities.values()), .08, None, [])
    assert "moka_query" not in text and "query_started" not in text and "oracle" not in text
    moka = next(iter(ladder.entities.values()))
    assert set(ladder.measurement_views[moka.id]) == {"agentview", "wrist"}
    states[1].latest_step = 3
    ladder.refresh(["moka pot"])
    assert next(iter(ladder.entities.values())).id == moka.id
    assert next(iter(ladder.entities.values())).source_step == 3
    assert ladder.calls == 4


def test_exhausted_ladder_does_not_turn_cached_object_into_current_measurement(tmp_path):
    state = PublicState(tmp_path)
    rpc = SAM(lambda _: {"instances": [encoded_item(state.no_depth_mask)]})
    scene = scene_for(state, rpc, True, dual=True)
    previous = Entity("e11", "moka pot", (.16, 0, 1.), (.14, -.02, .95), (.18, .02, 1.05), source_step=1)
    scene.entities = {previous.id: previous}
    scene.refresh(["moka pot"])
    measured = scene.entities[previous.id]
    assert not measured.visible and measured.xyz == previous.xyz and measured.source_step == 1
    assert scene.calls == len(rpc.calls) == 6
    assert scene.measurement_views[previous.id] == {}


def test_secondary_only_recall_preserves_cached_neutral_id_and_view_evidence(tmp_path):
    state = PublicState(tmp_path)
    def respond(call):
        mask = state.moka_mask if call["camera"] == "wrist" else state.no_depth_mask
        return {"instances": [encoded_item(mask)]}
    rpc = SAM(respond)
    scene = scene_for(state, rpc, True, dual=True)
    previous = Entity("e11", "moka pot", (.16, 0, 1.), (.14, -.02, .95), (.18, .02, 1.05), source_step=1)
    scene.entities = {previous.id: previous}
    scene.refresh(["moka pot"])
    measured = scene.entities[previous.id]
    assert set(scene.entities) == {previous.id}
    assert measured.visible and measured.source_step == state.latest_step
    assert scene.calls == len(rpc.calls) == 4
    assert set(scene.measurement_views[previous.id]) == {"wrist"}
    evidence = scene.perception_evidence[previous.id]
    assert evidence["source_cameras"] == ["wrist"]
    assert evidence["fusion"]["primary_missing"]
    artifacts = evidence["moka_query_artifacts"]
    assert [artifact["camera"] for artifact in artifacts] == ["agentview", "wrist"]
    for artifact, count in zip(artifacts, (3, 1)):
        path = state.artifact_path(artifact["path"].rsplit("/", 1)[1], step=state.latest_step)
        payload = json.loads(path.read_text())
        assert artifact["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert payload["query_count"] == count and payload["error"] is None
        assert payload["camera"] == artifact["camera"]
        assert payload["world_array_sha256"] == hashlib.sha256(
            state.worlds[artifact["camera"]].tobytes()).hexdigest()


def test_started_query_is_counted_and_persisted_when_sam_rpc_raises(tmp_path):
    state = PublicState(tmp_path)
    def fail(_):
        raise RuntimeError("SAM service disconnected")
    rpc = SAM(fail)
    scene = scene_for(state, rpc, True)
    with pytest.raises(RuntimeError, match="SAM service disconnected"):
        scene.refresh(["moka pot"])
    assert scene.calls == len(rpc.calls) == 1
    assert len([e for e in events_in_public_artifacts(state) if e["event"] == "query_started"]) == 1
    assert len(scene.moka_query_history) == 1
    artifact = scene.moka_query_history[0]
    path = state.artifact_path("moka_query_ladder_v1_0000.json", step=state.latest_step)
    payload = json.loads(path.read_text())
    assert artifact["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert payload["error"] == {"type": "RuntimeError", "message": "SAM service disconnected"}
    assert payload["camera"] == "agentview" and payload["source_step"] == state.latest_step
    assert payload["events"] == [{"event": "query_started", "query": "silver moka coffee pot",
                                  "minimum_score": .5, "query_index": 0}]
