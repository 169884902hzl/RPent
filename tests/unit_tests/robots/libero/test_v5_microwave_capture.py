"""Public evidence and actual withdrawal govern the microwave block stop."""

import copy
import math
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_microwave_capture import (
    MicrowaveEndpointCapture, combine_public_planes, points_mask, public_endpoint_candidate,
    stable_public_endpoint_candidates,
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


@pytest.mark.parametrize("wrist_occluded", [None, True])
def test_unknown_or_occluded_wrist_cannot_poison_clear_current_main_planes(tmp_path, wrist_occluded):
    state = State(tmp_path)
    views = {"agentview": view(state), "wrist": view(state, angle=20.)}
    fused = combine_public_planes(views, state, parent(), occlusion={
        "agentview": {"occluded": False}, "wrist": {"occluded": wrist_occluded}})
    assert fused["frame"]["source_cameras"] == ["agentview"]
    assert fused["moving"]["source_cameras"] == ["agentview"]
    assert fused["views"]["wrist"] is views["wrist"]
    assert fused["fusion_version"] == "rgbd_dual_view/1"


def test_all_unknown_views_supply_no_endpoint_planes(tmp_path):
    state = State(tmp_path)
    fused = combine_public_planes({"agentview": view(state), "wrist": view(state)}, state, parent(),
                                  occlusion={"agentview": {"occluded": None}, "wrist": {"occluded": None}})
    assert fused["frame"] is None and fused["moving"] is None
    assert public_endpoint_candidate(fused, "close")["endpoint_candidate"] is False


def test_two_clear_disagreeing_views_still_cannot_supply_endpoint(tmp_path):
    state = State(tmp_path)
    fused = combine_public_planes({"agentview": view(state), "wrist": view(state, angle=20.)},
        state, parent(), occlusion={"agentview": {"occluded": False}, "wrist": {"occluded": False}})
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


def observation_sample(step=20):
    measured = sample(step, 0., 60.)
    measured["frame"]["mask_count"] = measured["moving"]["mask_count"] = 1
    measured["frame"]["centre"] = [.12, .08, 1.]
    measured["moving"]["centre"] = [.16, .16, 1.]
    return measured


def observation_executor(*, reached=True):
    ex = executor_double(reached=reached)
    ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=20))
    return ex


def test_observation_move_raises_before_translating_from_current_public_midpoint():
    ex = observation_executor()
    capture = MicrowaveEndpointCapture(ex, parent(), "open", observation_pose_enabled=True)
    evidence = capture.observation_pose(observation_sample())
    assert evidence["status"] == "reached"
    assert [move["phase"] for move in evidence["moves"]] == ["raise", "translate"]
    np.testing.assert_allclose(evidence["moves"][0]["target_xyz_m"], [0., 0., 1.35])
    delta = np.array([.14, .12])
    delta *= .15 / np.linalg.norm(delta)
    np.testing.assert_allclose(evidence["moves"][1]["target_xyz_m"], [*delta, 1.35])
    assert evidence["measured_midpoint_xyz_m"] == [.14, .12, 1.]
    assert evidence["moves"][1]["actual_eef_xyz_m"] == evidence["final_eef_xyz_m"]
    assert evidence["private_truth_used"] is False


def test_observation_move_uses_actual_eef_and_does_not_translate_after_failed_raise():
    capture = MicrowaveEndpointCapture(observation_executor(reached=False), parent(), "open")
    evidence = capture.observation_pose(observation_sample())
    assert evidence["status"] == "not_reached"
    assert len(evidence["moves"]) == 1
    assert evidence["moves"][0]["receipt"]["waypoint_reached"] is True
    assert evidence["moves"][0]["waypoint_reached_by_proprioception"] is False
    assert evidence["final_eef_xyz_m"] == [0., 0., 1.]


@pytest.mark.parametrize("missing", ["plane", "stale", "overlap", "duplicate"])
def test_missing_or_nonindependent_public_planes_do_not_choose_observation_motion(missing):
    capture = MicrowaveEndpointCapture(observation_executor(), parent(), "open")
    measured = observation_sample()
    if missing == "plane":
        measured["frame"] = None
    elif missing == "stale":
        measured["source_step"] -= 1
    elif missing == "overlap":
        measured["frame_moving_mask_overlap"] = .051
    else:
        measured["moving"]["mask_id"] = measured["frame"]["mask_id"]
    evidence = capture.observation_pose(measured)
    assert evidence["status"] == "unmeasured" and evidence["moves"] == []


def test_observation_pose_private_labels_do_not_change_waypoints_or_repeated_height():
    capture = MicrowaveEndpointCapture(observation_executor(), parent(), "open")
    measured = observation_sample()
    first = capture.observation_pose(measured)
    measured.update(private_joint_qpos=100., solved=True)
    measured["frame"]["private_xyz"] = [99., 99., 99.]
    again = capture.observation_pose(measured)
    assert again["waypoints_xyz_m"][0][2] == first["waypoints_xyz_m"][0][2]
    assert again["measured_midpoint_xyz_m"] == first["measured_midpoint_xyz_m"]


def test_observation_pose_remeasures_two_fresh_frames_after_motion_without_reusing_planning_planes():
    ex = observation_executor()
    holds, frames = [], []
    ex.p._step_env = lambda action: holds.append(action.copy())
    capture = MicrowaveEndpointCapture(ex, parent(), "close", observation_pose_enabled=True)
    capture.withdraw = lambda: {"reason": "measured_clearance"}
    measured = [observation_sample(), sample(21, 1., 0.), sample(22, 1.3, 0.)]
    # Missing wrist remains missing in the newly measured frames.
    measured[1]["frame"] = measured[2]["frame"] = None

    def record(withdrawal):
        current = measured[len(frames)]
        frames.append({"sample": current, "actual_eef": ex.p._last_obs_eef_pos.copy()})
        return current

    capture.capture = record
    pair = capture.capture_pair()
    assert len(frames) == 3 and len(holds) == 6
    assert np.array_equal(frames[0]["actual_eef"], [0., 0., 1.])
    assert np.array_equal(frames[1]["actual_eef"], frames[2]["actual_eef"])
    assert pair[0]["source_step"] == 21 and pair[1]["source_step"] == 22
    assert pair[0]["frame"] is pair[1]["frame"] is None
    assert pair[0]["observation_pose"]["status"] == "reached"


def test_observation_pose_runtime_switch_defaults_off_and_can_be_set_by_registered_config():
    toolkit = SimpleNamespace(primitives=SimpleNamespace())
    assert V5Executor(toolkit, SimpleNamespace()).microwave_observation_pose_v1 is False
    assert V5Executor(toolkit, SimpleNamespace(), microwave_observation_pose_v1=True).microwave_observation_pose_v1 is True


def probe_frame(step, timestamp, angle):
    frame = sample(step, timestamp, angle)
    frame['frame']['mask_count'] = frame['moving']['mask_count'] = 1
    return frame


def test_readonly_nonendpoint_probe_does_not_interrupt_contact_controls():
    ex = executor_double(reached=True)
    capture = MicrowaveEndpointCapture(ex, parent(), 'close', stop_enabled=True, readonly_probe_enabled=True)
    capture.capture = lambda withdrawal: probe_frame(3, 1., 60.)
    capture.capture_pair = lambda: pytest.fail('nonendpoint must not release, move or hold')
    result = capture.observe(1)
    assert result['status'] == 'measured' and result['endpoint_candidate'] is False
    assert result['stop_admitted'] is False
    assert capture.records[0]['phase'] == 'probe' and capture.records[0]['intervening_controls'] == 0
    assert ex.p._last_obs_gripper == .04


def test_readonly_endpoint_requires_fresh_confirmed_pair_before_next_chunk():
    ex = executor_double(reached=True)
    capture = MicrowaveEndpointCapture(ex, parent(), 'close', stop_enabled=True, readonly_probe_enabled=True)
    capture.before = [probe_frame(1, 0., 60.), probe_frame(2, .3, 60.)]
    frame = probe_frame(3, 1., 0.)
    frame.update(arm_withdrawn=False, occluded=True)
    capture.capture = lambda withdrawal: frame
    confirmations = []
    def confirm():
        confirmations.append(True)
        return [probe_frame(4, 1.1, 0.), probe_frame(5, 1.4, 0.)]
    capture.capture_pair = confirm
    result = capture.observe(1)
    assert result['stop_admitted'] is True and confirmations == [True]
    assert capture.records[0]['measurement']['stop_admitted'] is False
    assert capture.records[1]['measurement']['stop_admitted'] is True


def test_readonly_endpoint_unknown_confirmation_cannot_stop():
    ex = executor_double(reached=True)
    capture = MicrowaveEndpointCapture(ex, parent(), 'close', stop_enabled=True, readonly_probe_enabled=True)
    capture.before = [probe_frame(1, 0., 60.), probe_frame(2, .3, 60.)]
    capture.capture = lambda withdrawal: probe_frame(3, 1., 0.)
    after = [probe_frame(4, 1.1, 0.), probe_frame(5, 1.4, 0.)]
    after[1]['occluded'] = None
    capture.capture_pair = lambda: after
    assert capture.observe(1)['stop_admitted'] is False


@pytest.mark.parametrize('missing', ['plane', 'duplicate', 'overlap', 'stale'])
def test_invalid_readonly_fit_does_not_trigger_recovery(missing):
    ex = executor_double(reached=True)
    capture = MicrowaveEndpointCapture(ex, parent(), 'close', readonly_probe_enabled=True)
    frame = probe_frame(3, 1., 0.)
    if missing == 'plane':
        frame['moving'] = None
    elif missing == 'duplicate':
        frame['moving']['mask_id'] = frame['frame']['mask_id']
    elif missing == 'overlap':
        frame['frame_moving_mask_overlap'] = .051
    else:
        frame['moving']['source_step'] = 2
    frame.update(solved=True, private_joint_qpos=0.)
    capture.capture = lambda withdrawal: frame
    capture.capture_pair = lambda: pytest.fail('unknown fit must not recover')
    assert capture.observe(1)['stop_admitted'] is False
    assert len(capture.records) == 1


def test_readonly_baseline_keeps_real_interval_without_release_or_reposition():
    ex = executor_double(reached=True)
    holds = []
    ex.p._step_env = lambda action: holds.append(action.copy())
    capture = MicrowaveEndpointCapture(ex, parent(), 'close', readonly_probe_enabled=True, observation_pose_enabled=True)
    capture.withdraw = lambda: pytest.fail('baseline must not release or move')
    capture.observation_pose = lambda sample: pytest.fail('baseline must not reposition')
    frames = iter([probe_frame(1, 0., 60.), probe_frame(2, .3, 60.)])
    capture.capture = lambda withdrawal: next(frames)
    capture.start()
    assert len(holds) == 6 and capture.records[0]['measurement']['status'] == 'measured'
    assert ex.p._last_obs_gripper == .04


def test_readonly_candidate_never_admits_stop_or_uses_private_labels():
    frame = probe_frame(3, 1., 0.)
    baseline = public_endpoint_candidate(frame, 'close')
    frame.update(solved=True, private_joint_qpos=1.57, private_endpoint=False)
    assert public_endpoint_candidate(frame, 'close') == baseline
    assert baseline['endpoint_candidate'] is True and baseline['stop_admitted'] is False


def test_readonly_probe_config_defaults_off_and_factory_receives_registered_switch(monkeypatch):
    import robots.libero.v5_microwave_capture as capture_module
    toolkit = SimpleNamespace(primitives=SimpleNamespace())
    assert V5Executor(toolkit, SimpleNamespace()).microwave_readonly_probe_v1 is False
    visited = []
    class Collector:
        def __init__(self, *args, **kwargs):
            visited.append(kwargs)
            self.records = []
        def start(self):
            pass
        def observe(self, chunks):
            return {'stop_admitted': False}
    monkeypatch.setattr(capture_module, 'MicrowaveEndpointCapture', Collector)
    enabled = V5Executor(toolkit, SimpleNamespace(), microwave_temporal_stop_v1=True, microwave_readonly_probe_v1=True)
    assert enabled.microwave_temporal_public_stop(parent(), 'close') is not None
    assert visited[0]['readonly_probe_enabled'] is True


def staged_row(step, controls, angle=0.):
    frame = probe_frame(step, 1000. * step, angle)
    return {'frame': frame, 'candidate': public_endpoint_candidate(frame, 'close'),
            'executed_controls': controls}


def test_staged_withdrawal_waits_for_real_contact_interval_and_never_admits_stop():
    # Job4516 withdrew at its only measured near-endpoint frame, block36.
    rows = [staged_row(38, 180, 14.896118489119132)]
    assert stable_public_endpoint_candidates(rows)['reason'] == 'waiting_more_public_candidates'
    rows.append(staged_row(39, 185, 14.5))
    measured = stable_public_endpoint_candidates(rows)
    assert measured['actual_contact_interval_s'] == .25
    assert measured['withdrawal_admitted'] is False  # Long SAM wall time adds no contact controls.
    rows.append(staged_row(40, 190, 14.))
    measured = stable_public_endpoint_candidates(rows)
    assert measured['actual_contact_interval_s'] == .5
    assert measured['withdrawal_admitted'] is True
    assert measured['stop_admitted'] is False


@pytest.mark.parametrize('counts', [(5, 5), (None, 10), (True, 10), (10, 5)])
def test_staged_withdrawal_needs_distinct_measured_executed_controls(counts):
    rows = [staged_row(3 + i, count) for i, count in enumerate(counts)]
    measured = stable_public_endpoint_candidates(rows)
    assert measured['reason'] == 'distinct_executed_contact_controls_not_measured'
    assert measured['withdrawal_admitted'] is measured['stop_admitted'] is False


@pytest.mark.parametrize('changed,reason', [
    ('step', 'candidate_captures_not_distinct'),
    ('fixed_angle', 'independent_fixed_frame_not_stable'),
    ('fixed_drift', 'independent_fixed_frame_not_stable'),
    ('door_angle', 'endpoint_candidate_still_moving'),
    ('door_centre', 'endpoint_candidate_still_moving'),
])
def test_staged_withdrawal_rejects_moving_or_unstable_public_planes(changed, reason):
    rows = [staged_row(3, 5), staged_row(4, 15)]
    if changed == 'step':
        rows[1]['frame']['source_step'] = 3
    elif changed == 'fixed_angle':
        rows[1]['candidate']['measured_planes']['frame']['normal_xy'] = [0., 1.]
    elif changed == 'fixed_drift':
        rows[1]['candidate']['measured_planes']['frame']['centre'][0] += .011
    elif changed == 'door_angle':
        rows[1]['candidate']['relative_angle_deg'] = 3.1
    else:
        rows[1]['candidate']['measured_planes']['moving']['centre'][2] += .011
    measured = stable_public_endpoint_candidates(rows)
    assert measured['reason'] == reason
    assert measured['withdrawal_admitted'] is measured['stop_admitted'] is False


def staged_capture():
    ex = executor_double(reached=True)
    ex.motion_evidence = []
    capture = MicrowaveEndpointCapture(ex, parent(), 'close', stop_enabled=True,
                                      readonly_probe_enabled=True, staged_candidate_enabled=True)
    capture.before = [probe_frame(1, 0., 60.), probe_frame(2, .3, 60.)]
    return capture


def test_staged_capture_waits_across_actual_vla_blocks_before_fresh_confirmation():
    capture = staged_capture()
    frames = iter(probe_frame(step, step * 1000., 0.) for step in (3, 4, 5))
    capture.capture = lambda withdrawal: next(frames)
    confirmations = []
    def confirm():
        confirmations.append(True)
        return [probe_frame(6, 1., 0.), probe_frame(7, 1.3, 0.)]
    capture.capture_pair = confirm
    for block in (1, 2):
        capture.executor.motion_evidence.append({'name': 'vla_act_chunk', 'executed_action_count': 5})
        assert capture.observe(block)['stop_admitted'] is False
        assert confirmations == []
    capture.executor.motion_evidence.append({'name': 'vla_act_chunk', 'executed_action_count': 5})
    assert capture.observe(3)['stop_admitted'] is True
    assert confirmations == [True]
    assert capture.records[-2]['measurement']['staged_confirmation']['withdrawal_admitted'] is True
    assert capture.records[-1]['phase'] == 'after'


def test_staged_capture_clears_candidate_sequence_on_current_missing_plane():
    capture = staged_capture()
    frames = [probe_frame(3, 1., 0.), probe_frame(4, 2., 0.), probe_frame(5, 3., 0.)]
    frames[1]['moving'] = None
    observed = iter(frames)
    capture.capture = lambda withdrawal: next(observed)
    capture.capture_pair = lambda: pytest.fail('missing plane breaks the stable candidate sequence')
    for block in (1, 2, 3):
        capture.executor.motion_evidence.append({'name': 'vla_act_chunk', 'executed_action_count': 10})
        assert capture.observe(block)['stop_admitted'] is False
    assert len(capture.candidate_history) == 1


def test_staged_capture_does_not_use_requested_blocks_or_private_truth_as_executed_controls():
    capture = staged_capture()
    frames = iter(probe_frame(step, step * 1000., 0.) for step in (3, 4, 5))
    capture.capture = lambda withdrawal: next(frames)
    capture.capture_pair = lambda: pytest.fail('no measured executed contact controls')
    capture.executor.motion_evidence = [{'name': 'vla_act_chunk', 'requested_action_count': 100,
                                       'solved': True, 'private_joint_qpos': 0.}]
    for block in (1, 2, 3):
        assert capture.observe(block)['stop_admitted'] is False
    assert capture.records[-1]['measurement']['staged_confirmation']['reason'] == 'distinct_executed_contact_controls_not_measured'


def test_staged_switch_defaults_off():
    toolkit = SimpleNamespace(primitives=SimpleNamespace())
    assert V5Executor(toolkit, SimpleNamespace()).microwave_staged_candidate_v1 is False
    assert V5Executor(toolkit, SimpleNamespace(), microwave_staged_candidate_v1=True).microwave_staged_candidate_v1 is True


@pytest.mark.parametrize("controls,endpoint,bad_reason", [
    (6, True, None), (5, True, "waiting_actual_contact_interval"),
    (6, False, "current_hold_endpoint_not_measured"),
    (None, True, "distinct_executed_contact_controls_not_measured"),
])
def test_candidate_hold_confirms_with_real_controls_before_another_contact_block(
    controls, endpoint, bad_reason,
):
    capture = staged_capture()
    capture.candidate_hold_enabled = True
    capture.executor.motion_evidence = [{'name': 'vla_act_chunk', 'executed_action_count': 5}]
    capture.capture = lambda withdrawal: probe_frame(3, .4, 0.)
    calls = []

    def confirm(*, withdraw_before=True):
        calls.append(withdraw_before)
        pair = ([probe_frame(4, .5, 0.), probe_frame(5, .8, 0. if endpoint else 60.)]
                if not withdraw_before else [probe_frame(6, 1., 0.), probe_frame(7, 1.3, 0.)])
        pair[-1]['interval_controls'] = controls
        return pair

    capture.capture_pair = confirm
    result = capture.observe(1)
    assert result['stop_admitted'] is (bad_reason is None)
    assert calls == ([False, True] if bad_reason is None else [False])
    record = next(row for row in capture.records if row['phase'] == 'candidate_hold')
    assert record['intervening_controls'] == controls
    if bad_reason is not None:
        assert record['measurement']['reason'] == bad_reason
    assert len(capture.executor.motion_evidence) == 1


def test_candidate_hold_defaults_off():
    toolkit = SimpleNamespace(primitives=None)
    assert V5Executor(toolkit, SimpleNamespace()).microwave_candidate_hold_v2 is False
    assert V5Executor(toolkit, SimpleNamespace(), microwave_candidate_hold_v2=True).microwave_candidate_hold_v2


def test_identity_tracking_switch_defaults_off_and_is_explicitly_wired():
    toolkit = SimpleNamespace(primitives=SimpleNamespace())
    assert V5Executor(toolkit, SimpleNamespace()).microwave_identity_tracking_v1 is False
    enabled = V5Executor(toolkit, SimpleNamespace(), microwave_identity_tracking_v1=True)
    assert enabled.microwave_identity_tracking_v1 is True


def test_identity_tracking_does_not_bridge_a_missing_current_fixed_frame(tmp_path):
    """A stale previous door identity cannot fill a frame without current support."""
    import robots.libero.v5_microwave_capture as capture_module

    state = State(tmp_path)
    ex = SimpleNamespace(
        toolkit=SimpleNamespace(_state=state),
        p=SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.])),
    )
    capture = MicrowaveEndpointCapture(ex, parent(), "close", identity_tracking_enabled=True)
    previous_mask = np.ones((5, 5), dtype=bool)
    capture._identity_history["agentview"] = {
        "rgb": np.zeros((5, 5, 3), dtype=np.uint8),
        "world": np.zeros((5, 5, 3), dtype=np.float32),
        "moving_mask": previous_mask,
        "frame": {"centre": [0., 0., 1.], "normal_xy": [1., 0.]},
        "anchor": {"lower": [-.1, -.1, .9], "upper": [.1, .1, 1.1], "source_step": 1},
        "source_step": 1,
    }
    views = {"agentview": {"frame": None, "moving": None}}
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(capture_module, "_public_rgbd", lambda *_: (
        np.zeros((5, 5, 3), dtype=np.uint8), np.zeros((5, 5, 3), dtype=np.float32)))
    try:
        capture._track_missing_views(views, {"agentview": {}})
    finally:
        monkeypatch.undo()
    assert views["agentview"]["moving"] is None
    assert views["agentview"]["identity_tracking"]["reason"] == "current_fixed_frame_not_measured"
    assert views["agentview"]["identity_tracking"]["stop_admitted"] is False


def test_job4577_lost_identity_is_not_labelled_independent(tmp_path):
    ex = SimpleNamespace(toolkit=SimpleNamespace(_state=State(tmp_path)))
    capture = MicrowaveEndpointCapture(ex, parent(), "close", identity_tracking_enabled=True)
    views = {"agentview": {"frame": {"source_step": 37}, "moving": None}}
    capture._track_missing_views(views, {})
    assert views["agentview"]["moving"] is None
    assert views["agentview"]["identity_tracking"]["reason"] == "previous_independent_door_identity_missing"
    assert views["agentview"]["identity_tracking"]["stop_admitted"] is False
    capture._update_identity_history(views, {})
    assert capture._identity_history["agentview"] is None


def test_identity_tracking_uses_current_rgbd_only_for_one_step_continuation(monkeypatch, tmp_path):
    from robots.libero import v5_microwave_identity

    state = State(tmp_path)
    ex = SimpleNamespace(toolkit=SimpleNamespace(_state=state))
    capture = MicrowaveEndpointCapture(ex, parent(), "close", identity_tracking_enabled=True)
    prior_mask = np.ones((5, 5), dtype=bool)
    prior_frame = {"centre": [0., 0., 1.], "normal_xy": [1., 0.], "source_step": 1}
    capture._identity_history["agentview"] = {
        "rgb": np.zeros((5, 5, 3), dtype=np.uint8),
        "world": np.zeros((5, 5, 3), dtype=np.float32),
        "moving_mask": prior_mask, "frame": prior_frame,
        "anchor": {"lower": [-.1, -.1, .9], "upper": [.1, .1, 1.1], "source_step": 1},
        "source_step": 1,
    }
    views = {"agentview": {"frame": {"centre": [0., 0., 1.], "normal_xy": [1., 0.],
                                        "source_step": 2}, "moving": None}}
    monkeypatch.setattr(capture_module := __import__(
        "robots.libero.v5_microwave_capture", fromlist=["_public_rgbd"]),
        "_public_rgbd", lambda *_: (np.zeros((5, 5, 3), dtype=np.uint8),
                                     np.zeros((5, 5, 3), dtype=np.float32)))
    monkeypatch.setattr(v5_microwave_identity, "track_measured_door",
                        lambda *args, **kwargs: (np.ones((5, 5), dtype=bool),
                                                  {"centre": [0., 0., 1.], "normal_xy": [1., 0.],
                                                   "residual_p90_m": .001, "points": 100},
                                                  {"reason": "current_depth_plane_with_tracked_door_identity"}))
    monkeypatch.setattr(capture, "_persist_tracked_moving",
                        lambda *args: {"source_step": 2, "mask_count": 1})
    capture._track_missing_views(views, {"agentview": {}})
    assert views["agentview"]["moving"]["source_step"] == 2
    assert views["agentview"]["identity_tracking"]["private_labels_used"] is False
