"""Complete drawer endpoints must preserve measured direction and fresh evidence."""

from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Entity
from robots.libero.v5_verification import measured_fixture_endpoint


def measurement(extension, step, *, outward=(0., 1.)):
    return {"source_step": step, "outward_axis_xy": outward,
            "frame": {"centre": [0., 0., 1.], "normal_xy": [0., 1.]},
            "moving": {"centre": [0., extension, 1.], "normal_xy": [0., 1.]}}


@pytest.mark.parametrize("extension,mode,expected", [
    (.09, "open", False), (.14, "open", False), (.15, "open", True),
    (.002, "close", False), (.0002, "close", True), (-.005, "close", True),
    (-.2, "close", None),
])
def test_public_complete_endpoint_keeps_signed_flush_and_rejects_partial_open(extension, mode, expected):
    verdict, evidence = measured_fixture_endpoint(
        measurement(.02, 0), measurement(extension, 1), mode,
        drawer=True, signed_drawer_v6=True)
    assert verdict is expected
    assert evidence["measured_signed_extension_m"] == extension


def test_complete_endpoint_does_not_guess_direction_from_a_private_state():
    before, after = measurement(0., 0), measurement(.15, 1)
    del after["outward_axis_xy"]
    assert measured_fixture_endpoint(before, after, "open", drawer=True,
                                    signed_drawer_v6=True)[0] is None
    after["outward_axis_xy"] = [0., -1.]
    assert measured_fixture_endpoint(before, after, "open", drawer=True,
                                    signed_drawer_v6=True)[0] is None


def test_legacy_distance_verdict_remains_unchanged_without_opt_in():
    before, after = measurement(0., 0), measurement(.09, 1)
    assert measured_fixture_endpoint(before, after, "open", drawer=True)[0] is True
    after = measurement(-.005, 1)
    assert measured_fixture_endpoint(before, after, "close", drawer=True)[0] is True


@pytest.mark.parametrize("after", [measurement(.15, 0), None])
def test_stale_or_missing_geometry_cannot_stop_contact(after):
    parent = Entity("e1", "cabinet", (0., 0., 1.), (-.1, -.1, .9), (.1, .1, 1.2))
    scene = SimpleNamespace(entities={parent.id: parent},
                            measure_fixture_endpoint=lambda *args: deepcopy(after))
    executor = V5Executor(SimpleNamespace(primitives=SimpleNamespace()), scene)
    executor._refresh = lambda names: None
    callback = executor.drawer_public_stop(parent, "top drawer", "open", measurement(0., 0))
    assert callback(5) is False
    assert callback(10) is False


def test_public_stop_requires_two_stable_complete_frames_after_a_failed_sample():
    parent = Entity("e1", "cabinet", (0., 0., 1.), (-.1, -.1, .9), (.1, .1, 1.2))
    frames = iter([measurement(.15, 1), measurement(.1, 2),
                   measurement(.16, 3), measurement(.1602, 4)])
    scene = SimpleNamespace(entities={parent.id: parent},
                            measure_fixture_endpoint=lambda *args: next(frames))
    executor = V5Executor(SimpleNamespace(primitives=SimpleNamespace()), scene)
    names = []
    executor._refresh = lambda queries: names.extend(queries)
    check = executor.drawer_public_stop(parent, "top drawer", "open", measurement(0., 0))
    assert [check(n) for n in (1, 5, 10, 15, 20)] == [False, False, False, False, True]
    assert names == ["cabinet"] * 4
    assert len(executor.last_verification_measurements["drawer_public_stop"]) == 4


def test_contact_stops_on_public_measurement_without_reading_native_truth():
    calls = []
    p = SimpleNamespace(_last_obs_gripper=.04,
                        env=SimpleNamespace(terminated=False, truncated=False))
    p._vlm_chunk = lambda prompt: calls.append(prompt)
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace())
    result = executor.vla_act("open the top drawer of the cabinet", 160,
                             "chunk_budget", public_stop=lambda chunks: chunks == 10)
    assert len(calls) == 10
    assert result["stop"] == "measured_fixture_endpoint"
    assert result["chunks"] == 10
    assert "grasp_verified" not in result


@pytest.mark.parametrize("opened,axis,reached", [
    (.04, (0., 1., 0.), True), (.078, None, True),
    (.078, (0., 1., 0.), False), (.078, (0., 1., 0.), True),
])
def test_clearance_requires_real_opening_and_measured_outward_motion(opened, axis, reached):
    parent = Entity("e1", "cabinet", (0., 0., 1.), (-.1, -.1, .9), (.1, .1, 1.2))
    p = SimpleNamespace(_last_obs_gripper=.04, _last_obs_eef_pos=np.array([0., 0., 1.]),
                        env=SimpleNamespace(terminated=False, truncated=False))
    def release(**kwargs):
        assert kwargs == {"max_steps": 40}
        p._last_obs_gripper = opened
        return {"name": "release", "steps_used": 40, "final_gripper_opening": opened}
    p.release = release
    scene = SimpleNamespace(fixture_front_axes={parent.id: axis})
    executor = V5Executor(SimpleNamespace(primitives=p), scene)
    moves, views = [], []
    def move(target, gripper, **kwargs):
        moves.append((target.tolist(), gripper, kwargs))
        return {"waypoint_reached": reached}
    executor.move = move
    executor.retreat = lambda: views.append("view")
    receipt = {}
    executor.clear_drawer_contact(parent, receipt)
    if opened < .075 or axis is None:
        assert not moves and not views
    else:
        assert moves[0][0] == pytest.approx([0., .08, 1.])
        assert moves[0][1] == -1.
        assert moves[0][2]["recoverable"] is True
        assert bool(views) is reached
    assert executor.motion_evidence[0]["name"] == "release"
    assert receipt["fixture_contact_clearance"]["opening_after_m"] == opened


def test_a_dense_rear_strip_cannot_replace_a_broad_measured_front_panel():
    from robots.libero.v5_fixture_parts import measured_drawer_faces

    parent = Entity("e1", "cabinet", (0., .035, 1.05), (-.12, -.08, .9), (.12, .19, 1.15))
    part = Entity("e2", "cabinet top drawer", (0., .14, 1.07),
                  (-.115, .09, 1.02), (.115, .195, 1.12), part_of="e1")
    strip = np.array([(x, .10, z) for x in np.linspace(-.053, .053, 70)
                      for z in np.linspace(1.03, 1.11, 50)])
    front = np.array([(x, .18, z) for x in np.linspace(-.10, .10, 35)
                      for z in np.linspace(1.03, 1.11, 35)])
    cloud = np.concatenate([strip, front])
    old, _ = measured_drawer_faces(cloud, parent, part, (0., 1., 0.),
                                   moving_part=part, measured_bounds_depth=True)
    fixed, _ = measured_drawer_faces(cloud, parent, part, (0., 1., 0.),
                                     moving_part=part, measured_bounds_depth=True, frontmost_panel=True)
    assert old["moving"]["centre"][1] == pytest.approx(.10)
    assert fixed["moving"]["centre"][1] == pytest.approx(.18)


def test_a_private_scoring_failure_is_recorded_without_a_control_exception():
    from scripts.probe_v5_skill501_original import fixture_score_sample

    class RPC:
        def call(self, *args, **kwargs):
            raise RuntimeError("diagnostic read unavailable")

    evidence = {"private_fixture_scores": []}
    fixture_score_sample(RPC(), {"kind": "articulate"}, evidence, "after_actual_chunk", 3)
    assert evidence["private_fixture_scores"][0]["label"] is None
    assert evidence["private_fixture_scores"][0]["used_for_control"] is False
    assert evidence["private_fixture_scoring_failure"] is True


def test_fixture_private_labels_cannot_change_release_clearance_or_retreat():
    from scripts.probe_v5_skill501_original import contact_probe_controls, row_infrastructure_failure
    from robots.libero.v5_state import Candidate

    obj = Entity("e1", "cabinet", (0., 0., 1.), (-.1, -.1, .9), (.1, .1, 1.2))
    controls = []
    p = SimpleNamespace(_vlm_chunk=lambda *a, **kw: None,
                        release=lambda **kw: controls.append("release") or {"steps_used": 40})
    executor = SimpleNamespace(scene=SimpleNamespace(entities={obj.id: obj}), p=p,
        stage_grasp=lambda *a, **kw: None, vla_act=lambda *a, **kw: None,
        _execute=lambda *a, **kw: None, move=lambda *a, **kw: controls.append("move") or {"waypoint_reached": True},
        motion_evidence=[], retreat=lambda: controls.append("retreat"), grasp_independent_views_v1=False)
    original_release, original_move, original_retreat = p.release, executor.move, executor.retreat
    class RPC:
        def call(self, *args, **kwargs):
            raise ConnectionError("scoring service unavailable")
    evidence = {}
    with contact_probe_controls(executor, RPC(), {"kind": "articulate"},
                                {"executor": "current", "private_fixture_sync": True},
                                Candidate("articulate", obj.id, mode="close"), evidence):
        assert p.release(max_steps=40) == {"steps_used": 40}
        assert executor.move([0., .08, 1.], -1.) == {"waypoint_reached": True}
        executor.retreat()
    assert controls == ["release", "move", "retreat"]
    assert [r["phase"] for r in evidence["private_fixture_scores"]] == [
        "after_fixture_release", "after_measured_contact_clearance", "after_view_retreat_attempt"]
    assert p.release is original_release and executor.move is original_move and executor.retreat is original_retreat
    assert row_infrastructure_failure({"first_attempt": {"contact_evidence": evidence}})
