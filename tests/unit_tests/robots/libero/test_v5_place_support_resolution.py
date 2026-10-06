"""A furniture selector is not a measured support plane."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity


def scene_executor(*, strict=True, cache=True):
    obj = Entity("e1", "bowl", (0., 0., 1.15), (-.04, -.04, 1.1), (.04, .04, 1.2))
    cabinet = Entity("e2", "cabinet", (-.1, .3, .95), (-.2, .2, .85), (0., .4, 1.05))
    support = Entity("e3", "cabinet top surface", (.2, .3, 1.07),
                     (.1, .2, 1.06), (.3, .4, 1.08), part_of=cabinet.id,
                     geometry="measured_top_surface")
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.3]), _last_obs_gripper=.08,
                        env=SimpleNamespace(terminated=False, truncated=False),
                        release=lambda: None, set_gripper=lambda **kwargs: None)
    scene = SimpleNamespace(entities={e.id: e for e in (obj, cabinet, support)},
                            view_axes=((1, 0, 0), (0, -1, 0)),
                            last_measurement_s={obj.name: 0.}, refresh=lambda *args, **kwargs: None)
    executor = V5Executor(SimpleNamespace(primitives=p, _state=SimpleNamespace(latest_step=2)), scene,
                          strict_place_v6=strict, target_cache_v1=cache, adjust_place_v1=True)
    executor.held, executor.held_offset = obj.id, np.array([0., 0., .15])
    executor.capture = executor.retreat = lambda: None
    executor._refresh = lambda *args: None
    return executor, obj, cabinet, support


def test_support_uses_pre_occlusion_public_cache_and_deduplicates_current_identity():
    executor, obj, cabinet, support = scene_executor()
    cached = replace(support, xyz=(.25, .35, 1.07), lower=(.15, .25, 1.06), upper=(.35, .45, 1.08))
    executor.target_cache[support.id] = cached
    assert executor.measured_placement_target(Candidate("place", obj.id, cabinet.id, "on")) is cached
    executor.scene.entities[support.id] = replace(support, visible=False)
    assert executor.measured_placement_target(Candidate("place", obj.id, cabinet.id, "on")) is cached


@pytest.mark.parametrize("problem", ["no_support", "ambiguous", "unrelated_parent", "unmeasured_geometry", "hidden_without_cache"])
@pytest.mark.parametrize("tool", ["place", "vla_subtask"])
def test_unresolved_support_remains_unmeasured_and_never_executes(problem, tool):
    executor, obj, cabinet, support = scene_executor()
    if problem == "no_support":
        del executor.scene.entities[support.id]
    elif problem == "ambiguous":
        executor.scene.entities["e4"] = replace(support, id="e4")
    elif problem == "unrelated_parent":
        executor.scene.entities[support.id] = replace(support, part_of="e8")
    elif problem == "unmeasured_geometry":
        executor.scene.entities[support.id] = replace(support, geometry="measured_front_surface")
    else:
        executor.scene.entities[support.id] = replace(support, visible=False)
    executor.move = executor.vla_act = lambda *args, **kwargs: pytest.fail("an unresolved support requested an action")
    receipt = {}
    executor._execute(Candidate(tool, obj.id, cabinet.id, "on"), receipt, None)
    assert receipt == {"executed": False, "place_verified": None, "verification": "unmeasured",
                       "failure_reason": "selected_support_surface_not_uniquely_measured"}
    assert executor.held == obj.id


@pytest.mark.parametrize("mode,strict,explicit_part", [("on", False, False), ("in", True, False), ("on", True, True)])
def test_legacy_in_and_explicit_part_keep_their_selected_target(mode, strict, explicit_part):
    executor, obj, cabinet, support = scene_executor(strict=strict)
    target = support if explicit_part else cabinet
    assert executor.measured_placement_target(Candidate("place", obj.id, target.id, mode)) is target


@pytest.mark.parametrize("tool", ["place", "adjust_place", "vla_subtask"])
def test_both_arms_verify_same_support_and_subtask_keeps_selector_prompt(monkeypatch, tool):
    executor, obj, cabinet, support = scene_executor()
    monkeypatch.setattr("robots.libero.v5_runtime.time.perf_counter", lambda: 1.)
    observed_targets, moves, prompts = [], [], []
    def verify(first, second, target, *args, **kwargs):
        observed_targets.append(target)
        return False
    monkeypatch.setattr("robots.libero.v5_verification.strict_place_verified_v6", verify)
    executor.move = lambda xyz, gripper: moves.append(np.array(xyz))
    executor.vla_act = lambda prompt, *args: prompts.append(prompt) or {"executed": True, "chunks": 1}
    receipt = {}
    executor._execute(Candidate(tool, obj.id, cabinet.id, "on"), receipt, None)
    assert observed_targets == [support]
    assert executor.last_verification_measurements["target"]["id"] == support.id
    assert receipt["verification_rule"] == "strict_place/6-dev"
    if tool == "vla_subtask":
        assert prompts == ["put the bowl on the cabinet"]
        assert not moves
    else:
        assert not prompts
        assert moves[2] == pytest.approx([.2, .3, 1.28])


def test_two_public_cached_support_ids_are_ambiguous():
    executor, obj, cabinet, support = scene_executor()
    executor.target_cache["e4"] = replace(support, id="e4")
    assert executor.measured_placement_target(Candidate("place", obj.id, cabinet.id, "on")) is None
