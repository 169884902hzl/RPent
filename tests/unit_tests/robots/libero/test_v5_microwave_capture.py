"""Public evidence and actual withdrawal govern the microwave block stop."""

import copy
import math
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_microwave_capture import (
    MicrowaveEndpointCapture, combine_public_planes, points_mask,
)
from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Entity


def parent():
    return Entity("e1", "microwave", (0., 0., 1.), (-.1, -.1, .9), (.1, .1, 1.2))


def cloud(angle=0., offset=0.):
    normal = np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
    tangent = np.array([-normal[1], normal[0]])
    return np.array([[*(tangent * y + normal * offset), 1 + z]
                     for y in np.linspace(-.08, .08, 12) for z in np.linspace(-.08, .08, 10)])


class State:
    latest_step = 3

    def __init__(self, path):
        self.path = path

    def save(self, name, value, **kwargs):
        path = self.path / name
        np.savez_compressed(path, array=value)
        return path

    def artifact_path(self, name, **kwargs):
        return self.path / name


def view(state, angle=60., frame_offset=0.):
    result = {"frame_moving_mask_overlap": .0}
    from robots.libero.v5_verification import vertical_face
    for kind, points in (("frame", cloud(offset=frame_offset)), ("moving", cloud(angle, .02))):
        name = f"{kind}-{angle}-{frame_offset}.npz"
        state.save(name, points)
        result[kind] = {**vertical_face(points), "path": str(state.artifact_path(name)),
                        "mask_count": 1, "source_step": state.latest_step}
    return result


def test_exact_cloud_mask_does_not_pick_door_pixels_for_fixed_reference():
    world = np.arange(18., dtype=np.float32).reshape(2, 3, 3)
    actual = points_mask(world, world.reshape(-1, 3)[[0, 4]])
    assert np.array_equal(actual, [[True, False, False], [False, True, False]])


def test_dual_view_planes_keep_current_sources_and_explicit_artifacts(tmp_path):
    state = State(tmp_path)
    data = view(state)
    fused = combine_public_planes({"agentview": data, "wrist": copy.deepcopy(data)}, state, parent())
    assert fused["fusion_version"] == "rgbd_dual_view/1"
    assert fused["moving"]["source_cameras"] == ["agentview", "wrist"]
    assert fused["moving"]["source_step"] == state.latest_step
    assert fused["frame"]["sha256"] != fused["moving"]["sha256"]
    assert fused["frame_moving_mask_overlap"] == 0.


def test_camera_disagreement_keeps_plane_unknown(tmp_path):
    state = State(tmp_path)
    fused = combine_public_planes({"agentview": view(state), "wrist": view(state, angle=20.)}, state, parent())
    assert fused["moving"] is None
    assert fused["measurement_counts"]["moving"]["reason"] == "dual_views_disagree"


@pytest.mark.parametrize("corruption", ["ambiguous", "stale"])
def test_invalid_plane_is_not_rescued_by_fusion(tmp_path, corruption):
    state = State(tmp_path)
    data = view(state)
    if corruption == "ambiguous":
        data["moving"]["mask_count"] = 2
    else:
        data["moving"]["source_step"] -= 1
    fused = combine_public_planes({"agentview": data, "wrist": copy.deepcopy(data)}, state, parent())
    assert fused["moving"] is None


def executor_double(*, reached, released=.08):
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.]), _last_obs_gripper=.04,
                        env=SimpleNamespace(terminated=False, truncated=False))
    def release(**kwargs):
        p._last_obs_gripper = released
        return {"executed": True}
    p.release = release
    def move(target, *args, **kwargs):
        if reached:
            p._last_obs_eef_pos = np.asarray(target)
        # Intentionally dishonest command result must never establish clearance.
        return {"waypoint_reached": True}
    return SimpleNamespace(p=p, move=move)


def test_actual_eef_measurement_overrides_successful_waypoint_command():
    capture = MicrowaveEndpointCapture(executor_double(reached=False), parent(), "close")
    evidence = capture.withdraw()
    assert evidence["after"]["clear"] is False
    assert evidence["reason"] == "clearance_not_reached"


def test_release_before_withdrawal_and_measured_clearance():
    capture = MicrowaveEndpointCapture(executor_double(reached=True), parent(), "close")
    evidence = capture.withdraw()
    assert evidence["release"]["executed"] is True
    assert evidence["after"]["clear"] is True


def test_failed_fixture_release_does_not_withdraw_or_admit_clearance():
    capture = MicrowaveEndpointCapture(executor_double(reached=True, released=.04), parent(), "close")
    evidence = capture.withdraw()
    assert evidence["moves"] == []
    assert evidence["reason"] == "fixture_grip_not_released"


def sample(step, timestamp, angle):
    normal = [math.cos(math.radians(angle)), math.sin(math.radians(angle))]
    def plane(normal, identity):
        return {"centre": [.01, .01, 1.], "normal_xy": normal, "residual_p90_m": .001,
                "points": 100, "mask_count": 1, "mask_id": identity,
                "source_cameras": ["agentview", "wrist"]}
    return {"source": "perception", "frame_id": "world", "length_unit": "m", "source_step": step,
            "timestamp_s": timestamp, "arm_withdrawn": True, "occluded": False,
            "frame_moving_mask_overlap": 0., "frame": plane([1., 0.], f"frame{step}"),
            "moving": plane(normal, f"door{step}")}


def test_measured_block_endpoint_stops_before_next_vla_chunk():
    p = SimpleNamespace(_last_obs_gripper=.08, env=SimpleNamespace(terminated=False, truncated=False))
    actions = []
    p._vlm_chunk = lambda prompt: actions.append(prompt)
    ex = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace())
    capture = MicrowaveEndpointCapture(ex, parent(), "close", stop_enabled=True, every_chunks=1)
    capture.before = [sample(1, 0., 60.), sample(2, .3, 60.)]
    capture.capture_pair = lambda: [sample(3, 1., 0.), sample(4, 1.3, 0.)]
    result = ex.vla_act("close the microwave door", 160, "chunk_budget", public_stop=capture.observe)
    assert len(actions) == result["chunks"] == 1
    assert result["stop"] == "microwave_temporal_endpoint_verified"


@pytest.mark.parametrize("unknown", ["mask", "arm", "occluded"])
def test_unknown_public_observation_cannot_stop_chunk_sequence(unknown):
    capture = MicrowaveEndpointCapture(SimpleNamespace(), parent(), "close", stop_enabled=True, every_chunks=1)
    capture.before = [sample(1, 0., 60.), sample(2, .3, 60.)]
    after = [sample(3, 1., 0.), sample(4, 1.3, 0.)]
    if unknown == "mask":
        after[0]["frame_moving_mask_overlap"] = None
    elif unknown == "arm":
        after[0]["arm_withdrawn"] = False
    else:
        after[0]["occluded"] = None
    capture.capture_pair = lambda: after
    assert capture.observe(1)["stop_admitted"] is False


def test_capture_only_flag_does_not_stop_at_measured_endpoint():
    capture = MicrowaveEndpointCapture(SimpleNamespace(), parent(), "close", every_chunks=1)
    capture.before = [sample(1, 0., 60.), sample(2, .3, 60.)]
    capture.capture_pair = lambda: [sample(3, 1., 0.), sample(4, 1.3, 0.)]
    assert capture.observe(1)["endpoint_reached"] is True
    assert capture.observe(1)["stop_admitted"] is False


def test_interrupted_physical_interval_is_not_replaced_with_segmentation_wall_time():
    ex = executor_double(reached=True)
    ex.p._step_env = lambda action: setattr(ex.p.env, "truncated", True)
    capture = MicrowaveEndpointCapture(ex, parent(), "close")
    frames = iter([sample(1, 0., 0.), sample(2, 100., 0.)])
    capture.capture = lambda withdrawal: next(frames)
    pair = capture.capture_pair()
    assert pair[-1]["interval_controls"] == 1
    assert pair[-1]["occluded"] is None


def job4463_baseline_pair():
    # The real 4463 before pair: planes were visible in both agentview frames,
    # but SAM returned no robot instance at step21. Unknown is not clearance.
    pair = [sample(20, 0., 88.3652), sample(21, .3, 88.4388)]
    for frame in pair:
        frame["source_cameras"] = ["agentview"]
        frame["robot_mask_evidence"] = {
            "agentview": {"robot_masks": 1, "occluded": False},
            "wrist": {"robot_masks": 0, "occluded": None},
        }
    pair[1]["occluded"] = None
    pair[1]["robot_mask_evidence"]["agentview"] = {"robot_masks": 0, "occluded": None}
    return pair


def test_job4463_unknown_baseline_retries_real_hold_before_first_contact():
    ex = executor_double(reached=True)
    holds = []
    ex.p._step_env = lambda action: holds.append(action.copy())
    capture = MicrowaveEndpointCapture(ex, parent(), "open", stop_enabled=True)
    bad_pair = job4463_baseline_pair()
    next_pair = [sample(22, 1., 88.36), sample(23, 1.3, 88.44)]
    frames = iter(bad_pair + next_pair)
    capture.capture = lambda withdrawal: next(frames)
    capture.start()
    assert len(holds) == 12
    assert all(np.array_equal(action, np.zeros(7)) for action in holds)
    assert capture.before == next_pair
    assert len(capture.records) == 2
    rejected, admitted = capture.records
    assert rejected["frames"][1]["occluded"] is None
    assert rejected["measurement"]["reason"] == "unobstructed_after_withdrawal_not_measured"
    assert rejected["measurement"]["rejected_observation"] == {"phase": "before", "index": 1}
    assert admitted["baseline_attempt"] == 2
    assert admitted["measurement"]["status"] == "measured"
    capture.capture_pair = lambda: [sample(24, 2., 88.37), sample(25, 2.3, 88.44)]
    endpoint = capture.observe(1)
    assert endpoint["stop_admitted"] is True
    assert endpoint["requested_direction_observed"] is False  # Already open is not an opening success.


@pytest.mark.parametrize("missing", ["robot_mask", "door", "fixed_frame"])
def test_unknown_baseline_caps_at_three_pairs_and_keeps_all_failures(missing):
    ex = executor_double(reached=True)
    holds = []
    ex.p._step_env = lambda action: holds.append(action.copy())
    capture = MicrowaveEndpointCapture(ex, parent(), "open", stop_enabled=True)
    pairs = []
    for attempt in range(3):
        pair = job4463_baseline_pair()
        for index, frame in enumerate(pair):
            frame.update(source_step=20 + 2 * attempt + index, timestamp_s=attempt + index * .3)
            frame["private_endpoint"] = True
            frame["solved"] = True
        if missing != "robot_mask":
            pair[1]["occluded"] = False
            pair[1]["moving" if missing == "door" else "frame"] = None
        pairs.extend(pair)
    frames = iter(pairs)
    capture.capture = lambda withdrawal: next(frames)
    capture.start()
    assert len(holds) == 18
    assert len(capture.records) == 3
    assert all(record["measurement"]["status"] == "unmeasured" for record in capture.records)
    assert capture.before[1]["source_step"] == 25
    capture.capture_pair = lambda: [sample(30, 4., 88.37), sample(31, 4.3, 88.44)]
    assert capture.observe(1)["stop_admitted"] is False


def test_complete_public_baseline_does_not_add_retry_controls():
    ex = executor_double(reached=True)
    holds = []
    ex.p._step_env = lambda action: holds.append(action.copy())
    capture = MicrowaveEndpointCapture(ex, parent(), "open")
    frames = iter([sample(20, 0., 60.), sample(21, .3, 60.)])
    capture.capture = lambda withdrawal: next(frames)
    capture.start()
    assert len(holds) == 6 and len(capture.records) == 1
    assert capture.records[0]["baseline_attempt"] == 1


def test_private_truth_cannot_change_captured_plane_fusion(tmp_path):
    state = State(tmp_path)
    data = view(state)
    baseline = combine_public_planes({"agentview": data}, state, parent())
    data["private_joint_qpos"] = 1.57
    data["solved"] = True
    enriched = combine_public_planes({"agentview": data}, state, parent())
    for kind in ("frame", "moving"):
        assert baseline[kind] == enriched[kind]
    assert baseline["frame_moving_mask_overlap"] == enriched["frame_moving_mask_overlap"]


@pytest.mark.parametrize("case,expected", [("missing", None), ("overlapping", True), ("elsewhere", False)])
def test_occlusion_requires_observed_robot_mask_independent_of_fixture_regions(tmp_path, monkeypatch, case, expected):
    from rpent.robots.components.sam3_client import Sam3Client
    state = State(tmp_path)
    state.load_bytes = lambda name: b"current-public-rgb"
    state.load = lambda name: np.ones((10, 10, 3))
    fixed, moving = np.zeros((10, 10), bool), np.zeros((10, 10), bool)
    fixed[:2, :2] = True
    moving[2:4, :2] = True
    records = {}
    for kind, mask in (("frame", fixed), ("moving", moving)):
        name = f"{kind}_mask.npz"
        state.save(name, mask)
        records[kind] = {"mask_artifact": {"path": str(state.artifact_path(name))}}
    robot = np.zeros((10, 10), bool)
    robot[0 if case == "overlapping" else 8, 0] = True
    monkeypatch.setattr(Sam3Client, "_decode_result", lambda payload: SimpleNamespace(mask=robot))
    rpc = SimpleNamespace(call=lambda *args, **kwargs: {"instances": [] if case == "missing" else [{}]})
    ex = SimpleNamespace(toolkit=SimpleNamespace(_state=state), scene=SimpleNamespace(rpc=rpc, calls=0))
    capture = MicrowaveEndpointCapture(ex, parent(), "close")
    assert capture._robot_occlusion("agentview", records)["occluded"] is expected


def test_default_runtime_does_not_start_capture_and_stop_implies_capture(monkeypatch):
    import robots.libero.v5_microwave_capture as capture_module
    p = SimpleNamespace()
    default = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace())
    assert default.microwave_temporal_public_stop(parent(), "open") is None
    visits = []
    def factory(*args, **kwargs):
        visits.append(kwargs)
        return (lambda chunks: {"stop_admitted": False}), []
    monkeypatch.setattr(capture_module, "make_microwave_public_stop", factory)
    enabled = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(), microwave_temporal_stop_v1=True)
    assert enabled.microwave_temporal_public_stop(parent(), "open") is not None
    assert visits == [{"stop_enabled": True, "every_chunks": 1}]


def test_missing_compound_robot_mask_checks_both_parts_on_same_current_image(tmp_path, monkeypatch):
    from rpent.robots.components.sam3_client import Sam3Client
    state = State(tmp_path)
    state.load_bytes = lambda name: b"current-public-rgb"
    state.load = lambda name: np.ones((10, 10, 3))
    records = {}
    for kind, row in (("frame", 0), ("moving", 2)):
        region = np.zeros((10, 10), bool)
        region[row:row + 2, :2] = True
        name = f"{kind}_mask.npz"
        state.save(name, region)
        records[kind] = {"mask_artifact": {"path": str(state.artifact_path(name))}}
    arm, gripper = np.zeros((10, 10), bool), np.zeros((10, 10), bool)
    arm[8, 8] = True
    gripper[0, 0] = True  # Only the gripper overlaps the measured fixture.
    monkeypatch.setattr(Sam3Client, "_decode_result", lambda item: SimpleNamespace(mask=item["mask"]))
    calls = []
    def segment(method, *, kwargs, timeout_s):
        calls.append(kwargs)
        masks = {"robot arm and gripper": [], "robot arm": [arm], "robot gripper": [gripper]}
        return {"instances": [{"mask": mask} for mask in masks[kwargs["text_prompt"]]]}
    scene = SimpleNamespace(rpc=SimpleNamespace(call=segment), calls=0)
    capture = MicrowaveEndpointCapture(SimpleNamespace(toolkit=SimpleNamespace(_state=state), scene=scene),
                                        parent(), "close")
    evidence = capture._robot_occlusion("agentview", records)
    assert evidence["occluded"] is True
    assert evidence["robot_masks"] == 2 and scene.calls == 3
    assert len({call["image_base64"] for call in calls}) == 1
    assert [query["valid_masks"] for query in evidence["queries"]] == [0, 1, 1]
