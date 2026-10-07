"""Public operating-area filtering keeps ambiguous or missing targets unknown."""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from robots.libero import v5_subtasks
from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Entity
from scripts.probe_v5_moka_transfer_public_20261007 import execute_original_subtask


def stove(identity, xyz, *, radius=.06, visible=True):
    return Entity(identity, "stove", xyz,
                  (xyz[0] - radius, xyz[1] - radius, xyz[2] - .02),
                  (xyz[0] + radius, xyz[1] + radius, xyz[2] + .02), visible=visible)


def transfer(monkeypatch, *, refreshed, before=(), eef=(0., 0., 1.1), private_done=False,
             point_guard=None):
    calls = []
    scene = SimpleNamespace(entities={item.id: item for item in before})

    def refresh(names):
        calls.append(("refresh", names))
        scene.entities = {item.id: item for item in refreshed}

    def rpc(method, **kwargs):
        calls.append((method, kwargs))
        if method == "oracle.status":
            return {"done": private_done}
        return {}

    def execute(executor, action, receipt):
        calls.append(("execute", action))
        receipt.update(executed=True, place_verified=True, verification="verified")

    scene.refresh = refresh
    if point_guard is not None:
        scene.stove_public_identity_v1 = True
        scene.stove_operating_area = lambda measured_eef: point_guard
        scene.stove_identity_history = [{"source": "perception", "aliases": []}]
    executor = SimpleNamespace(
        scene=scene,
        p=SimpleNamespace(_last_obs_eef_pos=eef, env=SimpleNamespace(
            _client=SimpleNamespace(call=rpc), complete_skill=nullcontext)),
        last_verification_measurements={},
    )
    monkeypatch.setattr(V5Executor, "execute_subtask", execute)
    monkeypatch.setattr(v5_subtasks, "subtask_prompt", lambda *args: "public bound sentence")
    obj = Entity("moka", "moka pot", (.1, .1, .95), (.08, .08, .9), (.12, .12, 1.0))
    receipt, evidence = {}, {}
    execute_original_subtask(executor, {"original_goal_source": True,
                                     "instruction": "put the moka pot on the stove"},
                             {"max_chunks": 320}, obj, receipt, evidence)
    return receipt, evidence, calls


@pytest.mark.parametrize("private_done", [False, True])
def test_4408_operating_area_outlier_does_not_block_public_unique_stove(monkeypatch, private_done):
    # Both measured centres are from 4408. Public EEF/bounds define the filter;
    # private completion labels deliberately vary without changing selection.
    near = Entity("e114", "stove", (-.0227, .2017, .9258),
                  (-.137939453125, .10995849609375, .90478515625),
                  (.045562744140625, .294921875, .93115234375))
    remote = Entity("e54", "stove", (-1.4668, .0641, .9092),
                    (-1.6962890625, -.38818359375, .90087890625),
                    (-1.36328125, .388916015625, .93212890625))
    eef = (-.19717544317245483, -.02297159470617771, 1.1804975271224976)
    receipt, evidence, calls = transfer(monkeypatch, refreshed=[near, remote], before=[near, remote],
                                        eef=eef, private_done=private_done)
    assert receipt["executed"] is True and receipt["target"] == "e114"
    assert calls[0] == ("refresh", ["stove"])
    binding = evidence["public_stove_binding_evidence"]
    assert binding["outcome"] == "unique" and binding["private_goal_used_for_selection"] is False
    assert binding["max_nearest_bbox_xy_distance_m"] == 1.0
    assert binding["public_eef_xyz_m"] == list(eef)
    assert len(evidence["public_stove_entities_before_refresh"]) == 2
    outlier = next(row for row in binding["entities"] if row["id"] == "e54")
    assert outlier["nearest_bbox_xy_distance_m"] > 1.
    assert outlier["rejection_reason"] == "outside_public_operating_area"
    assert outlier["bbox_m"]["lower"] == list(remote.lower)


def test_two_near_public_stoves_stay_ambiguous_and_never_query_private_goal(monkeypatch):
    receipt, evidence, calls = transfer(monkeypatch, refreshed=[
        stove("first", (0., .2, .9)), stove("second", (.3, .2, .9))])
    assert receipt["executed"] is False and receipt["place_verified"] is None
    assert evidence["public_stove_binding_evidence"]["outcome"] == "ambiguous"
    assert calls == [("refresh", ["stove"])]


@pytest.mark.parametrize("private_done", [False, True])
def test_4430_dual_view_duplicate_is_one_public_target(monkeypatch, private_done):
    fused = Entity("e11", "stove", (-.05, .19, .919),
                   (-.14309399489647834, .09560546875, .905029296875),
                   (.043304443359375, .281005859375, .9304421164772727))
    single = Entity("e47", "stove", (-.01, .19, .918),
                    (-.140625, .095947265625, .904296875),
                    (.043304443359375, .2822265625, .93115234375))
    receipt, evidence, _ = transfer(monkeypatch, refreshed=[fused, single],
                                    private_done=private_done)
    assert receipt["executed"] is True and receipt["target"] == "e11"
    binding = evidence["public_stove_binding_evidence"]
    assert binding["eligible_entity_ids"] == ["e11"]
    duplicate = next(row for row in binding["entities"] if row["id"] == "e47")
    assert duplicate["representative_id"] == "e11"
    assert duplicate["disposition"] == "duplicate_measurement"


@pytest.mark.parametrize("missing", ["no_detection", "invisible", "eef", "bbox"])
def test_missing_current_measurement_remains_unknown(monkeypatch, missing):
    near = stove("near", (0., .2, .9))
    eef = None if missing == "eef" else (0., 0., 1.1)
    if missing == "no_detection":
        refreshed = []
    elif missing == "invisible":
        refreshed = [stove("near", (0., .2, .9), visible=False)]
    elif missing == "bbox":
        refreshed = [SimpleNamespace(id="near", name="stove", xyz=near.xyz,
                                     lower=None, upper=near.upper, visible=True)]
    else:
        refreshed = [near]
    receipt, evidence, calls = transfer(monkeypatch, refreshed=refreshed, before=[near], eef=eef)
    assert receipt["executed"] is False and receipt["place_verified"] is None
    assert receipt["verification"] == "unmeasured"
    assert evidence["public_stove_binding_evidence"]["outcome"] in ("unmeasured", "missing")
    assert calls == [("refresh", ["stove"])]


def test_filter_uses_nearest_measured_bbox_instead_of_centre_distance(monkeypatch):
    wide = Entity("wide", "stove", (1.2, 0., .9), (.5, -.1, .85), (1.9, .1, .95))
    receipt, evidence, _ = transfer(monkeypatch, refreshed=[wide])
    assert receipt["executed"] is True
    assert evidence["public_stove_binding_evidence"]["entities"][0]["nearest_bbox_xy_distance_m"] == .5


def test_opted_in_transfer_rejects_wide_bbox_tail_by_current_public_point_support(monkeypatch):
    near = stove("near", (0., .2, .9))
    remote = Entity("remote", "stove", (-1.46, 0., .91), (-1.69, -.38, .90), (-.64, .38, 1.2))
    guard = {
        "near": {"disposition": "eligible", "rejection_reason": None,
                 "median_xy_distance_m": .2, "point_support_fraction": 1.},
        "remote": {"disposition": "rejected", "rejection_reason": "outside_public_point_supported_operating_area",
                   "median_xy_distance_m": 1.46, "point_support_fraction": .05},
    }
    receipt, evidence, _ = transfer(monkeypatch, refreshed=[near, remote], point_guard=guard)
    assert receipt["executed"] is True and receipt["target"] == "near"
    binding = evidence["public_stove_binding_evidence"]
    assert binding["eligible_entity_ids"] == ["near"]
    assert binding["version"] == "public_stove_point_operating_area/3-dev"
    distant = next(record for record in binding["entities"] if record["id"] == "remote")
    assert distant["nearest_bbox_xy_distance_m"] < 1.
    assert distant["point_supported_operating_area"] == guard["remote"]


def test_opted_in_transfer_does_not_fall_back_when_point_evidence_is_missing(monkeypatch):
    guard = {"near": {"disposition": "unmeasured", "rejection_reason": "current_public_points_missing"}}
    receipt, evidence, calls = transfer(monkeypatch, refreshed=[stove("near", (0., .2, .9))], point_guard=guard)
    assert receipt["executed"] is False
    assert evidence["public_stove_binding_evidence"]["outcome"] == "unmeasured"
    assert calls == [("refresh", ["stove"])]
