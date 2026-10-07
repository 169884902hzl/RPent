"""Two current released observations stop the macro, never private completion."""

import copy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_placement_endpoint_stop import PlacementEndpointStop, measure_placement_endpoint
from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity


def support():
    return Entity("e2", "stove", (0., 0., .95), (-.1, -.1, .9), (.1, .1, 1.), source_step=0)


def placed(step, **kwargs):
    return Entity("e1", "moka pot", (0., 0., 1.025), (-.02, -.02, 1.), (.02, .02, 1.05),
                  source_step=step, **kwargs)


def frame(step):
    return {"source": "perception", "capture_step": step, "entity": placed(step),
            "opening_m": .08, "eef_xyz_m": [.2, .2, 1.2], "capture_wall_timestamp_s": float(step)}


def judge(first=None, second=None, target=None, relation="on", controls=6):
    return measure_placement_endpoint(first or frame(1), second or frame(2), target or support(), relation,
                                     baseline_step=0, actual_hold_controls=controls)


def test_fresh_supported_released_pair_admits_endpoint_without_new_thresholds():
    result = judge()
    assert result["place_verified"] is True and result["stop_admitted"] is True
    assert result["interval_s"] == pytest.approx(.3)
    assert result["strict6_verdicts"] == [True, True]


def test_measured_in_containment_uses_same_strict6_verifier():
    target = replace(support(), name="bowl", upper=(.1, .1, 1.1))
    assert judge(target=target, relation="in")["stop_admitted"] is True


@pytest.mark.parametrize("kind", ["opening_first", "opening_second", "withdrawal_first", "withdrawal_second", "hover", "outside", "unstable"])
def test_physical_preconditions_missing_or_placement_failure_do_not_stop(kind):
    first, second = frame(1), frame(2)
    if kind.startswith("opening"):
        (first if kind.endswith("first") else second)["opening_m"] = .04
    elif kind.startswith("withdrawal"):
        (first if kind.endswith("first") else second)["eef_xyz_m"] = [0., 0., 1.025]
    elif kind == "hover":
        for sample in (first, second):
            sample["entity"] = replace(sample["entity"], xyz=(0., 0., 1.06), lower=(-.02, -.02, 1.035))
    elif kind == "outside":
        for sample in (first, second):
            sample["entity"] = replace(sample["entity"], xyz=(.2, 0., 1.025),
                                       lower=(.18, -.02, 1.), upper=(.22, .02, 1.05))
    else:
        second["entity"] = replace(second["entity"], xyz=(.03, 0., 1.025))
    result = judge(first, second)
    assert result["place_verified"] is False and result["stop_admitted"] is False


@pytest.mark.parametrize("kind", ["cached", "duplicate_step", "wrong_capture_step", "missing", "private_source", "future_target", "early_first"])
def test_cached_or_unmeasured_evidence_cannot_admit_endpoint(kind):
    first, second, target = frame(1), frame(2), support()
    if kind == "cached":
        second["entity"] = replace(second["entity"], visible=False, geometry="cached_perception_visible_surface")
    elif kind == "duplicate_step":
        second = copy.deepcopy(first)
    elif kind == "wrong_capture_step":
        second["capture_step"] = 3
    elif kind == "missing":
        second["entity"] = None
    elif kind == "private_source":
        second["source"] = "sim_truth"
    elif kind == "future_target":
        target = replace(target, source_step=9)
    else:
        first = frame(0)
    result = judge(first, second, target)
    assert result["place_verified"] is None and result["stop_admitted"] is False


@pytest.mark.parametrize("target,relation", [(replace(support(), name="area stove"), "on"),
                                           (replace(support(), name="microwave"), "in"),
                                           (replace(support(), name="cabinet top drawer"), "in")])
def test_unknown_or_moving_support_does_not_become_a_stationary_endpoint(target, relation):
    result = judge(target=target, relation=relation)
    assert result["place_verified"] is None and result["stop_admitted"] is False


def test_wall_latency_does_not_substitute_incomplete_physical_stability_hold():
    first, second = frame(1), frame(2)
    second["capture_wall_timestamp_s"] = 600.
    result = judge(first, second, controls=5)
    assert result["reason"] == "physical_stability_interval_incomplete"
    assert result["stop_admitted"] is False


def test_private_completion_and_joint_labels_cannot_rescue_a_failed_endpoint():
    first, second = frame(1), frame(2)
    second["opening_m"] = .04
    before = judge(first, second)
    for sample in (first, second):
        sample["oracle.status"] = True
        sample["native_success"] = True
        sample["private_placement_predicate"] = True
    after = judge(first, second)
    assert before["place_verified"] == after["place_verified"] is False
    assert after["stop_admitted"] is False


def fake_executor(*, opening=.08, stale=False, interrupt=False, enabled=False):
    initial, target = placed(0), support()
    state = SimpleNamespace(latest_step=0)
    p = SimpleNamespace(_last_obs_gripper=opening, _last_obs_eef_pos=np.array([.2, .2, 1.2]),
                        env=SimpleNamespace(terminated=False, truncated=False))
    controls, queries, chunks = [], [], []
    def hold(action):
        controls.append(np.array(action, copy=True))
        if interrupt:
            p.env.truncated = True
    p._step_env = hold
    p._vlm_chunk = lambda prompt: chunks.append(prompt)
    scene = SimpleNamespace(entities={initial.id: initial, target.id: target}, dual_view_fusion_v1=True,
                            perception_evidence={}, view_axes=((1., 0., 0.), (0., -1., 0.)))
    def refresh(names, **kwargs):
        queries.append((names, kwargs))
        scene.entities[initial.id] = placed(0 if stale else state.latest_step)
        scene.perception_evidence[initial.id] = {"source_cameras": ["agentview", "wrist"], "fusion_version": "rgbd_dual_view/1"}
    scene.refresh = refresh
    ex = V5Executor(SimpleNamespace(primitives=p, _state=state), scene, max_chunks=320,
                    placement_endpoint_stop_v1=enabled)
    def capture(**kwargs):
        state.latest_step += 1
    ex.capture = capture
    # Added release/servo/retreat or oracle status reads must not be necessary.
    def prohibited(*args, **kwargs):
        raise AssertionError("a placement endpoint probe cannot add contact commands")
    p.release = ex.move = ex.retreat = prohibited
    return ex, initial, target, controls, queries, chunks


def test_unopened_gripper_never_probes_or_adds_stability_controls():
    ex, obj, target, controls, queries, _ = fake_executor(opening=.04)
    collector = PlacementEndpointStop(ex, obj, target, "on")
    assert collector.observe(1)["status"] == "not_probed"
    assert controls == queries == []
    assert ex.toolkit._state.latest_step == 0


def test_probe_uses_main_camera_with_fusion_and_exactly_six_neutral_controls():
    ex, obj, target, controls, queries, _ = fake_executor()
    collector = PlacementEndpointStop(ex, obj, target, "on")
    result = collector.observe(1)
    assert result["stop_admitted"] is True
    assert len(controls) == 6 and all(np.array_equal(action, np.zeros(7)) for action in controls)
    assert all(kwargs["camera_view"] == "agentview" and kwargs["placement"] == (obj, target) for _, kwargs in queries)
    assert result["first"]["entity"]["source_step"] == 1
    assert result["second"]["entity"]["source_step"] == 2


def test_stale_measurement_does_not_stop_vla_macro():
    ex, obj, target, controls, queries, chunks = fake_executor(stale=True)
    collector = PlacementEndpointStop(ex, obj, target, "on")
    result = ex.vla_act("place the moka pot on the stove", 2, "chunk_budget", public_stop=collector.observe)
    assert len(chunks) == 2
    assert result["stop"] == "chunk_budget"
    assert all(record["stop_admitted"] is False for record in collector.records)


def test_admitted_endpoint_prevents_every_subsequent_vla_block():
    ex, obj, target, _, _, chunks = fake_executor()
    collector = PlacementEndpointStop(ex, obj, target, "on")
    result = ex.vla_act("place the moka pot on the stove", 320, "chunk_budget", public_stop=collector.observe)
    assert len(chunks) == result["chunks"] == 1
    assert result["stop"] == "placement_endpoint_verified"


def test_interrupted_hold_retains_unknown_endpoint():
    ex, obj, target, controls, _, _ = fake_executor(interrupt=True)
    collector = PlacementEndpointStop(ex, obj, target, "on")
    result = collector.observe(1)
    assert len(controls) == 1
    assert result["place_verified"] is None and result["stop_admitted"] is False


def test_runtime_subtask_returns_public_verification_without_later_contact_or_refresh():
    ex, obj, target, controls, queries, chunks = fake_executor(enabled=True)
    ex.measured_placement_target = lambda action: target
    ex._refresh = lambda names: pytest.fail("must not re-enter post-hoc placement after public endpoint")
    receipt = {}
    ex.execute_subtask(Candidate("vla_subtask", obj.id, target.id, "on"), receipt)
    assert receipt["place_verified"] is True
    assert receipt["verification_scope"] == "fresh_public_strict6_placement_endpoint"
    assert len(chunks) == 1 and len(controls) == 6
    assert "placement_endpoint_stop" in ex.last_verification_measurements


def test_stop_is_default_off():
    ex, *_ = fake_executor()
    assert ex.placement_endpoint_stop_v1 is False
