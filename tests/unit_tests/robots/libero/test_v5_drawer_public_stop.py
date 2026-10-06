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
