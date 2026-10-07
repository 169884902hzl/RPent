"""A moving drawer is measured afresh; a stationary surface keeps its cache."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity
from tests.unit_tests.robots.libero.test_v5_subtask_release_reverify import transfer, run_transfer


def executor_with_drawer():
    drawer = Entity("target", "drawer", (0., .2, 1.), (-.1, .1, .95), (.1, .3, 1.1), source_step=4)
    cache = replace(drawer, xyz=(0., 0., 1.), lower=(-.1, -.1, .95), upper=(.1, .1, 1.1), source_step=0)
    executor = V5Executor.__new__(V5Executor)
    executor.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4))
    executor.scene = SimpleNamespace(entities={drawer.id: drawer}, refresh=lambda _: None)
    executor.target_cache_v1, executor.strict_place_v6 = True, True
    executor.target_cache = {drawer.id: cache}
    action = Candidate("place", "held", drawer.id, "in")
    return executor, action, drawer, cache


@pytest.mark.parametrize("tool", ["place", "vla_subtask"])
def test_current_moving_target_wins_over_cached_pregrasp_geometry(tool):
    executor, action, drawer, cache = executor_with_drawer()
    executor.scene.refresh = lambda _: pytest.fail("already-current drawer must not add a query")
    action = replace(action, tool=tool)
    assert executor.measured_placement_target(action) is drawer
    assert executor.target_cache[drawer.id] is cache


def test_stale_moving_target_queries_same_public_capture_before_using_geometry():
    executor, action, drawer, _ = executor_with_drawer()
    executor.scene.entities[drawer.id] = replace(drawer, source_step=1)
    calls = []
    def refresh(names):
        calls.append(names)
        executor.scene.entities[drawer.id] = drawer
    executor.scene.refresh = refresh
    assert executor.measured_placement_target(action) is drawer
    assert calls == [["drawer"]]


@pytest.mark.parametrize("problem", ["stale", "occluded", "missing"])
@pytest.mark.parametrize("contact_mode", [False, True])
def test_unmeasured_current_drawer_returns_none_without_reusing_old_cache(problem, contact_mode):
    executor, action, drawer, _ = executor_with_drawer()
    executor.fixture_in_contact_v1 = contact_mode
    executor.scene.entities[drawer.id] = replace(drawer, source_step=1)
    def refresh(_):
        if problem == "missing":
            executor.scene.entities.pop(drawer.id)
        elif problem == "occluded":
            executor.scene.entities[drawer.id] = replace(drawer, visible=False)
    executor.scene.refresh = refresh
    assert executor.measured_placement_target(action) is None


def test_stationary_top_surface_still_uses_the_pre_occlusion_cache():
    executor, action, drawer, cache = executor_with_drawer()
    current = replace(drawer, name="cabinet top surface", geometry="measured_top_surface")
    old = replace(cache, name=current.name, geometry=current.geometry)
    executor.scene.entities[drawer.id] = current
    executor.target_cache[drawer.id] = old
    assert executor.measured_placement_target(replace(action, mode="on")) is old


def test_macro_endpoint_verification_uses_post_contact_drawer_geometry(monkeypatch):
    executor, action, _ = transfer(monkeypatch, enabled=False, relation="in", openings=(.08,))
    state = SimpleNamespace(latest_step=1)
    executor.toolkit = SimpleNamespace(_state=state)
    target = replace(executor.scene.entities[action.target], name="drawer")
    executor.scene.entities[target.id] = target
    executor.target_cache[target.id] = replace(target, source_step=0)
    refresh = executor.scene.refresh
    def measured_refresh(names, **kwargs):
        refresh(names, **kwargs)
        step = executor.scene.entities[action.object].source_step
        state.latest_step = step
        executor.scene.entities[target.id] = replace(target, source_step=step, xyz=(.01, 0., 1.))
    executor.scene.refresh = executor._refresh = measured_refresh
    verified_targets = []
    def verify(first, second, measured, *args, **kwargs):
        verified_targets.append(measured)
        return True
    monkeypatch.setattr("robots.libero.v5_verification.strict_place_verified_v6", verify)
    receipt = run_transfer(executor, action)
    assert receipt["place_verified"] is True
    assert verified_targets[0].source_step == state.latest_step > target.source_step
    assert verified_targets[0].xyz == (.01, 0., 1.)
    assert executor.last_verification_measurements["target"]["source_step"] == state.latest_step


def test_macro_missing_post_contact_drawer_is_unknown_not_verified_by_cache(monkeypatch):
    executor, action, _ = transfer(monkeypatch, enabled=False, relation="in", openings=(.08,))
    state = SimpleNamespace(latest_step=1)
    executor.toolkit = SimpleNamespace(_state=state)
    target = replace(executor.scene.entities[action.target], name="drawer")
    executor.scene.entities[target.id] = target
    executor.target_cache[target.id] = target
    refresh = executor.scene.refresh
    def measured_refresh(names, **kwargs):
        refresh(names, **kwargs)
        state.latest_step = executor.scene.entities[action.object].source_step
        executor.scene.entities[target.id] = replace(target, visible=False, source_step=state.latest_step)
    executor.scene.refresh = executor._refresh = measured_refresh
    monkeypatch.setattr("robots.libero.v5_verification.strict_place_verified_v6",
                        lambda *args, **kwargs: pytest.fail("cached drawer cannot grant verification"))
    receipt = run_transfer(executor, action)
    assert receipt["place_verified"] is None
    assert receipt["verification"] == "unmeasured"
    assert receipt["verification_reason"] == "moving_target_current_measurement_missing"
    assert executor.last_verification_measurements["target"] is None
