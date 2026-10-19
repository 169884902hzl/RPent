"""Identity must come from current RGB-D correspondence, never a front hint."""

import numpy as np
import pytest

from robots.libero.v5_microwave_identity import match_current_door_across_views, track_measured_door


@pytest.mark.parametrize('case', ['unique', 'missing', 'remote', 'competing'])
def test_current_handle_can_resolve_conflicting_views_only_with_unique_support(case):
    from robots.libero.v5_microwave_identity import resolve_door_views_from_current_handle

    x, z = np.mgrid[-.12:.12:25j, 1.:1.2:25j]
    door = np.stack((x.ravel(), np.zeros(x.size), z.ravel()), axis=-1)
    control = door + [0., -.13, 0.]
    handle = np.array([(px, .03, pz) for px in np.linspace(.01, .02, 10)
                       for pz in np.linspace(1.08, 1.1, 10)])
    handles = [] if case == 'missing' else [handle + ([0., .5, 0.] if case == 'remote' else 0.)]
    if case == 'competing':
        control = door.copy()
    selected, evidence = resolve_door_views_from_current_handle(
        {'agentview': door, 'wrist': control}, handles)
    assert selected == ('agentview' if case == 'unique' else None)
    assert evidence['stop_admitted'] is False
    if case == 'unique':
        assert evidence['views']['agentview']['supported'] is True
        assert evidence['views']['wrist']['supported'] is False


@pytest.mark.parametrize('provenance', ['current', 'stale', 'changed', 'private'])
def test_scene_conflicting_panels_require_current_hash_pinned_public_handle(tmp_path, monkeypatch, provenance):
    import hashlib
    from types import SimpleNamespace

    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity
    from rpent.robots.components.sam3_client import Sam3Client

    x, z = np.mgrid[-.12:.12:25j, 1.:1.2:25j]
    door = np.stack((x, np.zeros(x.shape), z), axis=-1)
    frames = {'agentview': door, 'wrist': door + [0., -.13, 0.]}
    state = SimpleNamespace(latest_step=3, load_bytes=lambda _: b'RGB',
        load=lambda name: ({'extrinsic_cam2world': np.eye(4)} if name.endswith('.json')
                           else frames[name.removesuffix('_world_high.npz')]),
        artifact_path=lambda name, step: tmp_path / name)

    def save(name, value, *, step):
        np.savez_compressed(tmp_path / name, value)
        return tmp_path / name

    state.save = save
    rpc = SimpleNamespace(call=lambda *args, **kwargs: {'instances': [{'score': .9}]})
    monkeypatch.setattr(Sam3Client, '_decode_result', staticmethod(
        lambda _: SimpleNamespace(mask=np.ones(x.shape, bool))))
    scene = MeasuredScene(SimpleNamespace(_state=state), rpc, 0, dual_view_fusion_v1=True)
    parent = Entity('e1', 'microwave', (0., -.06, 1.1), (-.2, -.2, 1.), (.2, .05, 1.2), source_step=3)
    scene.entities[parent.id] = parent
    scene.fixture_measurement_evidence[parent.id] = {}
    scene._microwave_door_history[(parent.id, 'wrist')] = {'source_step': 2}
    handle = np.array([(px, .03, pz) for px in np.linspace(.01, .02, 10)
                       for pz in np.linspace(1.08, 1.1, 10)])
    path = save('handle.npz', handle, step=3)
    ref = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
           'source': 'private' if provenance == 'private' else 'perception',
           'source_step': 2 if provenance == 'stale' else 3}
    if provenance == 'changed':
        ref['sha256'] = 'changed'
    monkeypatch.setattr(scene, 'measure_fixture_handle_pose',
        lambda _: {'views': {'agentview': {'cloud': ref}}})
    clouds, views = {}, {}
    measured = scene._measure_microwave_door(parent, 'agentview', measured_clouds=clouds, measured_views=views)
    evidence = scene.fixture_measurement_evidence[parent.id]['door_measurement']
    assert bool(measured) is (provenance == 'current')
    assert evidence['current_handle_association']['stop_admitted'] is False
    if measured:
        assert evidence['source_cameras'] == ['agentview']
        assert set(views) == {'agentview'}
        assert np.allclose(clouds['microwave door'][:, 1], 0.)
        assert (parent.id, 'wrist') not in scene._microwave_door_history
    else:
        assert evidence['reason'] == 'door_views_not_one_adjacent_plane'


def translated_public_panel():
    import cv2
    rng = np.random.default_rng(7)
    image = np.zeros((160, 200, 3), np.uint8)
    image[20:140, 30:150] = rng.integers(0, 256, (120, 120, 3), dtype=np.uint8)
    moved = cv2.warpAffine(image, np.float32([[1, 0, 5], [0, 1, 0]]), (200, 160))
    mask = np.zeros((160, 200), bool)
    mask[25:135, 35:145] = True
    rows, columns = np.mgrid[:160, :200]
    world = np.stack((columns * .002, np.full_like(rows, .25, dtype=float), 1 + rows * .002), axis=-1)
    anchor = {"lower": [.5, .24, .9], "upper": [.6, .26, 1.4], "source_step": 0}
    return image, moved, world.astype(np.float16), world.astype(np.float16), mask, anchor


def test_float16_public_depth_tracks_a_translated_independent_panel():
    mask, plane, evidence = track_measured_door(*translated_public_panel())
    assert plane is not None
    assert mask.sum() >= 60
    assert evidence["rigid_fraction"] >= .55
    assert evidence["plane_support_fraction_of_rigid_tracks"] >= .55
    assert evidence["private_labels_used"] is False
    assert evidence["stop_admitted"] is False


@pytest.mark.parametrize("missing", ["initial_identity", "visual_texture", "depth", "robot_occlusion"])
def test_lost_public_support_cannot_be_replaced_with_an_appliance_plane(missing):
    image, moved, previous, current, mask, anchor = translated_public_panel()
    robot = None
    if missing == "initial_identity":
        mask[:] = False
    elif missing == "visual_texture":
        image[:] = moved[:] = 0
    elif missing == "depth":
        current[:] = 0
    else:
        robot = np.ones(mask.shape, bool)
    mask, plane, evidence = track_measured_door(image, moved, previous, current, mask, anchor, robot_mask=robot)
    assert plane is None
    assert not mask.any()
    assert evidence["stop_admitted"] is False


def test_second_view_requires_current_matching_depth_not_copied_primary_plane():
    _, _, first, second, mask, anchor = translated_public_panel()
    matched, face, evidence = match_current_door_across_views(first, mask, second, anchor)
    assert face is not None and matched.sum() >= 60
    assert evidence["private_labels_used"] is False
    assert evidence["stop_admitted"] is False
    second[..., 1] += .03
    matched, face, evidence = match_current_door_across_views(first, mask, second, anchor)
    assert face is None and not matched.any()
    assert evidence["reason"] == "second_view_current_door_support_not_measured"


def test_warped_mask_does_not_mix_newly_revealed_background_into_door_plane():
    image, moved, previous, current, mask, _ = translated_public_panel()
    current = current.copy()
    current[:, 110:151, 1] += .05
    tracked, face, evidence = track_measured_door(image, moved, previous, current, mask, None)
    assert face is not None
    assert tracked.sum() >= 60
    assert np.all(np.abs(current[tracked, 1] - .25) < .008)
    support = evidence['tracked_plane_depth_support']
    assert support['retained_pixels'] < support['mapped_pixels']
    assert evidence['stop_admitted'] is False


def test_scene_missing_segmentation_uses_current_tracked_depth_and_clears_lost_identity(monkeypatch, tmp_path):
    import sys
    from types import SimpleNamespace

    from robots.libero import bounded_self_filter
    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity
    from rpent.robots.components.sam3_client import Sam3Client

    image, moved, previous, current, mask, _ = translated_public_panel()
    frames = {'agentview': (image, previous)}
    state = SimpleNamespace(latest_step=0, load_bytes=lambda _: b'RGB',
        load=lambda name: {'extrinsic_cam2world': np.eye(4)} if name.endswith('.json') else frames['agentview'][1],
        artifact_path=lambda name, step: tmp_path/name)

    def save(name, value, step):
        np.savez_compressed(tmp_path/name, value)
        return tmp_path/name

    state.save = save
    replies = [{'instances': [{'score': .9}]}, {'instances': []}, {'instances': []}, {'instances': []}]
    rpc = SimpleNamespace(call=lambda *args, **kwargs: replies.pop(0))
    toolkit = SimpleNamespace(_state=state, primitives=SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: {
        'robot0_eef_pos': [0, 0, 1], 'robot0_eef_quat': [0, 0, 0, 1],
        'robot0_gripper_qpos': [.04, .04], 'robot0_joint_pos': [0]*7})))
    monkeypatch.setitem(sys.modules, 'robosuite', SimpleNamespace(__file__=str(tmp_path/'__init__.py')))
    monkeypatch.setattr(bounded_self_filter, 'public_robot_mask', lambda world, robot, xml: np.zeros(mask.shape, bool))
    monkeypatch.setattr(Sam3Client, '_decode_result', staticmethod(lambda _: SimpleNamespace(mask=mask)))
    from robots.libero import v5_microwave_capture
    monkeypatch.setattr(v5_microwave_capture, '_public_rgbd', lambda state, view: frames[view])
    scene = MeasuredScene(toolkit, rpc, 0, dual_view_fusion_v1=False, microwave_door_tracking_v1=True)
    parent = Entity('e1', 'microwave', (.2, .25, 1.16), (0., .2, .9), (.4, .3, 1.4))
    scene.fixture_measurement_evidence[parent.id] = {}
    assert scene._measure_microwave_door(parent, 'agentview')
    state.latest_step = 1
    frames['agentview'] = moved, current
    clouds = {}
    assert scene._measure_microwave_door(parent, 'agentview', measured_clouds=clouds)
    assert len(clouds['microwave door']) >= 60
    evidence = scene.fixture_measurement_evidence[parent.id]['door_measurement']
    tracking = next(item['identity_tracking'] for item in evidence['instances'] if 'identity_tracking' in item)
    assert tracking['reason'] == 'current_depth_plane_with_tracked_door_identity'
    assert tracking['private_labels_used'] is False
    assert tracking['source_step'] == 1 and tracking['previous_source_step'] == 0
    # Losing visual support clears the history; a later textured image cannot
    # bridge that missing capture with a cached plane advertised as current.
    state.latest_step = 2
    frames['agentview'] = np.zeros_like(image), current
    assert not scene._measure_microwave_door(parent, 'agentview')
    state.latest_step = 3
    frames['agentview'] = moved, current
    assert not scene._measure_microwave_door(parent, 'agentview')
    assert not scene._microwave_door_history
