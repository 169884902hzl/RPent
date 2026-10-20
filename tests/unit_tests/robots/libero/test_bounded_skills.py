# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Public-only skill request and exact-ID execution checks."""
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.v5_state import Entity
from rpent.skill_package.contract import selected, validate
from tests.unit_tests.robots.libero.test_bounded_motion import FakePrimitives


@pytest.fixture
def adapter(monkeypatch):
    p = FakePrimitives()
    p.env.execution_budget = lambda: {"remaining_sim_steps": 10000-len(p.actions), "used_sim_steps": len(p.actions)}
    entity = Entity("e1", "box", (.1, .1, .9), (.08, .08, .88), (.12, .12, .92), True, 0)
    scene = SimpleNamespace(entities={"e1": entity}, vocabulary={"box"}, refresh=lambda names: None,
        _scores={"e1": .9}, dual_view_fusion_v1=True, view_axes=((1, 0, 0), (0, -1, 0)), measurement_clouds={})
    geometry = {"boxes": [], "max_opening_m": .08}
    monkeypatch.setattr("robots.libero.bounded_skills.panda_geometry", lambda xml: geometry)
    ex = SimpleNamespace(p=p, scene=scene, instruction="put the box on the plate", capture=lambda: None, held=None)
    ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=0,
        load=lambda _: np.empty((0, 0, 3))))
    def capture():
        ex.toolkit._state.latest_step += 1
    ex.capture = capture
    result = MeasuredSkillAdapter(ex, "/static/grippers/panda_gripper.xml", allow_vla=False)
    result.grasp_geometry = lambda e: {"xyz_m": [.1, .1, .9], "quat_xyzw": [0, 0, 0, 1], "width_m": .04}
    def screen(poses):
        return {
            "passed": True, "reason": "test_public_geometry", "collision": False, "ik_reachable": True,
            "path_min_clearance_m": .05, "screen_scope": "test_measured_mesh"}
    screen.points = screen.target = np.empty((0, 3))
    def cloud_screen(*args, **kwargs):
        if result._base_geometry is None:
            result._base_geometry = (screen.points, None)
        return screen
    result._cloud_and_ik = cloud_screen
    return result


def decision(request, ids):
    return {"schema_version": request["schema_version"], "kind": "decision", "revision": request["revision"],
            "observation_id": request["observation_id"], "candidate_ids": ids}


def test_public_push_fallback_has_measured_source_and_region_without_goal_filter(adapter):
    from jsonschema import ValidationError

    from robots.libero.v5_subtasks import subtask_phrase

    adapter.allow_vla = True
    adapter.scene.entities['dest'] = Entity('dest', 'area front of plate', (.2, .1, .9),
        (.16, .06, .9), (.24, .14, .9))
    adapter.ex.instruction = 'observe the box'
    request = adapter.request()
    push = next(c for c in request['candidates'] if c['skill'] == 'call_vla'
        and c['parameters']['mode'] == 'push')
    assert push['parameters'] == {'anchor_id': 'e1', 'target_id': 'dest', 'mode': 'push'}
    assert subtask_phrase('plate', 'push', 'area front of stove') == 'push the plate to the front of the stove'
    validate(request)
    del push['parameters']['target_id']
    with pytest.raises(ValidationError):
        validate(request)


def test_push_endpoint_requires_fresh_stable_planar_motion_in_public_region():
    from dataclasses import replace

    from robots.libero.v5_verification import measured_push_endpoint

    initial = Entity('e1', 'plate', (0., 0., .9), (-.06, -.06, .89), (.06, .06, .91))
    previous = replace(initial, xyz=(.2, 0., .9), source_step=1)
    current = replace(previous, xyz=(.205, 0., .9), source_step=2)
    target = Entity('dest', 'area front of stove', (.2, 0., .89), (.16, -.04, .89), (.24, .04, .89))
    assert measured_push_endpoint(initial, previous, current, target)[0] is True
    assert measured_push_endpoint(initial, current, current, target)[0] is False
    assert measured_push_endpoint(initial, previous, replace(current, visible=False), target)[0] is False
    assert measured_push_endpoint(initial, previous, replace(current, xyz=(.3, 0., .9)), target)[0] is False
    assert measured_push_endpoint(initial, previous, replace(current,
        lower=(-.06, -.06, .94), upper=(.06, .06, .96)), target)[0] is False


def test_targeted_vla_categories_use_public_parents_and_relative_region_support(adapter):
    from dataclasses import replace

    parent = Entity('cab', 'cabinet', (0., 0., .9), (-.1, -.1, .8), (.1, .1, 1.))
    drawer = replace(parent, id='drawer', name='cabinet top drawer', part_of='cab')
    area = replace(parent, id='area', name='area front of stove')
    adapter.scene.entities.update(cab=parent, drawer=drawer, area=area)
    assert adapter._vla_measurement_names(drawer, None) == ['cabinet']
    assert adapter._vla_measurement_names(adapter.scene.entities['e1'], area) == ['box', 'stove', 'table']


def test_targeted_refresh_preserves_the_full_scene_vocabulary(adapter):
    received = []
    adapter.scene.vocabulary.update(('plate', 'table'))
    adapter.scene.refresh = lambda names, **kwargs: received.append(names)
    adapter.refresh(names=['box'])
    adapter.refresh()
    assert received == [['box'], ['box', 'plate', 'table']]
    assert adapter.scene.vocabulary == {'box', 'plate', 'table'}


def test_targeted_vla_still_checks_each_control_and_fully_remeasures_after_handoff(adapter, monkeypatch):
    adapter.allow_vla = True
    adapter.targeted_vla_measurement_v1 = True
    received = []
    adapter.refresh = lambda **kwargs: received.append(kwargs.get('names'))
    def fallback(**kwargs):
        assert kwargs['budget'].controls_per_check == 1
        kwargs['observe']()
        kwargs['observe']()
        return {'outcome': 'failure', 'stop_reason': 'control_budget'}
    monkeypatch.setattr('robots.libero.bounded_skills.run_fallback', fallback)
    result = adapter.call_vla({'anchor_id': 'e1', 'mode': 'pick'})
    assert received == [['box'], ['box'], None]
    assert result['public_measurement_scope']['version'] == 'selected-subtask-entities/1'


def test_measured_anchor_still_has_screened_approaches_without_a_contact_fit(adapter):
    adapter.grasp_geometry = lambda entity: None
    request = adapter.request(k=4)
    approaches = [c for c in request['candidates'] if c['skill'] == 'move_to']
    assert len(approaches) == 12
    assert not any(c['skill'] in {'align', 'descend', 'lift'} for c in request['candidates'])
    assert not adapter.plans
    for candidate in approaches:
        assert candidate['consequences']['screen_scope'] == 'hand_mesh_observed_space'
        assert candidate['consequences']['expected_width_m'] is None
        route = adapter._route('move_to', candidate['parameters'])
        assert route[-1]['quat_xyzw'] == request['robot']['eef_quat_xyzw']
        endpoint = np.asarray(route[-1]['xyz_m'])
        lower = np.asarray(adapter.scene.entities['e1'].lower)
        upper = np.asarray(adapter.scene.entities['e1'].upper)
        assert np.linalg.norm(np.maximum(0., np.maximum(lower-endpoint, endpoint-upper))) >= .12-1e-9
        adapter._commit_grasp(candidate)
    assert not adapter.committed_grasps
    validate(request)


def test_private_recovery_approaches_an_ungraspable_source_once_before_measuring(adapter):
    from robots.libero.bounded_oracle import BoundedOracle

    adapter.grasp_geometry = lambda entity: None
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.3, .1, .9),
        (.25, .05, .89), (.35, .15, .91), True, 0)
    status = {'done': False, 'goals': [['on', 'box_1', 'plate_1']], 'satisfied': [False]}
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: status), adapter)
    request = adapter.request(k=4)
    decision = oracle.choose(request)
    assert len(decision['candidate_ids']) == 1
    chosen = next(c for c in request['candidates'] if c['id'] == decision['candidate_ids'][0])
    assert chosen['skill'] == 'move_to' and chosen['parameters']['anchor_id'] == 'e1'
    assert oracle.last_labels['positions'][0]['rule_acceptable']
    # Prior recovery views are not additional progress labels. No controls
    # are needed to check that the private selector advances to another view.
    adapter.receipts.append({'candidate_id': chosen['id']})
    acceptable = oracle._acceptable(request, status)
    assert chosen['id'] not in acceptable
    assert oracle._choose_one(request, status)['id'] != chosen['id']


def test_same_capture_self_filter_reuses_only_identical_inputs(adapter, monkeypatch):
    import scipy.spatial
    from scipy.spatial import cKDTree

    builds = []
    def tree(points):
        builds.append(True)
        return cKDTree(points)
    monkeypatch.setattr(scipy.spatial, 'cKDTree', tree)
    world = np.array([[[.1, .2, .3], [.4, .5, .6]]])
    adapter._base_geometry = (world.reshape(-1, 3)[:1].copy(), None)
    first = adapter._self_filtered_world(world)
    assert np.array_equal(first[0, 0], world[0, 0])
    assert np.isnan(first[0, 1]).all()
    first[:] = 0.  # A consumer must not mutate later cached results.
    assert np.array_equal(adapter._self_filtered_world(world.copy())[0, 0], world[0, 0])
    assert len(builds) == 1

    changed = world.copy()
    changed[0, 0, 0] += .001
    assert np.isnan(adapter._self_filtered_world(changed)).all()
    assert len(builds) == 2
    adapter.ex.toolkit._state.latest_step += 1
    adapter._self_filtered_world(world)
    assert len(builds) == 3
    adapter._base_geometry = (world.reshape(-1, 3)[1:].copy(), None)
    latest = adapter._self_filtered_world(world)
    assert np.isnan(latest[0, 0]).all()
    assert np.array_equal(latest[0, 1], world[0, 1])
    assert len(builds) == 4


@pytest.mark.parametrize('mode', ['refresh', 'blocked_scan', 'withdrawal'])
def test_observation_keeps_contact_until_the_hand_actually_withdraws(adapter, monkeypatch, mode):
    original_obs = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original_obs(), 'robot0_gripper_qpos': [.02, -.02]}
    adapter.p.env.position[:] = [.1, .1, .9]
    initial = adapter.request()
    descend = next(c for c in initial['candidates'] if c['skill'] == 'descend')
    adapter._commit_grasp(descend)
    adapter.active = 'e1'
    adapter.grasp_reference = (adapter.scene.entities['e1'], adapter.robot())
    committed = adapter.committed_grasps['e1']
    # Jaw occlusion prevents finding a new patch. The existing measured
    # contact still exposes lift; a refresh alone must not destroy it.
    adapter.grasp_geometry = lambda entity: None
    if mode == 'blocked_scan':
        monkeypatch.setattr('robots.libero.bounded_skills.SmoothMotion.run',
            lambda *args, **kwargs: dict(executed=False, stop_reason='measured_sweep_collision'))
    request = adapter.request()
    assert any(c['skill'] == 'lift' for c in request['candidates'])
    observe = next(c for c in request['candidates'] if c['skill'] == 'observe'
        and c['parameters']['mode'] == ('refresh' if mode == 'refresh' else 'wrist_scan'))
    receipt = adapter.execute(request, decision(request, [observe['id']]))[0]
    if mode == 'withdrawal':
        assert receipt['steps_used'] > 0
        assert adapter.active is adapter.grasp_reference is None
        assert not adapter.committed_grasps
    else:
        assert receipt['steps_used'] == 0
        assert adapter.active == 'e1' and adapter.grasp_reference is not None
        assert adapter.committed_grasps['e1'] is committed
        assert any(c['skill'] == 'lift' for c in adapter.request()['candidates'])


def test_precontact_instance_reference_preserves_exact_public_pixels(adapter):
    points = np.random.default_rng(18).uniform([.08, .08, .88], [.12, .12, .92], (80, 3))
    adapter.precontact_instance_surface_v1 = True
    adapter.plans['e1'] = {'xyz_m': [.1, .1, .9]}
    adapter._instance_pixels = lambda key: points
    neighbour = np.array([[.15, .1, .9]])
    adapter._base_geometry = (np.concatenate([points, neighbour]), None)
    adapter._commit_grasp({'skill': 'move_to', 'parameters': {'anchor_id': 'e1'}})
    saved = adapter.committed_grasps['e1']['instance_reference']
    np.testing.assert_array_equal(saved['xyz_world'], points)
    assert not np.shares_memory(saved['xyz_world'], points)
    assert saved['source_step'] == 0
    np.testing.assert_allclose(saved['stationary_scene'], neighbour)


def test_current_support_plane_cannot_become_contact_payload(adapter, monkeypatch):
    from robots.libero.v5_perception_geometry import measured_work_surface

    y, x = np.mgrid[:80, :80]
    world = np.stack([-.1+x*.005, -.1+y*.005, np.full(x.shape, .88)], axis=-1)
    adapter.ex.toolkit._state.load = lambda _: world
    calls = []
    def measure(*args):
        calls.append(True)
        return measured_work_surface(*args)
    monkeypatch.setattr('robots.libero.v5_perception_geometry.measured_work_surface', measure)
    support = world[20:25, 20:25].reshape(-1, 3)
    object_pixels = np.array([[.1, .1, .90], [.1, .12, .91]])
    pixels = np.concatenate([support, object_pixels])
    original = world.copy()
    result, evidence = adapter._exclude_measured_support(pixels)
    np.testing.assert_array_equal(result, object_pixels)
    assert evidence['retained_as_obstacles'] == len(support)
    assert evidence['private_pose_used'] is False
    assert evidence['measurement']['source_step'] == 0
    # Instance subtraction never removes the support from the source scene.
    np.testing.assert_array_equal(world, original)
    adapter._exclude_measured_support(pixels)
    assert len(calls) == 1
    world[:, :, 2] += .005
    adapter.ex.toolkit._state.latest_step += 1
    result, evidence = adapter._exclude_measured_support(pixels+[0., 0., .005])
    np.testing.assert_allclose(result, object_pixels+[0., 0., .005])
    assert len(calls) == 2
    assert evidence['measurement']['source_step'] == 1


def test_missing_support_measurement_does_not_invent_a_plane(adapter):
    y, x = np.mgrid[:8, :8]
    world = np.stack([x*.005, y*.005, np.full(x.shape, .9)], axis=-1)
    adapter.ex.toolkit._state.load = lambda _: world
    pixels = world.reshape(-1, 3)
    result, evidence = adapter._exclude_measured_support(pixels)
    np.testing.assert_array_equal(result, pixels)
    assert evidence is None


def test_rejected_zero_step_nudge_keeps_measured_contact_for_recovery(adapter, monkeypatch):
    original_obs = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original_obs(), 'robot0_gripper_qpos': [.02, -.02]}
    adapter.p.env.position[:] = [.1, .1, .9]
    initial = adapter.request(k=1)
    descend = next(c for c in initial['candidates'] if c['skill'] == 'descend')
    adapter._commit_grasp(descend)
    adapter.active = 'e1'
    committed = adapter.committed_grasps['e1']
    adapter.grasp_geometry = lambda entity: None
    request = adapter.request(k=1)
    nudge = next(c for c in request['candidates'] if c['skill'] == 'nudge')
    monkeypatch.setattr('robots.libero.bounded_skills.SmoothMotion.run',
        lambda *args, **kwargs: dict(executed=False, stop_reason='measured_sweep_collision'))
    receipt = adapter.execute(request, decision(request, [nudge['id']]))[0]
    assert receipt['outcome'] == 'failure' and receipt['steps_used'] == 0
    assert adapter.active == 'e1' and adapter.held is None
    assert adapter.committed_grasps['e1'] is committed
    assert any(c['skill'] == 'lift' for c in adapter.request(k=1)['candidates'])


@pytest.mark.parametrize('state', ['active', 'lost_identity', 'held'])
def test_precontact_curved_instance_recovers_occluded_rim_but_keeps_other_depth(adapter, state):
    angles = np.linspace(0., 2*np.pi, 80, endpoint=False)
    z, angle = np.meshgrid(np.linspace(.84, .96, 40), angles, indexing='ij')
    world = np.stack([.1+.02*np.cos(angle), .1+.02*np.sin(angle), z], axis=-1)
    reference = world.reshape(-1, 3).copy()
    missing = world[20, 65].copy()
    # A different present surface inside the old bounds does not become
    # target merely because it lies near the missing semantic boundary.
    world[20, 66, :2] = [.1, .117]
    other = world[20, 66].copy()
    current = world[:, 20:55].reshape(-1, 3)
    adapter._instance_pixels = lambda key: current
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: world))
    adapter._base_geometry = world.reshape(-1, 3), None
    adapter.active = 'e1'
    if state == 'held':
        adapter.held = 'e1'
    if state == 'lost_identity':
        reference += .2
    adapter.committed_grasps['e1'] = {'plan': {}, 'instance_reference': {
        'xyz_world': reference, 'source_step': 0}}
    result = adapter._contact_pixels('e1')
    assert bool((np.linalg.norm(result-missing, axis=1) < 1e-9).any()) is (state == 'active')
    assert not (np.linalg.norm(result-other, axis=1) < 1e-9).any()
    if state == 'active':
        evidence = adapter.instance_boundary_evidence['e1'][-1]
        assert evidence['reference_capture_step'] == 0 and evidence['capture_step'] == 4
        assert evidence['private_pose_used'] is False


@pytest.mark.parametrize('shift_m, has_static', [(.006, False), (.006, True), (.03, False)])
def test_precontact_surface_tracks_small_contact_motion_only(adapter, shift_m, has_static):
    y, x = np.mgrid[:30, :40]
    old = np.stack([.08+x*.001, .08+y*.001,
                    .9+.004*np.sin(x*.2)+.002*np.cos(y*.3)], axis=-1)
    world = old + [0., 0., shift_m]
    missing = world[15, 20].copy()
    current = world.copy()
    current[14:17, 19:22] = np.nan
    current = current[np.isfinite(current).all(axis=2)]
    # A separate nearby depth surface remains an obstacle after association.
    other = world[15, 21] + [0., 0., .006]
    world[15, 21] = other
    stationary = world[5, 5].copy()
    current = current[np.linalg.norm(current-stationary, axis=1) > 1e-9]
    adapter._instance_pixels = lambda key: current
    adapter._self_filtered_world = lambda points: points
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: world))
    adapter._base_geometry = (world.reshape(-1, 3), None)
    adapter.active = 'e1'
    adapter.committed_grasps['e1'] = {'plan': {}, 'instance_reference': {
        'xyz_world': old.reshape(-1, 3), 'source_step': 0,
        'stationary_scene': np.array([stationary]) if has_static else np.empty((0, 3))}}
    pixels = adapter._contact_pixels('e1')
    evidence = adapter.instance_boundary_evidence['e1'][-1]
    accepted = shift_m < .015
    assert evidence['surface_registration']['accepted'] is accepted
    assert bool((np.linalg.norm(pixels-missing, axis=1) < 1e-9).any()) is accepted
    assert not (np.linalg.norm(pixels-other, axis=1) < 1e-9).any()
    assert bool((np.linalg.norm(pixels-stationary, axis=1) < 1e-9).any()) is (accepted and not has_static)
    assert evidence['private_pose_used'] is False


def test_precontact_current_depth_connects_an_occluded_curved_patch_but_not_static_neighbour(adapter):
    y, x = np.mgrid[:30, :40]
    world = np.stack([.08+x*.001, .08+y*.001,
        .9+.004*np.sin(x*.2)+.002*np.cos(y*.2)], axis=-1)
    reference = world.reshape(-1, 3).copy()
    world[15, 20, 2] += .002
    missing = world[15, 20].copy()
    world[15, 21] = missing+[.001, 0., .006]
    other = world[15, 21].copy()
    current = world.copy()
    current[12:19, 17:24] = np.nan
    current = current[np.isfinite(current).all(axis=2)]
    adapter._instance_pixels = lambda key: current
    adapter._self_filtered_world = lambda points: points
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: world))
    adapter._base_geometry = (world.reshape(-1, 3), None)
    adapter.active = 'e1'
    adapter.committed_grasps['e1'] = {'plan': {}, 'instance_reference': {
        'xyz_world': reference, 'source_step': 0, 'stationary_scene': np.array([other])}}
    pixels = adapter._contact_pixels('e1')
    assert (np.linalg.norm(pixels-missing, axis=1) < 1e-9).any()
    assert not (np.linalg.norm(pixels-other, axis=1) < 1e-9).any()


@pytest.mark.parametrize('mode', ['continuous', 'depth_jump', 'filtered_robot'])
def test_precontact_rim_recovers_one_current_plane_edge_beyond_old_extent(adapter, mode):
    y, x = np.mgrid[:8, :20]
    world = np.stack([.1+x*.001, .1+y*.001, np.full(x.shape, .9)], axis=-1)
    old = world[:, :8].reshape(-1, 3).copy()
    wanted = world[4, 9].copy()
    world[:, 10:, 2] += .006  # A separate surface cannot join through this gap.
    if mode == 'depth_jump':
        world[:, 9, 2] += .006
        wanted = world[4, 9].copy()
    filtered = world.copy()
    if mode == 'filtered_robot':
        filtered[:, 9] = np.nan
    adapter._instance_pixels = lambda key: old
    adapter._self_filtered_world = lambda world: filtered
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: world))
    adapter._base_geometry = (filtered.reshape(-1, 3), None)
    adapter.active = 'e1'
    adapter.committed_grasps['e1'] = {'plan': {}, 'instance_reference': {
        'xyz_world': old, 'source_step': 0}}
    pixels = adapter._contact_pixels('e1')
    assert bool((np.linalg.norm(pixels-wanted, axis=1) < 1e-9).any()) is (mode == 'continuous')
    assert not (np.linalg.norm(pixels-world[4, 10], axis=1) < 1e-9).any()


@pytest.mark.parametrize('mode', ['valid', 'missing_seed', 'not_found'])
def test_payload_point_refinement_uses_measured_interior_and_bounds(adapter, monkeypatch, mode):
    entity = adapter.scene.entities['e1']
    y, x = np.mgrid[:5, :5]
    world = np.stack([.085+x*.005, .085+y*.005, np.full(x.shape, .9)], axis=-1)
    world[0, 0] = [.9, .9, .9]
    world[0, 1] = np.nan
    semantic = (x >= 1) & (x <= 3) & (y >= 1) & (y <= 3)
    mask = np.ones(x.shape, bool)
    if mode == 'missing_seed':
        mask[2, 2] = False
    reply = SimpleNamespace(found=mode != 'not_found', mask=mask, score=.96, reason='not_found')
    monkeypatch.setattr('rpent.robots.components.sam3_client.Sam3Client._decode_result', lambda _: reply)
    calls = []
    adapter.scene.rpc = SimpleNamespace(call=lambda *args, **kwargs: calls.append((args, kwargs)))
    adapter.scene.calls = 0
    adapter.ex.toolkit._state.load_bytes = lambda _: b'current-public-image'
    current = np.asarray([entity.lower, entity.upper])
    points, evidence = adapter._guided_payload_pixels(world, semantic, 'wrist', entity, current)
    assert calls[0][0] == ('sam3.segment',)
    assert calls[0][1]['kwargs']['point'] == [2, 2]
    assert 'text_prompt' not in calls[0][1]['kwargs']
    assert evidence['capture_step'] == 0 and evidence['private_pose_used'] is False
    assert len(points) == (23 if mode == 'valid' else 0)
    assert np.isfinite(points).all()
    assert (points >= entity.lower).all() and (points <= entity.upper).all()
    adapter._guided_payload_pixels(world, None, 'wrist', entity, current)
    assert len(calls) == 1


def test_payload_prompt_uses_owned_surface_without_carving_its_bounds(adapter, monkeypatch):
    from dataclasses import replace

    y, x = np.mgrid[:9, :9]
    world = np.stack([.08+x*.005, .08+y*.005, np.full(x.shape, .9)], axis=-1)
    semantic = np.ones(x.shape, bool)
    current = world[1:4, 1:4].reshape(-1, 3)
    calls = []
    adapter.scene.rpc = SimpleNamespace(call=lambda *args, **kwargs: calls.append(kwargs))
    adapter.scene.calls = 0
    adapter.ex.toolkit._state.load_bytes = lambda _: b'current-public-image'
    # A prompt bound cannot itself grant membership to other depth pixels.
    mask = np.zeros(x.shape, bool)
    mask[2, 2] = True
    mask[2, 1] = True
    mask[8, 8] = True
    monkeypatch.setattr('rpent.robots.components.sam3_client.Sam3Client._decode_result',
        lambda _: SimpleNamespace(found=True, mask=mask, score=.96, reason=''))
    entity = replace(adapter.scene.entities['e1'], lower=(.09, .08, .88))
    points, evidence = adapter._guided_payload_pixels(
        world, semantic, 'wrist', entity, current)
    assert calls[0]['kwargs']['point'] == [2, 2]
    np.testing.assert_array_equal(points, world[2, 1:3])
    assert points[0, 0] < entity.lower[0]
    assert evidence['member_pixels'] == 2
    empty, evidence = adapter._guided_payload_pixels(
        world, semantic, 'wrist', adapter.scene.entities['e1'], np.empty((0, 3)))
    assert len(empty) == 0 and len(calls) == 1
    assert evidence['reason'] == 'no_current_instance_depth_seed'


@pytest.mark.parametrize('seed_kind', ['current', 'stale_pose', 'filtered_robot'])
def test_payload_point_recovery_after_text_loss_needs_exact_current_depth(adapter, monkeypatch, seed_kind):
    y, x = np.mgrid[:5, :9]
    world = np.stack([.1+x*.001, .1+y*.001, np.full(x.shape, .9)], axis=-1)
    world[:, 7:, 2] += .02
    owned = (x >= 1) & (x <= 3) & (y >= 1) & (y <= 3)
    current = world[owned].copy()
    if seed_kind == 'stale_pose':
        current[:, 2] += .001
    if seed_kind == 'filtered_robot':
        filtered = world.copy()
        filtered[owned] = np.nan
        adapter._self_filtered_world = lambda _: filtered
    calls = []
    adapter.scene.rpc = SimpleNamespace(call=lambda *a, **kw: calls.append(kw) or {})
    adapter.scene.calls = 0
    adapter.ex.toolkit._state.load_bytes = lambda _: b'current-public-image'
    monkeypatch.setattr('rpent.robots.components.sam3_client.Sam3Client._decode_result',
        lambda _: SimpleNamespace(found=True, mask=np.ones(x.shape, bool), score=.96, reason=''))
    points, evidence = adapter._guided_payload_pixels(
        world, None, 'wrist', adapter.scene.entities['e1'], current)
    assert evidence['seed_source'] == 'exact_current_co_moving_rgbd_pixels'
    if seed_kind == 'current':
        assert calls[0]['kwargs']['point'] == [2, 2]
        np.testing.assert_array_equal(points, world[x < 7])
        assert evidence['depth_connected_pixels_outside_prompt_extent'] > 0
    else:
        assert not calls and len(points) == 0
        assert evidence['reason'] == 'no_current_instance_depth_seed'


@pytest.mark.parametrize('mode', ['connected', 'depth_gap', 'robot_gap'])
def test_guided_mask_can_measure_a_new_tail_but_cannot_bridge_an_obstacle(adapter, monkeypatch, mode):
    y, x = np.mgrid[:5, :7]
    world = np.stack([.1+x*.001, .1+y*.001, np.full(x.shape, .9)], axis=-1)
    if mode == 'depth_gap':
        world[:, 4:, 2] += .02
    semantic = (x >= 1) & (x <= 3) & (y >= 1) & (y <= 3)
    current = world[semantic]
    mask = np.ones(x.shape, bool)
    adapter.scene.rpc = SimpleNamespace(call=lambda *args, **kwargs: {})
    adapter.scene.calls = 0
    adapter.ex.toolkit._state.load_bytes = lambda _: b'current-public-image'
    if mode == 'robot_gap':
        adapter._base_geometry = (world[x != 4], None)
    monkeypatch.setattr('rpent.robots.components.sam3_client.Sam3Client._decode_result',
        lambda _: SimpleNamespace(found=True, mask=mask, score=.96, reason=''))
    points, evidence = adapter._guided_payload_pixels(
        world, semantic, 'wrist', adapter.scene.entities['e1'], current)
    included = np.any(np.linalg.norm(points-world[2, 5], axis=1) < 1e-9)
    assert bool(included) is (mode == 'connected')
    # The left tail remains depth-connected in all cases; only the right
    # tail is separated by the measured depth or robot gap.
    expected = world.reshape(-1, 3) if mode == 'connected' else world[x < 4]
    np.testing.assert_array_equal(points, expected)
    assert evidence['depth_connected_pixels_outside_prompt_extent'] == len(expected)-len(current)
    if mode == 'robot_gap':
        assert not np.any(np.linalg.norm(points-world[2, 4], axis=1) < 1e-9)


def test_public_request_omits_whole_task_and_vla_disabled(adapter):
    request = adapter.request(k=4)
    assert not any(c["skill"] in {"vla_task", "call_vla"} for c in request["candidates"])
    assert len([c for c in request["candidates"] if c["skill"] == "move_to"]) == 12
    with pytest.raises(ValueError, match="unknown"):
        selected(request, decision(request, ["invented"]))
    with pytest.raises(ValueError, match="stale"):
        selected(request, {**decision(request, [request["candidates"][0]["id"]]), "revision": 100})


@pytest.mark.parametrize('effect,expected', [
    ('stationary', 'no_effect'), ('moved', 'success'),
    ('occluded', 'no_effect'), ('stale', 'no_effect'),
    ('rgbd_occluded', 'unmeasured'), ('raw_stale', 'unmeasured'),
    ('opposite', 'failure'), ('perpendicular', 'no_effect'),
    ('boundary_moved', 'success'), ('boundary_opposite', 'failure'),
    ('segmentation_drift', 'no_effect'),
])
def test_contact_nudge_requires_current_object_motion_not_only_eef_arrival(adapter, effect, expected):
    from dataclasses import replace

    adapter.active = 'e1'
    surface = np.random.default_rng(97).uniform([-.02, -.015, -.01], [.02, .015, .01], (900, 3))
    shifted = np.zeros(3)
    original_screen = adapter._cloud_and_ik()
    def screen(*args, **kwargs):
        original_screen.target = surface+shifted
        cloud = np.empty((0, 3)) if effect == 'rgbd_occluded' else original_screen.target
        adapter._base_geometry = (cloud, None)
        return original_screen
    adapter._cloud_and_ik = screen
    def refresh(_):
        entity = adapter.scene.entities['e1']
        delta = {'moved': [0., .02, 0.], 'opposite': [0., -.02, 0.],
            'boundary_moved': [0., .006, 0.], 'boundary_opposite': [0., -.006, 0.],
            'perpendicular': [.02, 0., 0.], 'segmentation_drift': [0., .02, 0.]}.get(effect, [0., 0., 0.])
        shifted[:] = delta if effect != 'segmentation_drift' else [0., 0., 0.]
        adapter.scene.entities['e1'] = replace(entity,
            xyz=tuple(np.asarray(entity.xyz)+delta),
            visible=effect != 'occluded',
            source_step=entity.source_step+(effect != 'stale'))
    adapter.scene.refresh = refresh
    if effect == 'raw_stale':
        adapter.ex.capture = lambda: None
    initial = adapter.robot()['eef_xyz_m']
    request = adapter.request(k=1)
    candidate = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'anchor_id': 'e1', 'axis': 'y', 'distance_m': .02})
    receipt = adapter.execute(request, decision(request, [candidate['id']]))[0]
    assert receipt['outcome'] == expected
    assert adapter.robot()['eef_xyz_m'][1]-initial[1] == pytest.approx(.02)
    assert adapter.details[-1]['execution']['public_contact_motion']['source'] == 'paired_public_rgbd_axis_surface_registration'
    if effect in {'opposite', 'boundary_opposite'}:
        assert receipt['stop_reason'] == 'contact_motion_opposes_command'
    if effect in {'moved', 'opposite', 'perpendicular', 'boundary_moved', 'boundary_opposite'}:
        assert adapter.details[-1]['execution']['public_contact_motion']['axis_progress_m'] == pytest.approx(
            {'moved': .02, 'opposite': -.02, 'perpendicular': 0.,
             'boundary_moved': .006, 'boundary_opposite': -.006}[effect])
    if effect == 'stationary':
        request = adapter.request(k=1)
        adapter.execute(request, decision(request, [candidate['id']]))
        assert all(c['id'] != candidate['id'] for c in adapter.request(k=1)['candidates'])


@pytest.mark.parametrize('entity_state', ['cached', 'removed'])
def test_nudge_uses_fresh_depth_when_sam_loses_handle_identity(adapter, entity_state):
    from dataclasses import replace

    handle = np.random.default_rng(271).uniform([-.015, -.01, -.01], [.015, .01, .01], (900, 3))
    shift = np.zeros(3)
    original = adapter._cloud_and_ik()
    def screen(*args, **kwargs):
        original.target = handle+shift
        adapter._base_geometry = (original.target, None)
        return original
    adapter._cloud_and_ik = screen
    adapter.active = 'e1'
    request = adapter.request(k=1)
    def refresh(_):
        shift[:] = [0., .02, 0.]
        if entity_state == 'removed':
            adapter.scene.entities.pop('e1')
        else:
            adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], visible=False)
    adapter.scene.refresh = refresh
    candidate = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'anchor_id': 'e1', 'axis': 'y', 'distance_m': .02})
    receipt = adapter.execute(request, decision(request, [candidate['id']]))[0]
    assert receipt['outcome'] == 'success'
    motion = adapter.details[-1]['execution']['public_contact_motion']
    assert not motion['entity_measurement_current']
    assert motion['axis_progress_m'] == pytest.approx(.02)
    assert (motion['before_capture_step'], motion['after_capture_step']) == (0, 1)
    assert any(e['measurement_id'] == 'rgbd-contact:0:1:e1' and e['source'] == 'derived_public'
        for e in receipt['evidence'])
    validate(receipt)


def test_free_space_nudge_reports_motion_arrival_without_object_effect(adapter):
    request = adapter.request(k=1)
    candidate = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'y', 'distance_m': .02})
    assert adapter.execute(request, decision(request, [candidate['id']]))[0]['outcome'] == 'success'


def test_held_nudge_registers_moving_payload_when_stationary_target_is_empty(adapter):
    from dataclasses import replace

    from scipy.spatial.transform import Rotation

    adapter.active = adapter.held = 'e1'
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.02, -.02]}
    surface = np.random.default_rng(52).uniform([.08, .08, .88], [.12, .12, .92], (900, 3))
    shift = np.zeros(3)
    public_screen = adapter._cloud_and_ik()
    public_screen.target = np.empty((0, 3))
    def screen(*args, **kwargs):
        robot = adapter.robot()
        public_screen.payload = ((surface+shift-robot['eef_xyz_m'])
            @ Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix())
        adapter._base_geometry = (surface+shift, None)
        return public_screen
    adapter._cloud_and_ik = screen
    def refresh(_):
        shift[:] = [0., .02, 0.]
        entity = adapter.scene.entities['e1']
        adapter.scene.entities['e1'] = replace(entity,
            xyz=tuple(np.asarray(entity.xyz)+shift),
            lower=tuple(np.asarray(entity.lower)+shift),
            upper=tuple(np.asarray(entity.upper)+shift), source_step=entity.source_step+1)
    adapter.scene.refresh = refresh
    request = adapter.request(k=1)
    candidate = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'anchor_id': 'e1', 'axis': 'y', 'distance_m': .02})
    receipt = adapter.execute(request, decision(request, [candidate['id']]))[0]
    assert receipt['outcome'] == 'success'
    assert adapter.held == 'e1'
    fit = adapter.details[-1]['execution']['public_contact_motion']['surface_registration']
    assert fit['accepted'] and fit['translation_m'][1] == pytest.approx(.02)


@pytest.mark.parametrize('committed_handle', [False, True])
def test_nudge_measures_handle_motion_independently_of_stationary_parent_pixels(adapter, committed_handle):
    from dataclasses import replace

    rng = np.random.default_rng(27)
    handle = rng.uniform([-.015, -.01, -.01], [.015, .01, .01], (900, 3))
    parent = rng.uniform([-.03, -.11, -.03], [.03, -.09, .03], (2000, 3))
    shifted = np.zeros(3)
    original = adapter._cloud_and_ik()
    def screen(*args, **kwargs):
        original.target = np.r_[parent, handle+shifted]
        adapter._base_geometry = (original.target, None)
        return original
    adapter._cloud_and_ik = screen
    adapter._handle_pixels = lambda *args, **kwargs: np.empty((0, 3)) if committed_handle else handle.copy()
    if committed_handle:
        # Screening recovered this old identity in current depth; the
        # original capture itself is deliberately unavailable as current.
        adapter._contact_pixels = lambda key, *, handle_only=False: (
            handle.copy() if handle_only else np.r_[parent, handle])
    adapter.active = 'e1'
    request = adapter.request(k=1)
    adapter.plans['e1']['handle_measurement'] = {'source_step': 0}
    def refresh(_):
        shifted[:] = [0., .02, 0.]
        entity = adapter.scene.entities['e1']
        adapter.scene.entities['e1'] = replace(entity, source_step=1)
    adapter.scene.refresh = refresh
    candidate = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'anchor_id': 'e1', 'axis': 'y', 'distance_m': .02})
    receipt = adapter.execute(request, decision(request, [candidate['id']]))[0]
    assert receipt['outcome'] == 'success'
    fit = adapter.details[-1]['execution']['public_contact_motion']['surface_registration']
    assert fit['translation_m'][1] == pytest.approx(.02)


def test_contacted_drawer_occlusion_retains_cached_anchor_and_measured_plan(adapter):
    from dataclasses import replace

    measured = replace(adapter.scene.entities['e1'], name='cabinet middle drawer',
        visible=False, source_step=2)
    adapter.scene.entities['e1'] = measured
    adapter.active = 'e1'
    adapter.gripper_command = 1.
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.02, -.02]}
    plan = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0, 0, 0, 1], 'width_m': .04}
    adapter.committed_grasps['e1'] = {'plan': plan, 'anchor_xyz': np.array(measured.xyz)}
    request = adapter.request(k=4)
    anchor = next(a for a in request['anchors'] if a['id'] == 'e1')
    assert anchor['cached'] and anchor['evidence'][0]['capture_step'] == 2
    assert adapter.plans['e1'] == plan
    assert any(c['skill'] == 'nudge' and c['parameters'].get('anchor_id') == 'e1'
        for c in request['candidates'])
    validate(request)


@pytest.mark.parametrize('removed', [False, True])
def test_removed_or_uncommitted_occluded_entity_has_no_dangling_candidate_references(adapter, removed):
    from dataclasses import replace

    adapter.active = 'e1'
    if removed:
        adapter.scene.entities.clear()
    else:
        adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], visible=False)
    request = adapter.request(k=4)
    assert request['anchors'] == []
    assert not any(c['parameters'].get('anchor_id') for c in request['candidates'])
    assert any(c['skill'] == 'observe' for c in request['candidates'])
    validate(request)


def test_private_upper_bound_retains_resolved_public_identity(adapter):
    from robots.libero.bounded_oracle import BoundedOracle
    status = {"done": False, "goals": [["on", "box_1", "plate_1"]], "satisfied": [False]}
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: status), adapter)
    request = adapter.request(k=1)
    oracle.choose(request)
    assert oracle.binding._bindings["box_1"] == "e1"
    assert oracle.private_trace[-1]["source_public_id"] == "e1"
    assert "box_1" not in str(request)
    # A temporarily missing peer must remain excluded from later rebinding.
    oracle.binding._binding_peers['box_1'] = {'previous_other_box'}
    oracle.choose(adapter.request(k=1))
    assert oracle.binding._binding_peers['box_1'] == {'previous_other_box'}


@pytest.mark.parametrize('skill', ['carry_to', 'lower'])
def test_transport_centres_measured_bounds_instead_of_dense_visible_walls(adapter, skill):
    from dataclasses import replace

    held = adapter.scene.entities['e1']
    adapter.scene.entities['e1'] = replace(held, xyz=(.119, .115, held.xyz[2]))
    adapter.scene.entities['e2'] = Entity('e2', 'basket', (.379, .27, .87),
        (.22, .16, .8), (.38, .34, .94), True, 0)
    adapter.held = 'e1'
    start = np.asarray(adapter.robot()['eef_xyz_m'])
    route = adapter._route(skill, {'target_id': 'e2'})
    held_midpoint = (np.asarray(held.lower)+held.upper)/2
    target_midpoint = np.array([.30, .25])
    assert np.asarray(route[-1]['xyz_m'])[:2] == pytest.approx(
        target_midpoint+(start-held_midpoint)[:2])


def test_carry_preserves_height_and_clears_higher_targets_before_translation(adapter):
    adapter.held = 'e1'
    start = np.asarray(adapter.robot()['eef_xyz_m'])
    for height in (start[2]-.4, start[2]+.1):
        adapter.scene.entities['e2'] = Entity('e2', 'plate', (.3, .2, height),
            (.25, .15, height-.01), (.35, .25, height+.01), True, 0)
        route = adapter._route('carry_to', {'target_id': 'e2'})
        assert route[-1]['xyz_m'][2] >= start[2]
        if route[-1]['xyz_m'][2] > start[2]:
            np.testing.assert_allclose(route[0]['xyz_m'][:2], start[:2])
            assert route[0]['xyz_m'][2] == route[-1]['xyz_m'][2]


@pytest.mark.parametrize('mode', ['attached', 'dropped', 'occluded', 'stale'])
@pytest.mark.parametrize('blended', [False, True])
def test_transport_rechecks_visible_holding_and_releases_a_dropped_payload(adapter, mode, blended):
    from dataclasses import replace

    adapter.held = adapter.active = 'e1'
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.5, .4, .9),
        (.45, .35, .89), (.55, .45, .91), True, 0)
    adapter.scene.entities['e3'] = Entity('e3', 'plate', (.65, .4, .9),
        (.60, .35, .89), (.70, .45, .91), True, 0)
    prior = adapter.scene.entities['e1']
    before = adapter.robot()
    def refresh(_):
        delta = np.asarray(adapter.robot()['eef_xyz_m'])-before['eef_xyz_m']
        if mode == 'dropped':
            delta = np.zeros(3)
        adapter.scene.entities['e1'] = replace(prior,
            xyz=tuple(np.asarray(prior.xyz)+delta), lower=tuple(np.asarray(prior.lower)+delta),
            upper=tuple(np.asarray(prior.upper)+delta), visible=mode != 'occluded',
            source_step=prior.source_step+(mode != 'stale'))
    adapter.scene.refresh = refresh
    request = adapter.request(k=4 if blended else 1)
    candidate = next(c for c in request['candidates'] if c['skill'] == 'carry_to'
        and c['parameters']['target_id'] == 'e2')
    choices = [candidate]
    if blended:
        choices.append(next(c for c in request['candidates'] if c['skill'] == 'carry_to'
            and c['parameters']['target_id'] == 'e3'))
        if mode == 'dropped':
            choices.append(next(c for c in request['candidates'] if c['skill'] == 'release'))
    receipts = adapter.execute(request, decision(request, [c['id'] for c in choices]))
    receipt = receipts[-1]
    if blended:
        assert adapter.details[-1]['blended']
        assert len(receipts) == (1 if mode == 'dropped' else 2)
        if mode != 'dropped':
            assert receipts[0]['outcome'] == 'success'
    if mode == 'dropped':
        assert receipt['outcome'] == 'failure' and receipt['stop_reason'] == 'public_hold_lost'
        assert receipt['phase'] == 'contact_failure'
        assert adapter.held is adapter.active is adapter.ex.held is None
        assert adapter.payload_reference is adapter.grasp_reference is None
        assert next(c for c in receipt['changes'] if c['anchor_id'] == 'e1')['held'] is False
        assert all(c['consequences']['screen_scope'] == 'conditional_on_prefix'
        for c in adapter.request(k=1)['candidates'] if c['skill'] == 'carry_to')
    else:
        assert receipt['outcome'] == 'success'
        assert adapter.held == 'e1'


def test_transport_holding_bounds_follow_rotation_instead_of_assuming_a_fixed_world_offset(adapter):
    from dataclasses import replace

    from scipy.spatial.transform import Rotation

    prior = adapter.scene.entities['e1']
    before = {'eef_xyz_m': [0., 0., 1.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    rotation = Rotation.from_euler('z', np.pi/2)
    corners = np.array([[x, y, z] for x in (prior.lower[0], prior.upper[0])
        for y in (prior.lower[1], prior.upper[1]) for z in (prior.lower[2], prior.upper[2])])
    points = rotation.apply(corners-before['eef_xyz_m'])+before['eef_xyz_m']
    current = replace(prior, xyz=tuple(points.mean(axis=0)), lower=tuple(points.min(axis=0)),
        upper=tuple(points.max(axis=0)), source_step=1)
    evidence = adapter._held_motion_evidence(prior, current, before,
        {**before, 'eef_quat_xyzw': rotation.as_quat().tolist()})
    assert evidence['extent_gap_m'] == pytest.approx(0.) and not evidence['lost']


@pytest.mark.parametrize('blended', [False, True])
def test_empty_jaws_interrupt_transport_before_endpoint_even_when_payload_is_occluded(adapter, blended):
    from dataclasses import replace

    adapter.held = adapter.active = adapter.ex.held = 'e1'
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.5, .4, .9),
        (.45, .35, .89), (.55, .45, .91), True, 0)
    raw_obs = adapter.p.env.raw_obs
    def measured():
        opening = .001 if len(adapter.p.actions) >= 8 else .03
        return {**raw_obs(), 'robot0_gripper_qpos': [opening/2, -opening/2]}
    adapter.p.env.raw_obs = measured
    def occluded(_):
        adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], visible=False)
    adapter.scene.refresh = occluded
    request = adapter.request(k=4 if blended else 1)
    carry = next(c for c in request['candidates'] if c['skill'] == 'carry_to'
        and c['parameters']['target_id'] == 'e2')
    choices = [carry]
    if blended:
        choices.append(next(c for c in request['candidates'] if c['skill'] == 'lower'
            and c['parameters']['target_id'] == 'e2'))
    receipts = adapter.execute(request, decision(request, [c['id'] for c in choices]))
    assert len(receipts) == 1
    assert receipts[0]['stop_reason'] == 'public_hold_lost'
    assert receipts[0]['outcome'] == 'failure' and receipts[0]['phase'] == 'contact_failure'
    assert adapter.held is adapter.active is adapter.ex.held is None
    result = adapter.details[-1]['execution']
    assert result['braking']['executed']
    assert next(i for i, row in enumerate(result['trace']) if row['braking']) == 8
    assert result['steps_used'] < carry['consequences']['expected_steps']
    assert all(c['consequences']['screen_scope'] == 'conditional_on_prefix'
        for c in adapter.request(k=1)['candidates'] if c['skill'] == 'carry_to')


def test_empty_jaw_stop_uses_original_sensor_calibration_and_keeps_thin_held_rim(adapter):
    adapter.ex.grasp_measurement_calibration = {'opening_calibration': {
        'closed_empty_max_m': .001, 'open_empty_min_m': .08, 'tolerance_m': .001}}
    adapter.held = 'e1'
    assert adapter._empty_held_gripper({'gripper_opening_m': .002})
    assert not adapter._empty_held_gripper({'gripper_opening_m': .003})
    adapter.held = None
    assert not adapter._empty_held_gripper({'gripper_opening_m': .001})


def test_held_alignment_uses_measured_support_normal_and_preserves_projected_closing_axis(adapter):
    from scipy.spatial.transform import Rotation

    adapter.held = 'e1'
    normal = np.array([.03, -.02, 1.])
    normal /= np.linalg.norm(normal)
    adapter.scene.work_surface_measurement = {'normal_xyz': normal.tolist(),
        'centroid_xyz': [0., 0., .8], 'source': 'perception'}
    rotation = Rotation.from_euler('xyz', [np.pi, .7, .2])
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_eef_quat': rotation.as_quat()}
    request = adapter.request(k=1)
    candidate = next(c for c in request['candidates'] if c['skill'] == 'align')
    assert candidate['parameters'] == {'anchor_id': 'e1'}
    route = adapter._route('align', candidate['parameters'])
    np.testing.assert_allclose(route[0]['xyz_m'], request['robot']['eef_xyz_m'])
    aligned = Rotation.from_quat(route[0]['quat_xyzw'])
    np.testing.assert_allclose(aligned.apply([0., 0., 1.]), -normal, atol=1e-10)
    closing = rotation.apply([0., -1., 0.])
    closing -= normal*(closing@normal)
    closing /= np.linalg.norm(closing)
    np.testing.assert_allclose(aligned.apply([0., -1., 0.]), closing, atol=1e-10)
    rotation = aligned
    assert adapter._route('align', candidate['parameters']) is None


def test_oracle_selects_existing_measured_alignment_after_carry_ik_rejection(adapter):
    from scipy.spatial.transform import Rotation

    from robots.libero.bounded_oracle import BoundedOracle

    adapter.held = 'e1'
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.3, .1, .9),
        (.25, .05, .89), (.35, .15, .91), True, 0)
    adapter.scene.work_surface_measurement = {'normal_xyz': [0., 0., 1.],
        'centroid_xyz': [0., 0., .8], 'source': 'perception'}
    raw = adapter.p.env.raw_obs
    quat = Rotation.from_euler('xyz', [np.pi, .7, 0.]).as_quat()
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_eef_quat': quat}
    request = adapter.request(k=1)
    for candidate in request['candidates']:
        if candidate['skill'] == 'carry_to':
            candidate['consequences']['ik_reachable'] = False
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: {
        'done': False, 'goals': [['on', 'box_1', 'plate_1']], 'satisfied': [False]}), adapter)
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['skill'] == 'align' and chosen['parameters'] == {'anchor_id': 'e1'}


@pytest.mark.parametrize('available', [.02, .01, None])
def test_oracle_uses_only_a_clear_bounded_lift_after_blocked_transport(adapter, available):
    from robots.libero.bounded_oracle import BoundedOracle

    adapter.active = adapter.held = 'e1'
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.3, .1, .9),
        (.25, .05, .89), (.35, .15, .91), True, 0)
    request = adapter.request(k=1)
    for c in request['candidates']:
        if c['skill'] in {'carry_to', 'align'}:
            c['consequences']['collision'] = True
        if c['skill'] == 'nudge':
            c['consequences']['collision'] = (c['parameters'].get('axis') != 'z'
                or c['parameters'].get('distance_m') != available)
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: {
        'done': False, 'goals': [['on', 'box_1', 'plate_1']], 'satisfied': [False]}), adapter)
    chosen = selected(request, oracle.choose(request))[0]
    if available is None:
        assert chosen['skill'] == 'observe'
        assert 'recovery' not in oracle.private_trace[-1]
    else:
        assert chosen['skill'] == 'nudge'
        assert chosen['parameters'] == {'anchor_id': 'e1', 'axis': 'z', 'distance_m': available}
        assert oracle.private_trace[-1]['recovery'] == 'screened_bounded_lift_after_blocked_transport'


@pytest.mark.parametrize('direction', [-1, 1])
@pytest.mark.parametrize('available', [.01, .02, None])
def test_oracle_uses_only_screened_lateral_progress_when_lift_is_blocked(adapter, direction, available):
    from robots.libero.bounded_oracle import BoundedOracle

    adapter.active = adapter.held = 'e1'
    x = .1+.2*direction
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (x, .1, .9),
        (x-.05, .05, .89), (x+.05, .15, .91), True, 0)
    request = adapter.request(k=1)
    for candidate in request['candidates']:
        parameters = candidate['parameters']
        if candidate['skill'] in {'carry_to', 'align', 'nudge'}:
            candidate['consequences']['collision'] = True
        if candidate['skill'] == 'nudge' and parameters['axis'] == 'x':
            # An away-from-goal move is clear too; it must not be chosen.
            if parameters['distance_m'] == -.02*direction:
                candidate['consequences']['collision'] = False
            if available is not None and parameters['distance_m'] == available*direction:
                candidate['consequences']['collision'] = False
    oracle = BoundedOracle(SimpleNamespace(call=lambda _: {
        'done': False, 'goals': [['on', 'box_1', 'plate_1']], 'satisfied': [False]}), adapter)
    chosen = selected(request, oracle.choose(request))[0]
    if available is None:
        assert chosen['skill'] == 'observe'
    else:
        assert chosen['skill'] == 'nudge'
        assert chosen['parameters'] == {'anchor_id': 'e1', 'axis': 'x', 'distance_m': available*direction}
        assert oracle.private_trace[-1]['recovery'] == 'screened_lateral_progress_after_blocked_transport'


def test_oracle_can_select_a_previously_measured_occluded_target(adapter):
    from robots.libero.bounded_oracle import BoundedOracle

    target = Entity('e2', 'plate', (.3, .1, .9), (.25, .05, .89), (.35, .15, .91),
                    False, 0, geometry='cached_perception_visible_surface')
    adapter.scene.entities['e2'] = target
    adapter.target_cache['e2'] = target
    adapter.held = 'e1'
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: {
        'done': False, 'goals': [['on', 'box_1', 'plate_1']], 'satisfied': [False]}), adapter)
    request = adapter.request(k=1)
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['skill'] == 'carry_to' and chosen['parameters']['target_id'] == 'e2'
    assert next(a for a in request['anchors'] if a['id'] == 'e2')['cached'] is True


@pytest.mark.parametrize('second_feasible_reference', [False, True])
def test_oracle_between_reference_is_resolved_jointly_without_deleting_anchors(second_feasible_reference):
    from robots.libero.bounded_oracle import BoundedOracle

    def entity(key, name, x, y):
        return Entity(key, name, (x, y, .93), (x-.03, y-.03, .91),
                      (x+.03, y+.03, .95), True, 0)

    measured = [entity('e28', 'bowl', -.0731, .2011),
                entity('e79', 'bowl', -.2068, .3258),
                entity('e90', 'plate', .0730, .2090),
                entity('e84', 'ramekin', -.2291, .2106),
                entity('e97', 'plate', -.2502, -.1275)]
    if second_feasible_reference:
        measured[-1] = entity('e97', 'plate', -.1845, .4410)
    instruction = 'pick up the black bowl between the plate and the ramekin and place it on the plate'
    plan = {'xyz_m': [-.0731, .2011, .93], 'quat_xyzw': [0., 0., 0., 1.],
            'approach_xyz_m': [-.0731, .2011, 1.1]}
    adapter = SimpleNamespace(ex=SimpleNamespace(instruction=instruction), held=None,
        scene=SimpleNamespace(entities={e.id: e for e in measured}, view_axes=((0, 1, 0), (1, 0, 0))),
        plans={'e28': plan, 'e79': plan}, receipts=[])
    oracle = BoundedOracle(SimpleNamespace(call=lambda _: {
        'done': False, 'goals': [['on', 'akita_black_bowl_9', 'plate_7']], 'satisfied': [False]}), adapter)
    request = {'schema_version': 'bounded-skills/3', 'revision': 0,
        'observation_id': 'public-0', 'max_actions': 1,
        'robot': {'eef_xyz_m': [0., 0., 1.2], 'eef_quat_xyzw': [0., 0., 0., 1.],
                  'gripper_opening_m': .08},
        'anchors': [{'id': e.id} for e in measured],
        'candidates': [{'id': 'approach', 'skill': 'move_to',
                        'consequences': {'collision': False, 'ik_reachable': True, 'screen_scope': 'hand_mesh_observed_space'},
                        'parameters': {'anchor_id': 'e28', 'approach': 'above', 'path': 'over'}},
                       {'id': 'scan', 'skill': 'observe',
                        'consequences': {'collision': False, 'ik_reachable': True, 'screen_scope': 'hand_mesh_observed_space'},
                        'parameters': {'mode': 'wrist_scan'}}]}
    result = oracle._choose_one(request, oracle.rpc.call('oracle.status'))
    assert result['id'] == ('scan' if second_feasible_reference else 'approach')
    assert oracle.private_trace[-1]['target_public_id'] == (None if second_feasible_reference else 'e90')
    assert list(adapter.scene.entities) == ['e28', 'e79', 'e90', 'e84', 'e97']
    assert len(request['anchors']) == 5


@pytest.mark.parametrize('predicate,gap,blocked,expected', [
    ('on', .08, True, 'release'), ('on', .08, False, 'lower'),
    ('on', .15, True, 'observe'), ('in', .08, True, 'observe'),
])
def test_oracle_uses_existing_release_only_above_nearby_support(adapter, predicate, gap, blocked, expected):
    from robots.libero.bounded_oracle import BoundedOracle

    top = adapter.scene.entities['e1'].lower[2]-gap
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.1, .1, top-.01),
        (.05, .05, top-.02), (.15, .15, top), True, 0)
    adapter.held = 'e1'
    adapter.target_cache['e2'] = adapter.scene.entities['e2']
    oracle = BoundedOracle(SimpleNamespace(call=lambda _: {
        'done': False, 'goals': [[predicate, 'box_1', 'plate_1']], 'satisfied': [False]}), adapter)
    request = adapter.request(k=1)
    for candidate in request['candidates']:
        if candidate['skill'] == 'lower':
            candidate['consequences']['collision'] = blocked
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['skill'] == expected
    assert 'recovery' not in str(request)


def test_empty_hand_preserves_measured_static_target_through_occlusion(adapter):
    from dataclasses import replace

    target = Entity('e2', 'area front of stove', (.3, .1, .9),
        (.25, .05, .89), (.35, .15, .91), True, 0)
    adapter.scene.entities['e2'] = target
    adapter.refresh()
    adapter.scene.entities['e2'] = replace(target, visible=False, source_step=5)
    # A movable source without current evidence must not acquire the static
    # target exemption just because it has an old measurement in the cache.
    source = adapter.scene.entities['e1']
    adapter.scene.entities['e1'] = replace(source, visible=False)
    request = adapter.request(k=1)
    assert adapter.held is None
    assert [a['id'] for a in request['anchors']] == ['e2']
    anchor = request['anchors'][0]
    assert anchor['cached'] and anchor['evidence'][0]['capture_step'] == 0
    assert anchor['xyz_m'] == list(target.xyz)
    candidate = adapter._candidate('nudge', {'anchor_id': 'e2', 'axis': 'x', 'distance_m': .01})
    assert candidate['consequences']['evidence_ids'] == ['rgbd:0:e2']


def test_oracle_does_not_lift_a_push_source_when_its_target_is_missing(adapter):
    from dataclasses import replace

    from robots.libero.bounded_oracle import BoundedOracle

    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], name='plate')
    adapter.ex.instruction = 'push the plate to the front of the stove'
    adapter.active = 'e1'
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.02, -.02]}
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: {
        'done': False, 'goals': [['on', 'plate_1', 'main_table_stove_front_region']],
        'satisfied': [False]}), adapter)
    request = adapter.request(k=1)
    assert any(c['skill'] == 'lift' for c in request['candidates'])
    assert selected(request, oracle.choose(request))[0]['skill'] == 'observe'


def test_held_payload_retains_target_cache_in_request_route_and_release(adapter, monkeypatch):
    from dataclasses import replace

    from robots.libero.bounded_oracle import BoundedOracle

    target = Entity('e2', 'plate', (.3, .1, .9), (.25, .05, .89), (.35, .15, .91), True, 0)
    adapter.scene.entities['e2'] = target
    adapter.refresh()
    adapter.held = 'e1'
    # The new visible mask supplies current obstacle evidence but is only a
    # partial view of the destination. It cannot overwrite its release pose.
    adapter.scene.entities['e2'] = replace(target, xyz=(.35, .15, .9), source_step=5)
    monkeypatch.setattr(adapter, '_refresh_held_measurement', lambda: None)
    adapter.refresh()
    assert adapter.target_cache['e2'] == target
    request = adapter.request(k=1)
    anchor = next(a for a in request['anchors'] if a['id'] == 'e2')
    assert anchor['cached'] and anchor['xyz_m'] == list(target.xyz)
    assert anchor['evidence'][0]['capture_step'] == 0
    route = adapter._route('carry_to', {'target_id': 'e2'})
    start = np.asarray(adapter.robot()['eef_xyz_m'])
    np.testing.assert_allclose(route[-1]['xyz_m'][:2],
        (np.asarray(target.xyz)+start-adapter.scene.entities['e1'].xyz)[:2])
    adapter.scene.entities['e1'] = Entity('e1', 'box', (.301, .101, .93),
        (.28, .08, .91), (.32, .12, .95), True, 5)
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: {
        'done': False, 'goals': [['on', 'box_1', 'plate_1']], 'satisfied': [False]}), adapter)
    request = adapter.request(k=1)
    assert selected(request, oracle.choose(request))[0]['skill'] == 'release'
    # A later empty-hand observation refreshes the destination normally.
    adapter.held = None
    adapter.refresh()
    assert adapter.target_cache['e2'].source_step == 5


def test_vla_history_cannot_be_attached_to_other_actions(adapter):
    import jsonschema
    request = adapter.request(k=1)
    request["candidates"][0]["history"] = {"n": 0, "success_rate": None,
        "expected_steps": None, "source_manifest_sha256": None}
    with pytest.raises(jsonschema.ValidationError):
        validate(request)


def test_unmeasured_relation_id_is_rejected(adapter):
    request = adapter.request(k=1)
    request["relations"] = [{"source_id": "e1", "relation": "on", "target_id": "private-or-missing"}]
    with pytest.raises(ValueError, match="unmeasured anchor"):
        validate(request)


def test_transfer_vla_requires_a_measured_target(adapter):
    import jsonschema
    adapter.allow_vla = True
    request = adapter.request(k=1)
    call = next(c for c in request["candidates"] if c["skill"] == "call_vla")
    call["parameters"]["mode"] = "on"
    with pytest.raises(jsonschema.ValidationError):
        validate(request)
    call["parameters"]["target_id"] = "missing"
    with pytest.raises(ValueError, match="unmeasured anchor"):
        validate(request)
    call["parameters"]["target_id"] = "e1"
    validate(request)


def test_motion_candidate_executes_using_measured_pose(adapter):
    request = adapter.request(k=1)
    candidate = next(c for c in request["candidates"] if c["skill"] == "nudge" and c["parameters"] == {"axis": "x", "distance_m": .01})
    receipt = adapter.execute(request, decision(request, [candidate["id"]]))[0]
    assert receipt["outcome"] == "success"
    assert receipt["steps_used"] > 0
    assert abs(receipt["after"]["eef_xyz_m"][0]-.01) < 1e-8


def test_gripper_contact_saves_every_control_for_exact_prefix_replay(adapter):
    from scripts.probe_bounded_prefix_diagnostic import prefix_controls

    request = adapter.request(k=1)
    candidate = next(c for c in request['candidates'] if c['skill'] == 'set_gripper'
                     and c['parameters']['mode'] == 'close')
    receipts = adapter.execute(request, decision(request, [candidate['id']]))
    trace = prefix_controls([{'index': 0, 'sim_steps_before': 0,
        'sim_steps_after': receipts[0]['steps_used'],
        'execution_details': adapter.details[-1:]}], 0)
    assert len(trace) == 15
    assert all(t['action'][-1] == 1. for t in trace)
    assert all('finger_positions_m' in t['before'] and 'finger_positions_m' in t['after'] for t in trace)


def test_public_screen_record_preserves_exact_obstacle_pixels_outside_model_request(adapter, tmp_path):
    import hashlib
    from pathlib import Path

    from rpent.session.base import EnvState

    state = EnvState(tmp_path)
    with state.record_step(state={}):
        pass
    adapter.ex.toolkit = SimpleNamespace(_state=state)
    points = np.array([[.001, .002, .003], [.004, .005, .006]])
    adapter.record_public_geometry = True
    evidence = adapter._record_public_geometry('bounded_screen_e1_scene', points)
    path = Path(evidence['path'])
    with np.load(path) as stored:
        np.testing.assert_array_equal(stored[stored.files[0]], points)
    assert evidence['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert evidence['capture_step'] == 0 and evidence['private_truth_used'] is False
    request = adapter.request(k=1)
    assert 'public_geometry_evidence' not in request
    assert str(path) not in str(request)


def test_grasp_search_rejects_blocked_top_and_keeps_screened_side_entry(adapter, monkeypatch):
    from copy import deepcopy

    points = np.repeat([[.1, .1, .9]], 40, axis=0)
    adapter.scene.measurement_clouds['e1'] = points
    rows = []
    for name, entry, score in [('top', [.1, 0., 1.], 2.), ('side', [0., .1, .9], 1.)]:
        rows.append({'id': name, 'rejected': [], 'route_status': 'not_screened',
            'route': [{'xyz': entry, 'body_quat_xyzw': [0, 0, 0, 1]},
                      {'xyz': [.1, .1, .9], 'body_quat_xyzw': [0, 0, 0, 1]}],
            'approach_xyz': entry, 'xyz': [.1, .1, .9], 'body_quat_xyzw': [0, 0, 0, 1],
            'width_m': .03, 'measurement_confidence': .9, 'score': score})
    monkeypatch.setattr('robots.libero.v5_grasp_route.sample_unified_grasps',
        lambda *args, **kwargs: (None, deepcopy(rows)))
    class Screen:
        def __init__(self):
            self.target, self.points, self.ik = points, np.empty((0, 3)), object()
        def __call__(self, poses):
            blocked = any(p['xyz_m'][0] > .05 and p['xyz_m'][1] < .001 for p in poses)
            return {'passed': not blocked, 'reason': 'measured_sweep_collision' if blocked else 'clear',
                'collision': blocked, 'ik_reachable': True, 'path_min_clearance_m': 0. if blocked else .02}
    adapter._cloud_and_ik = lambda *args, **kwargs: Screen()
    monkeypatch.setattr('robots.libero.v5_geometric_grasp.collision_counts', lambda *args, **kwargs: {})
    plan = MeasuredSkillAdapter.grasp_geometry(adapter, adapter.scene.entities['e1'])
    assert plan['grasp_candidate_id'] == 'side'
    diagnostics = adapter.candidate_diagnostics[-1]['candidates']
    assert diagnostics[0]['rejected'] == ['measured_sweep_collision']
    assert diagnostics[1]['route_status'] == 'passed'
    adapter.plans['e1'] = plan
    approach = adapter._route('move_to', {'anchor_id': 'e1', 'approach': plan['preferred_approach'], 'path': 'over'})
    assert approach[-1]['xyz_m'] == rows[1]['approach_xyz']
    assert adapter._route('descend', {'anchor_id': 'e1'})[-1]['xyz_m'] == rows[1]['xyz']


def test_no_opposition_does_not_build_full_scene_or_skip_route_checks(adapter, monkeypatch):
    adapter.scene.measurement_clouds['e1'] = np.repeat([[.1, .1, .9]], 40, axis=0)
    monkeypatch.setattr('robots.libero.v5_grasp_route.sample_unified_grasps',
        lambda *args, **kwargs: (None, [{'id': 'bad', 'rejected': ['no_opposition']}]))
    adapter._cloud_and_ik = lambda *args, **kwargs: pytest.fail('no route to screen')
    adapter._surface_contact_plan = lambda *args: None
    assert MeasuredSkillAdapter.grasp_geometry(adapter, adapter.scene.entities['e1']) is None
    assert adapter.candidate_diagnostics[-1]['selected'] is None


@pytest.mark.parametrize('primary_clear,closure_clear', [(True, True), (False, True), (False, False)])
def test_side_bands_wait_for_failed_routes_and_keep_closure_screen(adapter, monkeypatch,
                                                                  primary_clear, closure_clear):
    adapter.scene.measurement_clouds['e1'] = np.repeat([[.1, .1, .9]], 40, axis=0)
    sampled = []
    def sample(*args, include_band_seeds=False, **kwargs):
        sampled.append(include_band_seeds)
        entry = [0., .1, .9] if include_band_seeds else [.1, 0., 1.]
        return None, [{'id': 'band' if include_band_seeds else 'primary', 'rejected': [],
            'route': [{'xyz': entry, 'body_quat_xyzw': [0, 0, 0, 1]},
                      {'xyz': [.1, .1, .9], 'body_quat_xyzw': [0, 0, 0, 1]}],
            'approach_xyz': entry, 'xyz': [.1, .1, .9], 'body_quat_xyzw': [0, 0, 0, 1],
            'width_m': .03, 'measurement_confidence': .9, 'score': 1.}]
    monkeypatch.setattr('robots.libero.v5_grasp_route.sample_unified_grasps', sample)
    class Screen:
        points = np.array([[2., 2., 2.]])
        target = np.empty((0, 3))
        def __call__(self, poses):
            blocked = not primary_clear and any(p['xyz_m'][0] > .05 and p['xyz_m'][1] < .001 for p in poses)
            return {'passed': not blocked, 'reason': 'measured_sweep_collision' if blocked else 'clear',
                'collision': blocked, 'ik_reachable': True, 'path_min_clearance_m': 0. if blocked else .02}
    adapter._cloud_and_ik = lambda *args, **kwargs: Screen()
    adapter._surface_contact_plan = lambda *args: None
    monkeypatch.setattr('robots.libero.v5_geometric_grasp.collision_counts',
        lambda points, *args, **kwargs: {'palm': int(not closure_clear and len(points) > 0)})
    plan = MeasuredSkillAdapter.grasp_geometry(adapter, adapter.scene.entities['e1'])
    if primary_clear:
        assert sampled == [False] and plan['grasp_candidate_id'] == 'primary'
    else:
        assert sampled == [False, True]
        if closure_clear:
            assert plan['grasp_candidate_id'] == 'band'
            assert adapter.candidate_diagnostics[-1]['sampling_pass'] == 'route_fallback_bands'
        else:
            assert plan is None
            assert adapter.candidate_diagnostics[-1]['candidates'][0]['rejected'] == ['closure_sweep_collision']


def test_fixture_stages_along_measured_normal_and_uses_pad_contact_offset(adapter):
    from dataclasses import replace

    from scipy.spatial.transform import Rotation

    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], name='microwave')
    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.01, -.01, .003],
        'upper': [.01, .01, .005]} for name in ('leftfinger', 'rightfinger')]
    adapter.scene.measure_fixture_handle_pose = lambda *args: {'pose': {
        'xyz': [.1, .1, .9], 'approach_normal_xyz': [0., -1., 0.]}}
    request = adapter.request(k=4)
    plan = adapter.plans['e1']
    np.testing.assert_allclose(np.asarray(plan['approach_xyz_m'])-plan['xyz_m'], [0., -.12, 0.])
    body = Rotation.from_quat(plan['quat_xyzw']).as_matrix()
    site = body@Rotation.from_euler('z', -np.pi/2).as_matrix()
    np.testing.assert_allclose(np.asarray(plan['xyz_m'])+site@[0., 0., .004], [.1, .1, .9])
    move = next(c for c in request['candidates'] if c['skill'] == 'move_to'
        and c['parameters']['approach'] == 'front' and c['parameters']['path'] == 'over')
    route = adapter._route('move_to', move['parameters'])
    assert route[-1]['xyz_m'] == route[-2]['xyz_m'] == plan['approach_xyz_m']
    assert route[0]['quat_xyzw'] == route[-2]['quat_xyzw'] == request['robot']['eef_quat_xyzw']
    current = Rotation.from_quat(request['robot']['eef_quat_xyzw'])
    chosen = Rotation.from_quat(plan['quat_xyzw'])
    assert (chosen*current.inv()).magnitude() <= (
        chosen*Rotation.from_euler('z', np.pi)*current.inv()).magnitude()+1e-9


def test_current_handle_pixels_are_contact_members_but_stale_samples_are_not(adapter, tmp_path):
    points = np.array([[.1, .1, .9], [.11, .1, .9]])
    path = tmp_path/'handle.npz'
    np.savez(path, points)
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=3))
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    handle = {'source_step': 3, 'views': {'main': {'pose': {'xyz': [.1, .1, .9]}, 'cloud': {
        'path': str(path), 'source': 'perception', 'source_step': 3}}}}
    adapter.plans['e1'] = {'handle_measurement': handle}
    np.testing.assert_equal(adapter._contact_pixels('e1'), points)
    adapter.ex.toolkit._state.latest_step = 4
    assert len(adapter._contact_pixels('e1')) == 0


def test_full_current_control_surface_does_not_change_grasp_patch_or_own_neighbour(adapter, tmp_path):
    y, x = np.mgrid[:10, :10]
    patch = np.stack([.1+x*.0005, .1+y*.0005, np.full(x.shape, .9)], axis=-1)
    side = patch.copy()
    side[:, :, 2] -= .015
    full = np.concatenate([patch.reshape(-1, 3), side.reshape(-1, 3)])
    neighbour = patch.copy()
    neighbour[:, :, 0] += .02
    world = np.concatenate([patch, side, neighbour])
    for name, points in (('patch', patch.reshape(-1, 3)), ('full', full)):
        np.savez(tmp_path/f'{name}.npz', points)
    def cloud(name):
        return {'path': str(tmp_path/f'{name}.npz'), 'source': 'perception', 'source_step': 3}
    measurement = {'source_step': 3, 'views': {'agentview': {
        'pose': {'xyz': [.1, .1, .9]}, 'cloud': cloud('patch'), 'contact_cloud': cloud('full')}}}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=3, load=lambda _: world))
    adapter._self_filtered_world = lambda world: world
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    adapter.plans['e1'] = {'handle_measurement': measurement}
    np.testing.assert_equal(adapter._handle_pixels(measurement), patch.reshape(-1, 3))
    contact = adapter._contact_pixels('e1')
    assert any(np.array_equal(point, side[5, 5]) for point in contact)
    assert np.max(contact[:, 0]) < np.min(neighbour[:, :, 0])
    adapter.ex.toolkit._state.latest_step = 4
    assert len(adapter._contact_pixels('e1')) == 0


@pytest.mark.parametrize('object_moved', [False, True])
@pytest.mark.parametrize('withdrawal', [False, True])
def test_precontact_refresh_keeps_current_handle_pixels_inside_old_extent_only(
        adapter, tmp_path, object_moved, withdrawal):
    from dataclasses import replace

    y, x = np.mgrid[:10, :10]
    surface = np.stack([.1+x*.0005, .1+y*.0005, np.full(x.shape, .9)], axis=-1)
    path = tmp_path/'handle.npz'
    np.savez(path, surface.reshape(-1, 3))
    current = surface.copy()
    current[-1, :, 2] += .006
    current[:, -1, 0] += .01  # A continuation outside the old extent is not owned.
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: current))
    adapter.plans['e1'] = {'handle_measurement': {'source_step': 3, 'views': {'main': {
        'pose': {'xyz': [.1, .1, .9]}, 'cloud': {
            'path': str(path), 'source': 'perception', 'source_step': 3}}}}}
    entity = adapter.scene.entities['e1']
    adapter.committed_grasps['e1'] = {'anchor_xyz': np.asarray(entity.xyz)}
    if withdrawal:
        adapter.withdrawal_contact = {**adapter.committed_grasps.pop('e1'),
            'anchor_id': 'e1', 'plan': adapter.plans.pop('e1')}
    if object_moved:
        adapter.scene.entities['e1'] = replace(entity, xyz=(.12, .1, .9))
    pixels = adapter._contact_pixels('e1')
    if object_moved:
        assert len(pixels) == 0
    else:
        assert len(pixels) > 0
        assert np.max(pixels[:, 2]) == .9 and np.max(pixels[:, 0]) < .11
        assert all(e['reference_capture_step'] == 3 and e['capture_step'] == 4
            and e['private_pose_used'] is False for e in adapter.instance_boundary_evidence['e1'])


@pytest.mark.parametrize('object_moved', [False, True])
def test_release_recovers_latest_contact_surface_without_sam_or_hand_attachment(adapter, object_moved):
    from copy import deepcopy

    y, x = np.mgrid[:10, :10]
    surface = np.stack([.1+x*.0005, .1+y*.0005, np.full(x.shape, .9)], axis=-1)
    current = surface.copy()
    current[-1, :, 2] += .006  # An adjacent depth discontinuity remains an obstacle.
    state = SimpleNamespace(latest_step=4, load=lambda _: current)
    adapter.ex.toolkit = SimpleNamespace(_state=state)
    adapter._self_filtered_world = lambda world: world
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.01, -.01]}
    adapter.active = 'e1'
    request = adapter.request(k=1)
    adapter.committed_grasps['e1'] = {'plan': deepcopy(adapter.plans['e1']),
        'anchor_xyz': np.array(adapter.scene.entities['e1'].xyz)}
    screen = adapter._cloud_and_ik()
    screen.target = surface.reshape(-1, 3).copy()
    release = next(c for c in request['candidates'] if c['skill'] == 'release')
    adapter.execute(request, decision(request, [release['id']]))
    saved = adapter.withdrawal_contact['withdrawal_surface']
    np.testing.assert_array_equal(saved['xyz_world'], surface.reshape(-1, 3))
    assert saved['source_step'] == 4 and adapter.active is adapter.held is None
    # The pre-release capture is copied, and neither the old SAM plan nor
    # subsequent hand movement may translate its stationary identity.
    screen.target[:] += .2
    adapter.scene.entities.clear()
    adapter.plans.clear()
    adapter.p.env.position += [.03, 0., .04]
    state.latest_step = 5
    if object_moved:
        current[:, :, 0] += .03
    prior_evidence = len(adapter.instance_boundary_evidence.get('e1', []))
    recovered = adapter._contact_pixels('e1')
    if object_moved:
        assert len(recovered) == 0
    else:
        assert len(recovered) > 0 and np.max(recovered[:, 2]) == .9
    evidence = adapter.instance_boundary_evidence['e1'][prior_evidence:]
    assert {e['camera'] for e in evidence} == {'agentview', 'wrist'}
    assert all(e['source'] == 'current_rgbd_matches_last_contact_before_release'
        and e['reference_capture_step'] == 4 and e['capture_step'] == 5
        and e['private_pose_used'] is False for e in evidence)


@pytest.mark.parametrize('derived_part', [False, True])
def test_instance_recovers_unsegmented_view_surface_but_not_neighbour(adapter, derived_part):
    y, x = np.mgrid[:8, :20]
    primary = np.stack([x*.0005, y*.0005, np.ones_like(x)], axis=-1)
    part = Entity('e2', 'cabinet top drawer' if derived_part else 'box',
        (.00475, .00175, 1.), (0., 0., 1.), (.0095, .0035, 1.),
        True, 3, part_of='e1' if derived_part else None,
        geometry='measured_front_band' if derived_part else 'segmented_rgbd_bounds')
    adapter.scene.entities[part.id] = part
    secondary = primary.copy()
    secondary[..., 2] += .0008
    secondary[:, 12:, 2] += .003
    metadata = {'width': 20, 'height': 8,
        'intrinsic_K': [[2000., 0., 0.], [0., 2000., 0.], [0., 0., 1.]],
        'extrinsic_cam2world': np.eye(4).tolist()}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=3,
        load=lambda name: metadata if name.endswith('_metadata.json')
            else primary if name.startswith('agentview') else secondary))
    adapter.scene.measurement_clouds_by_view = {part.id: {'agentview': {
        'xyz_world': primary.reshape(-1, 3), 'source_step': 3}}}
    pixels = adapter._instance_pixels(part.id)
    assert np.any(np.all(pixels == secondary[4, 5], axis=1))
    assert not np.any(np.all(pixels == secondary[4, 16], axis=1))
    assert adapter.instance_boundary_evidence[part.id][-1]['private_pose_used'] is False


def test_contacted_handle_recovers_current_surface_but_keeps_adjacent_obstacle(adapter, tmp_path):
    from robots.libero.bounded_motion import measured_robot

    x, y = np.meshgrid(np.arange(10)*.0005, np.arange(10)*.0005)
    surface = np.stack([x+.1, y+.1, np.full_like(x, .9)], axis=-1)
    path = tmp_path/'handle.npz'
    np.savez(path, surface.reshape(-1, 3))
    adapter.active = 'e1'
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.01, -.02]}
    handle = {'source_step': 3, 'views': {'main': {'pose': {'xyz': [.1, .1, .9]},
        'cloud': {'path': str(path), 'source': 'perception', 'source_step': 3}}}}
    adapter.plans['e1'] = {'handle_measurement': handle}
    adapter.committed_grasps['e1'] = {'contact_robot': measured_robot(adapter.p)}
    # One depth-discontinuous adjacent row has no support from the old
    # handle. Neither stored points nor a bounding-box halo may own it.
    current = surface.copy()
    current[-1, :, 2] += .006
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: current))
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    recovered = adapter._contact_pixels('e1')
    assert len(recovered) > 0 and np.max(recovered[:, 2]) == .9
    assert all(e['private_pose_used'] is False for e in adapter.instance_boundary_evidence['e1'])
    assert len(adapter._handle_pixels(handle, contact_surface=True)) == 0
    parent = np.array([[.1, .1, .8]])
    adapter._instance_pixels = lambda key: parent
    handle_pixels = adapter._contact_pixels('e1', handle_only=True)
    assert len(handle_pixels) > 0 and np.min(handle_pixels[:, 2]) == .9
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    adapter.active = None
    assert len(adapter._contact_pixels('e1')) == 0


def test_partial_current_handle_keeps_still_measured_committed_side(adapter, tmp_path):
    from robots.libero.bounded_motion import measured_robot

    y, x = np.mgrid[:10, :10]
    original = np.stack([.1+x*.0005, .1+y*.0005, np.full(x.shape, .9)], axis=-1)
    world = original.copy()
    world[-1, :, 2] += .006
    def measurement(name, points, step):
        path = tmp_path/f'{name}.npz'
        np.savez(path, points)
        return {'source_step': step, 'views': {'agentview': {
            'pose': {'xyz': [.1, .1, .9]}, 'cloud': {
                'path': str(path), 'source': 'perception', 'source_step': step}}}}
    old = measurement('full', original.reshape(-1, 3), 3)
    partial = measurement('partial', world[:-1, :3].reshape(-1, 3), 4)
    adapter.active = 'e1'
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.01, -.02]}
    adapter.plans['e1'] = {'handle_measurement': partial}
    adapter.committed_grasps['e1'] = {'contact_robot': measured_robot(adapter.p),
        'plan': {'handle_measurement': old}}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: world))
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    pixels = adapter._contact_pixels('e1')
    assert any(np.array_equal(point, world[5, 1]) for point in pixels)
    assert any(np.array_equal(point, world[5, 7]) for point in pixels)
    assert not any(np.array_equal(point, world[9, 7]) for point in pixels)


def test_vertical_handle_recovers_curved_side_from_measured_axis_not_backing_tangent(adapter, tmp_path):
    from robots.libero.bounded_motion import measured_robot

    z, angle = np.meshgrid(np.linspace(-.06, .06, 40),
                           np.linspace(0., 2*np.pi, 100, endpoint=False), indexing='ij')
    world = np.stack([.1+.008*np.cos(angle), .1+.008*np.sin(angle), .9+z], axis=-1)
    path = tmp_path/'vertical_handle.npz'
    np.savez(path, world[(angle >= .1) & (angle <= 2.9)])
    handle = {'source_step': 3, 'pose': {'handle_tangent_xy': [1., 0.]},
        'views': {'agentview': {'pose': {'xyz': [.1, .1, .9]}, 'cloud': {
            'path': str(path), 'source': 'perception', 'source_step': 3}}}}
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.01, -.02]}
    adapter.active = 'e1'
    adapter.plans['e1'] = {'handle_measurement': handle}
    adapter.committed_grasps['e1'] = {'contact_robot': measured_robot(adapter.p),
        'plan': {'handle_measurement': handle}}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: world))
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    pixels = adapter._contact_pixels('e1', handle_only=True)
    assert any(np.array_equal(point, world[20, 75]) for point in pixels)
    fits = [e for e in adapter.instance_boundary_evidence['e1'] if 'handle_axis_measurement' in e]
    assert fits and all(abs(e['handle_axis_measurement']['axis_xyz'][2]) > .99 for e in fits)


def test_contacted_thin_surface_recovers_only_current_stationary_pixels(adapter):
    y, x = np.mgrid[:10, :10]
    world = np.stack([.1+x*.0005, .1+y*.0005, np.full(x.shape, .9)], axis=-1)
    original = world.reshape(-1, 3).copy()
    world[-1, :, 2] += .006
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: world))
    adapter.committed_grasps['e1'] = {'plan': {'contact_kind': 'surface', 'surface_measurement': {
        'xyz_world': original.tolist(), 'source_step': 3}}}
    adapter.active = 'e1'
    pixels = adapter._contact_pixels('e1')
    assert len(pixels) > 0 and np.allclose(pixels[:, 2], .9)
    assert adapter.instance_boundary_evidence['e1'][-1]['reference_capture_step'] == 3
    adapter.active = None
    assert len(adapter._contact_pixels('e1')) == 0


def test_tracked_handle_does_not_grow_onto_connected_backing_surface(adapter, tmp_path):
    from robots.libero.bounded_motion import measured_robot

    y, x = np.mgrid[:10, :60]
    world = np.stack([.1+x*.0005, .1+y*.0005, np.full(x.shape, .9)], axis=-1)
    original = world[:, :10].reshape(-1, 3).copy()
    path = tmp_path/'handle.npz'
    np.savez(path, original)
    handle = {'source_step': 3, 'views': {'agentview': {
        'pose': {'xyz': [.1, .1, .9]}, 'cloud': {
            'path': str(path), 'source': 'perception', 'source_step': 3}}}}
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.01, -.02]}
    adapter.active = 'e1'
    adapter.plans['e1'] = {'handle_measurement': handle}
    adapter.committed_grasps['e1'] = {'contact_robot': measured_robot(adapter.p),
        'plan': {'handle_measurement': handle}}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: world))
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    pixels = adapter._contact_pixels('e1', handle_only=True)
    assert len(pixels) > 0
    assert pixels[:, 0].max() <= original[:, 0].max()+.001
    assert not any(np.array_equal(point, world[5, 40]) for point in pixels)


@pytest.mark.parametrize('moved', [False, True])
def test_precontact_surface_keeps_measured_extent_without_owning_neighbour(adapter, moved):
    from dataclasses import replace

    y, x = np.mgrid[:10, :10]
    original = np.stack([.1+x*.0005, .1+y*.0005, .9+np.where(x < 5, 0., .002)], axis=-1)
    world = original.copy()
    world[-1, :, 2] += .006
    adapter._instance_pixels = lambda key: world[:4, :2].reshape(-1, 3)
    adapter._self_filtered_world = lambda world: world
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: world))
    adapter.plans['e1'] = {'surface_measurement': {
        'xyz_world': original.reshape(-1, 3).tolist(), 'source_step': 3}}
    entity = adapter.scene.entities['e1']
    adapter.committed_grasps['e1'] = {'plan': adapter.plans['e1'], 'anchor_xyz': np.asarray(entity.xyz)}
    if moved:
        adapter.scene.entities['e1'] = replace(entity, xyz=(.12, .1, .9))
    pixels = adapter._contact_pixels('e1')
    assert any(np.array_equal(point, world[5, 7]) for point in pixels) is not moved
    assert not any(np.array_equal(point, world[9, 7]) for point in pixels)


@pytest.mark.parametrize('filtered_gap', [False, True])
def test_contact_surface_boundary_uses_current_measurement_but_not_depth_or_robot_gaps(adapter, filtered_gap):
    y, x = np.mgrid[:10, :12]
    world = np.stack([.1+x*.0005, .1+y*.0005, np.full(x.shape, .906)], axis=-1)
    world[:, 9:, 2] += .01
    original = world.copy()
    original[..., 2] = .9  # Closing exposed a surface outside the old depth band.
    adapter._instance_pixels = lambda key: world[:, 2:5].reshape(-1, 3)
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: world))
    adapter.plans['e1'] = {'surface_measurement': {'xyz_world': original.reshape(-1, 3), 'source_step': 3}}
    adapter.active = 'e1'
    if filtered_gap:
        adapter._base_geometry = (world[(x < 6) | (x >= 8)], None)
    pixels = adapter._contact_pixels('e1')
    assert bool(np.linalg.norm(pixels-world[3, 7], axis=1).min() < 1e-9) is (not filtered_gap)
    assert pixels[:, 2].max() == .906


@pytest.mark.parametrize('force_normal_fit', [False, True])
@pytest.mark.parametrize('shift_m,accepted', [(.004, True), (.02, False)])
@pytest.mark.parametrize('rolling', [False, True])
def test_contacted_handle_refines_small_public_depth_motion_without_owning_neighbour(
        adapter, tmp_path, monkeypatch, shift_m, accepted, force_normal_fit, rolling):
    from robots.libero.bounded_motion import measured_robot

    if force_normal_fit:
        monkeypatch.setattr('robots.libero.bounded_payload._surface_registration',
            lambda predicted, measured: (predicted, {'accepted': False,
                'reason': 'surface_shift_exceeds_public_hold_tolerance'}))
    y, x = np.mgrid[:12, :12]
    old = np.stack([.1+x*.001, .1+y*.001, np.full(x.shape, .9)], axis=-1)
    path = tmp_path/'handle.npz'
    np.savez(path, old.reshape(-1, 3))
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.01, -.02]}
    adapter.active = 'e1'
    adapter.committed_grasps['e1'] = {'contact_robot': measured_robot(adapter.p)}
    if rolling:
        # Earlier public frames already measured most of this change.
        # Association must continue from that frame, not the initial fit.
        latest = old.copy()
        latest[..., 2] += max(0., shift_m-.004)
        adapter.committed_grasps['e1']['contact_surface_reference'] = {
            'robot': measured_robot(adapter.p), 'xyz_world': latest.reshape(-1, 3), 'source_step': 2}
    adapter.plans['e1'] = {'handle_measurement': {'source_step': 3,
        'pose': {'approach_normal_xyz': [0., 0., 1.]}, 'views': {
        'main': {'pose': {'xyz': [.105, .105, .9]}, 'cloud': {
            'path': str(path), 'source': 'perception', 'source_step': 3}}}}}
    current = old.copy()
    current[..., 2] += shift_m
    scene = current.reshape(-1, 3).copy()
    # The neighbouring final row is not the contacted plane.
    current[-1, :, 2] += .006
    adapter._base_geometry = scene, None
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4, load=lambda _: current))
    pixels = adapter._contact_pixels('e1')
    expected = accepted or rolling
    assert bool(len(pixels)) is expected
    if expected:
        np.testing.assert_allclose(pixels[:, 2], .9+shift_m)
    evidence = next(v for v in adapter.instance_boundary_evidence['e1'] if 'registration' in v)
    assert evidence['registration']['accepted'] is expected
    assert evidence['reference_capture_step'] == (2 if rolling else 3)
    assert evidence['private_pose_used'] is False


def test_current_handle_view_recovers_another_views_new_surface_but_not_its_neighbour(adapter, tmp_path):
    from robots.libero.bounded_motion import measured_robot

    y, x = np.mgrid[:10, :10]
    main = np.stack([.1+x*.0005, .1+y*.0005, np.full(x.shape, .9)], axis=-1)
    old = main[:, :3].reshape(-1, 3)
    path = tmp_path/'handle.npz'
    np.savez(path, old)
    wrist = main.copy()
    wrist[..., 0] += .0045
    wrist[-1, :, 2] += .006  # A separate surface must remain an obstacle.
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.01, -.02]}
    adapter.active = 'e1'
    old_handle = {'source_step': 3, 'views': {
        'main': {'pose': {'xyz': [.1, .1, .9]}, 'cloud': {
            'path': str(path), 'source': 'perception', 'source_step': 3}}}}
    adapter.committed_grasps['e1'] = {'contact_robot': measured_robot(adapter.p),
        'plan': {'handle_measurement': old_handle}}
    current_path = tmp_path/'current_handle.npz'
    np.savez(current_path, main.reshape(-1, 3))
    # A newly observed side needs an independent CURRENT handle measurement;
    # smooth continuation from an old patch could instead be the backing.
    adapter.plans['e1'] = {'handle_measurement': {'source_step': 4, 'views': {
        'main': {'pose': {'xyz': [.1, .1, .9]}, 'cloud': {
            'path': str(current_path), 'source': 'perception', 'source_step': 4}}}}}
    adapter._instance_pixels = lambda key: np.empty((0, 3))
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4,
        load=lambda name: wrist if name.startswith('wrist') else main))
    pixels = adapter._contact_pixels('e1')
    assert np.any(np.linalg.norm(pixels-wrist[4, 1], axis=1) < 1e-9)
    assert not np.any(np.linalg.norm(pixels-wrist[-1, 1], axis=1) < 1e-9)
    evidence = [v for v in adapter.instance_boundary_evidence['e1']
        if v['source'] == 'current_rgbd_matches_other_current_contact_pixels']
    assert len(evidence) == 2 and all(v['surface_residual_m'] == .001 for v in evidence)


def test_fixture_search_rejects_long_palm_collision_and_screens_short_entry_through_contact(adapter):
    plan = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
        'approach_xyz_m': [.1, -.02, .9], 'handle_measurement': {'pose': {}},
        'width_m': .01, 'preferred_approach': 'front'}
    routes = []
    def screen(poses):
        routes.append(poses)
        blocked = any(p['xyz_m'][1] < .045 and p['xyz_m'][2] < .95 for p in poses)
        return {'passed': not blocked, 'reason': 'measured_sweep_collision' if blocked else 'clear',
            'collision': blocked, 'ik_reachable': True, 'path_min_clearance_m': 0. if blocked else .02}
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    result = adapter._screen_fixture_approaches(adapter.scene.entities['e1'], plan)
    np.testing.assert_allclose(result['approach_xyz_m'], [.1, .06, .9])
    np.testing.assert_allclose(routes[-1][-1]['xyz_m'], plan['xyz_m'])
    choices = adapter.candidate_diagnostics[-1]['candidates']
    old_routes = [c for c in choices if c['rotate_at'] in {'entry', 'clearance'}]
    assert [choice['stand_off_m'] for choice in old_routes[:5]] == [.12, .12, .08, .08, .04]
    assert all(choice['screen']['collision'] for choice in old_routes[:4])
    assert old_routes[4]['screen']['passed']


def test_fixture_direct_entry_avoids_unreachable_extra_lift_and_keeps_contact_screen(adapter):
    plan = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
        'approach_xyz_m': [.1, -.02, .9], 'width_m': .01, 'preferred_approach': 'front'}
    checked = []
    def screen(poses):
        checked.append(poses)
        blocked = any(p['xyz_m'][2] > 1.01 for p in poses)
        return {'passed': not blocked, 'reason': 'numerical_ik_not_found' if blocked else 'clear',
            'collision': False, 'ik_reachable': not blocked, 'path_min_clearance_m': .02}
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    result = adapter._screen_fixture_approaches(adapter.scene.entities['e1'], plan)
    assert result is not None and result['preferred_path'] == 'direct'
    assert all(np.allclose(poses[-1]['xyz_m'], plan['xyz_m']) for poses in checked)
    adapter.plans['e1'] = result
    assert adapter._route('move_to', {'anchor_id': 'e1', 'approach': 'front', 'path': 'direct'}) == result['approach_route']


def test_fixture_with_blocked_contact_has_no_plan_even_when_entry_is_clear(adapter):
    plan = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
        'approach_xyz_m': [.1, -.02, .9]}
    def screen(poses):
        contact = poses[-1]['xyz_m']
        blocked = np.linalg.norm(np.asarray(contact)-plan['xyz_m']) < 1e-9
        return {'passed': not blocked, 'reason': 'measured_sweep_collision' if blocked else 'clear',
            'collision': blocked, 'ik_reachable': True, 'path_min_clearance_m': 0.}
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    assert adapter._screen_fixture_approaches(adapter.scene.entities['e1'], plan) is None
    assert adapter.candidate_diagnostics[-1]['selected'] is None
    assert all(c['screen']['collision'] for c in adapter.candidate_diagnostics[-1]['candidates'])


def test_fixture_replans_a_symmetric_contact_after_measured_joint_limit_failure(adapter):
    from scipy.spatial.transform import Rotation

    plan = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
        'approach_xyz_m': [.1, -.02, .9], 'width_m': .01}
    adapter.failed_contact_poses['e1'] = [dict(plan)]
    result = adapter._screen_fixture_approaches(adapter.scene.entities['e1'], plan)
    turn = (Rotation.from_quat(result['quat_xyzw'])*Rotation.from_quat(plan['quat_xyzw']).inv()).magnitude()
    assert turn == pytest.approx(np.pi)
    choices = adapter.candidate_diagnostics[-1]['candidates']
    old_routes = [c for c in choices if c['rotate_at'] in {'entry', 'clearance'}]
    assert all(c['screen']['reason'] == 'measured_joint_limit_during_prior_descent' for c in old_routes[:6])
    assert old_routes[6]['screen']['passed']


def test_fixture_prefers_symmetric_route_with_larger_public_ik_joint_margin(adapter):
    from scipy.spatial.transform import Rotation

    plan = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
        'approach_xyz_m': [.1, -.02, .9], 'width_m': .01}
    def screen(poses):
        turn = Rotation.from_quat(poses[-1]['quat_xyzw']).magnitude()
        margin = .2 if turn > 3. else 1e-6
        return {'passed': True, 'reason': 'clear', 'collision': False,
            'ik_reachable': True, 'path_min_clearance_m': .02,
            'ik_checks': [{'solves': [{'solution_found': True,
                'joint_margin_min_rad': margin}]}]}
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    result = adapter._screen_fixture_approaches(adapter.scene.entities['e1'], plan)
    assert Rotation.from_quat(result['quat_xyzw']).magnitude() == pytest.approx(np.pi)
    choices = adapter.candidate_diagnostics[-1]['candidates']
    old_routes = [c for c in choices if c['rotate_at'] in {'entry', 'clearance'}]
    assert old_routes[0]['screen']['passed'] and old_routes[6]['screen']['passed']
    assert old_routes[0]['screen']['route_joint_margin_rad'] == 1e-6
    assert choices[adapter.candidate_diagnostics[-1]['selected']] is old_routes[6]


@pytest.mark.parametrize('joint_margin', [.001, .1])
def test_partial_descent_retains_only_withdrawal_identity_and_records_actual_joint_limits(
        adapter, monkeypatch, joint_margin):
    seen = []
    original_screen = adapter._cloud_and_ik
    def screen(anchor=None, *, contact=False):
        seen.append((anchor, contact))
        result = original_screen(anchor, contact=contact)
        result.ik = SimpleNamespace(limits=np.array([[-1., joint_margin]]*7))
        return result
    adapter._cloud_and_ik = screen
    request = adapter.request(k=1)
    descend = next(c for c in request['candidates'] if c['skill'] == 'descend')
    def fail(motion, *args, **kwargs):
        motion.p._step_env(np.zeros(7))
        return {'executed': True, 'steps_used': 1, 'stop_reason': 'tracking_error',
            'endpoint_error_m': .04, 'trace': []}
    with monkeypatch.context() as patch:
        patch.setattr('robots.libero.bounded_skills.SmoothMotion.run', fail)
        receipt = adapter.execute(request, decision(request, [descend['id']]))[0]
    assert receipt['outcome'] == 'failure'
    assert adapter.active is adapter.held is None
    assert adapter.withdrawal_contact['anchor_id'] == 'e1'
    assert 'e1' not in adapter.committed_grasps
    assert bool(adapter.failed_contact_poses.get('e1')) is (joint_margin < .02)
    request = adapter.request(k=1)
    scan = next(c for c in request['candidates'] if c['skill'] == 'observe'
        and c['parameters']['mode'] == 'wrist_scan')
    seen.clear()
    adapter.execute(request, decision(request, [scan['id']]))
    assert ('e1', True) in seen
    assert adapter.withdrawal_contact is None and adapter.active is adapter.held is None


def test_wrist_scan_uses_a_screened_side_route_when_up_is_unreachable(adapter):
    tried = []
    def screen(poses):
        end = poses[-1]['xyz_m']
        passed = end[0] > .03
        tried.append(passed)
        return {'passed': passed, 'reason': 'clear' if passed else 'numerical_ik_not_found',
            'collision': False, 'ik_reachable': passed, 'path_min_clearance_m': .02}
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    request = adapter.request(k=1)
    scan = next(c for c in request['candidates'] if c['skill'] == 'observe'
        and c['parameters']['mode'] == 'wrist_scan')
    adapter.execute(request, decision(request, [scan['id']]))
    attempts = adapter.details[-1]['execution']['scan_route_attempts']
    assert [(a['offset_m'], a['executed']) for a in attempts] == [
        ([0., 0., .04], False), ([.04, 0., 0.], True)]
    np.testing.assert_allclose(adapter.robot()['eef_xyz_m'], [.04, 0., 1.], atol=1e-8)


def test_release_preserves_measured_withdrawal_surface_without_claiming_attachment(adapter):
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.01, -.01]}
    adapter.active = 'e1'
    request = adapter.request(k=1)
    descend = next(c for c in request['candidates'] if c['skill'] == 'descend')
    adapter._commit_grasp(descend)
    release = next(c for c in request['candidates'] if c['skill'] == 'release')
    adapter.execute(request, decision(request, [release['id']]))
    assert adapter.held is adapter.active is None and adapter.committed_grasps == {}
    assert adapter.withdrawal_contact['anchor_id'] == 'e1'
    assert adapter.robot()['held_anchor_id'] is None
    assert adapter.grasp_reference is adapter.payload_reference is None


def test_successive_scans_keep_released_surface_identity_without_active_contact(adapter):
    reference = {'anchor_id': 'e1', 'plan': {'xyz_m': [.1, .1, .9]},
        'withdrawal_surface': {'xyz_world': np.array([[.1, .1, .9]]), 'source_step': 0}}
    adapter.withdrawal_contact = reference
    calls = []
    original = adapter._cloud_and_ik
    def screen(key=None, *, contact=False):
        calls.append((key, contact))
        return original(key, contact=contact)
    adapter._cloud_and_ik = screen
    for _ in range(2):
        request = adapter.request(k=1)
        scan = next(c for c in request['candidates'] if c['skill'] == 'observe'
            and c['parameters']['mode'] == 'wrist_scan')
        receipt = adapter.execute(request, decision(request, [scan['id']]))[0]
        # This fake scan leaves all entity measurements unchanged, so its
        # semantic receipt may be no_effect despite actual camera motion.
        assert receipt['steps_used'] > 0
        assert calls[-1] == ('e1', True)
        assert adapter.active is adapter.held is None
        assert adapter.withdrawal_contact is reference
        assert not adapter.committed_grasps
        np.testing.assert_array_equal(reference['withdrawal_surface']['xyz_world'], [[.1, .1, .9]])


def test_fixture_search_uses_oblique_contact_when_upright_palm_route_is_blocked(adapter):
    from scipy.spatial.transform import Rotation

    plan = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
        'approach_xyz_m': [.1, -.02, .9], 'width_m': .01}
    def screen(poses):
        closing = Rotation.from_quat(poses[-1]['quat_xyzw']).as_matrix()[:, 0]
        blocked = abs(closing[2]) < .5
        return {'passed': not blocked, 'reason': 'measured_sweep_collision' if blocked else 'clear',
            'collision': blocked, 'ik_reachable': True, 'path_min_clearance_m': 0. if blocked else .01}
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    result = adapter._screen_fixture_approaches(adapter.scene.entities['e1'], plan)
    assert result is not None
    np.testing.assert_allclose(result['xyz_m'], plan['xyz_m'])
    choices = adapter.candidate_diagnostics[-1]
    assert choices['candidates'][choices['selected']]['handle_roll_deg'] == -45
    assert all(c['screen']['collision'] for c in choices['candidates']
        if c['handle_roll_deg'] == 0)


def test_fixture_closure_uses_local_finger_sweeps_instead_of_entire_bar(adapter):
    from scipy.spatial import ConvexHull
    from scipy.spatial.transform import Rotation

    boxes = []
    for name, limits, slide in (
            ('leftfinger', [-.01, 0.], [-1., 0., 0.]),
            ('rightfinger', [0., .01], [1., 0., 0.])):
        corners = np.array([[x, y, z] for x in limits for y in (-.01, .01) for z in (-.02, .01)])
        boxes.append({'name': name, 'slide_per_half_opening': slide,
            'convex_halfspaces': ConvexHull(corners).equations.tolist()})
    adapter.geometry['boxes'] = boxes
    rng = np.random.default_rng(18102026)
    local = np.concatenate([rng.uniform([x, -.1, -.015], [x, .1, .005], (1000, 3))
        for x in (-.015, .015)])
    # An oblique bar's far ends enlarge its global projection but never
    # enter the finite finger footprints. They cannot predict jaw opening.
    ends = rng.uniform([-.08, .06, -.015], [.08, .1, .005], (500, 3))
    orientation = Rotation.from_euler('z', np.pi/2)
    contact = np.array([.1, .1, .9])
    points = np.concatenate([local, ends])+contact
    assert np.ptp(np.quantile(points[:, 0], [.02, .98])) > .08
    measured = adapter._fixture_closure_aperture(points, contact, orientation)
    assert measured['width_m'] == pytest.approx(.03)
    adapter._handle_pixels = lambda measurement: points
    plan = {'xyz_m': contact.tolist(), 'quat_xyzw': orientation.as_quat().tolist(),
        'approach_xyz_m': [.1, -.02, .9], 'width_m': .15}
    selected = adapter._screen_fixture_approaches(adapter.scene.entities['e1'], plan)
    assert selected['width_m'] == pytest.approx(.03)
    assert selected['closure_aperture'] == measured
    # One-sided or missing depth cannot establish bilateral contact width.
    assert adapter._fixture_closure_aperture(local[local[:, 0] > 0]+contact,
        contact, orientation) is None


def test_fixture_oblique_width_is_measured_and_cannot_exceed_gripper_opening(adapter):
    plan = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
        'approach_xyz_m': [.1, -.02, .9], 'width_m': .01}
    # Both projected axes exceed the opening, including the oblique options.
    adapter._handle_pixels = lambda measurement: np.array(
        [[x, y, z] for x in (-.2, 0., .2) for y in (-.2, 0., .2) for z in (-.2, 0., .2)])
    adapter._cloud_and_ik = lambda *args, **kwargs: lambda poses: pytest.fail(
        'wide handle must be rejected before route screening')
    assert adapter._screen_fixture_approaches(adapter.scene.entities['e1'], plan) is None
    assert all(c['screen']['reason'] == 'measured_handle_width_exceeds_opening'
        for c in adapter.candidate_diagnostics[-1]['candidates'])


def test_fixture_approach_keeps_contact_through_occlusion_and_reports_its_original_capture(adapter):
    from dataclasses import replace

    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], name='cabinet')
    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.01, -.01, .003],
        'upper': [.01, .01, .005]} for name in ('leftfinger', 'rightfinger')]
    calls = []
    def measure(*args):
        calls.append(True)
        return {'pose': {'xyz': [.1+.03*(len(calls)-1), .1, .9],
            'approach_normal_xyz': [0., -1., 0.]}}
    adapter.scene.measure_fixture_handle_pose = measure
    first = adapter.request(k=1)
    move = next(c for c in first['candidates'] if c['skill'] == 'move_to')
    adapter._commit_grasp(move)
    contact = adapter.plans['e1']['xyz_m']
    adapter.active = 'e1'
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], source_step=1,
        xyz=(.13, .1, .9))
    second = adapter.request(k=1)
    assert len(calls) == 1 and adapter.plans['e1']['xyz_m'] == contact
    anchor = next(a for a in second['anchors'] if a['id'] == 'e1')
    assert {e['capture_step'] for e in anchor['evidence']} == {0, 1}
    descend = next(c for c in second['candidates'] if c['skill'] == 'descend')
    assert set(descend['consequences']['evidence_ids']) == {
        e['measurement_id'] for e in anchor['evidence']}


def test_fixture_bar_is_clamped_across_its_measured_short_section(adapter, tmp_path):
    from dataclasses import replace

    from scipy.spatial.transform import Rotation

    rng = np.random.default_rng(16102026)
    points = rng.uniform([.02, .095, .895], [.18, .105, .905], (1000, 3))
    path = tmp_path/'bar.npz'
    np.savez(path, points)
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], name='cabinet')
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=2))
    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.01, -.01, .003],
        'upper': [.01, .01, .005]} for name in ('leftfinger', 'rightfinger')]
    handle = {'source_step': 2, 'pose': {'xyz': [.1, .1, .9],
        'approach_normal_xyz': [0., -1., 0.]}, 'views': {'main': {'pose': {'xyz': [.1, .1, .9]}, 'cloud': {
        'path': str(path), 'source': 'perception', 'source_step': 2}}}}
    calls = []
    adapter.scene.measure_fixture_handle_pose = lambda *args: calls.append(True) or handle
    adapter.request(k=4)
    plan = adapter.plans['e1']
    site = Rotation.from_quat(plan['quat_xyzw']).as_matrix()@Rotation.from_euler('z', -np.pi/2).as_matrix()
    assert abs(site[:, 0]@[0., 0., 1.]) > .99
    assert plan['width_m'] < .012
    adapter.committed_grasps['e1'] = {'plan': plan, 'anchor_xyz': np.array([.1, .1, .9])}
    adapter.request(k=4)
    assert len(calls) == 1  # An open approach keeps its chosen measured patch.
    original_obs = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original_obs(), 'robot0_gripper_qpos': [.01, -.01]}
    adapter.request(k=4)
    assert len(calls) == 2  # Once closed, moving fixture geometry is remeasured.


def test_closed_fixture_keeps_contact_identity_when_handle_is_occluded(adapter):
    from dataclasses import replace

    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], name='cabinet top drawer')
    plan = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
        'approach_xyz_m': [.1, -.02, .9], 'width_m': .01,
        'handle_measurement': {'source_step': 0, 'pose': {'xyz': [.1, .1, .9]}}}
    adapter.committed_grasps['e1'] = {'plan': plan, 'anchor_xyz': np.array([.1, .1, .9])}
    adapter.active = 'e1'
    original = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original(), 'robot0_gripper_qpos': [.01, -.01]}
    adapter.scene.measure_fixture_handle_pose = lambda *args: {'pose': None, 'reason': 'occluded'}
    adapter._screen_fixture_approaches = lambda *args: pytest.fail('closed contact must not plan another approach')
    request = adapter.request(k=1)
    assert adapter.plans['e1']['handle_measurement'] == plan['handle_measurement']
    assert any(c['skill'] == 'nudge' and c['parameters'].get('anchor_id') == 'e1'
        for c in request['candidates'])
    assert adapter.candidate_diagnostics[-1]['current_handle_measured'] is False


def test_thin_surface_contact_is_available_without_pretending_opposition(adapter):
    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.01, -.01, .003],
        'upper': [.01, .01, .005]} for name in ('leftfinger', 'rightfinger')]
    y, x = np.mgrid[:20, :20]
    points = np.stack([x.ravel()*.003, y.ravel()*.003, np.full(x.size, .9)], axis=-1)
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    assert plan['contact_kind'] == 'surface' and plan['width_m'] is None
    assert adapter._surface_contact_plan(adapter.scene.entities['e1'],
        np.concatenate([points, points+[0., 0., .08]])) is None


def test_thin_rim_keeps_measured_incline_separate_from_contour_approach(adapter):
    from scipy.spatial.transform import Rotation

    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.002, -.002, .003],
        'upper': [.002, .002, .005]} for name in ('leftfinger', 'rightfinger')]
    radius, angle = np.meshgrid(np.linspace(.03, .05, 25), np.linspace(0., 2*np.pi, 120, endpoint=False))
    points = np.stack([.1+radius.ravel()*np.cos(angle.ravel()),
        .1+radius.ravel()*np.sin(angle.ravel()), .9+.5*(radius.ravel()-.03)], axis=-1)
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    normal = np.asarray(plan['surface_measurement']['normal_xyz'])
    assert .8 < normal[2] < .95
    contact = np.asarray(adapter.candidate_diagnostics[-1]['contact_xyz_m'])
    radial = contact[:2]-[.1, .1]
    # The observed upper face points upward and toward the rim's centre.
    assert normal[:2]@radial < 0
    approach = np.asarray(plan['contact_approach_xyz'])
    assert approach[:2]@radial > 0
    assert approach[2] == pytest.approx(.5)
    assert plan['approach_basis'] == 'measured_contour_fixed_incline'
    rotation = Rotation.from_quat(plan['quat_xyzw']).as_matrix()
    np.testing.assert_allclose(rotation[:, 2], -approach, atol=1e-12)
    np.testing.assert_allclose(np.asarray(plan['approach_xyz_m'])-plan['xyz_m'], approach*.12)
    assert plan['width_m'] is None


def test_contact_descent_follows_the_screened_guide_instead_of_a_new_straight_line(adapter):
    route = [{'xyz_m': [.08, .09, .95], 'quat_xyzw': [0., 0., 0., 1.]},
             {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.]}]
    adapter.plans['e1'] = {'xyz_m': route[-1]['xyz_m'],
        'quat_xyzw': route[-1]['quat_xyzw'], 'contact_route': route}
    result = adapter._route('descend', {'anchor_id': 'e1'})
    assert result == route
    result[0]['xyz_m'][0] = 99.
    assert adapter.plans['e1']['contact_route'][0]['xyz_m'][0] == .08


def test_surface_contact_can_select_a_clear_wrist_orientation(adapter):
    from scipy.spatial.transform import Rotation

    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.01, -.01, .003],
        'upper': [.01, .01, .005]} for name in ('leftfinger', 'rightfinger')]
    y, x = np.mgrid[:20, :20]
    points = np.stack([x.ravel()*.003, y.ravel()*.003, np.full(x.size, .9)], axis=-1)
    checks = []
    def screen(poses):
        checks.append(poses)
        passed = len(checks) > 1
        return {'passed': passed, 'reason': 'clear' if passed else 'measured_sweep_collision',
            'collision': not passed, 'ik_reachable': True, 'path_min_clearance_m': .02 if passed else 0.}
    screen.points = screen.target = np.empty((0, 3))
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    assert len(checks) >= 2
    # Directional rim alternatives are screened after the default plan. Its
    # first rejected and second clear wrist must still determine that plan.
    default_route = checks[1]
    # SmoothMotion may choose the equivalent antipodal quaternion for continuity.
    difference = Rotation.from_quat(plan['quat_xyzw'])*Rotation.from_quat(default_route[-1]['quat_xyzw']).inv()
    assert difference.magnitude() < 1e-12
    np.testing.assert_allclose(plan['xyz_m'], default_route[-1]['xyz_m'], atol=1e-12)
    assert adapter.candidate_diagnostics[-1]['candidates'][0]['screen']['collision'] is True


def test_panel_contact_prefers_terminal_joint_room_without_accepting_a_blocked_route(adapter):
    from scipy.spatial.transform import Rotation

    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.002, -.002, .003],
        'upper': [.002, .002, .005]} for name in ('leftfinger', 'rightfinger')]
    y, z = np.mgrid[:20, :20]
    points = np.stack([np.full(y.size, .1), y.ravel()*.003, .9+z.ravel()*.003], axis=-1)
    checked = []
    def screen(poses):
        index = len(checked)
        checked.append(poses)
        passed = index != 2
        margin = .3 if index == 1 else .9 if not passed else 1e-6
        return {'passed': passed, 'reason': 'clear' if passed else 'measured_sweep_collision',
            'collision': not passed, 'ik_reachable': True, 'path_min_clearance_m': .02,
            'ik_checks': [{'solves': [{'solution_found': True, 'joint_margin_min_rad': margin}]}]}
    screen.points = screen.target = np.empty((0, 3))
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    assert len(checked) == 16
    desired = checked[1][-1]
    np.testing.assert_allclose(plan['xyz_m'], desired['xyz_m'])
    assert (Rotation.from_quat(plan['quat_xyzw'])*Rotation.from_quat(desired['quat_xyzw']).inv()).magnitude() < 1e-12
    options = adapter.candidate_diagnostics[-1]['candidates']
    assert plan['approach_route'] == options[1]['route'][:-1]
    assert options[0]['screen']['passed']
    assert options[1]['screen']['contact_joint_margin_rad'] == .3
    assert options[2]['screen']['collision']


def test_surface_contact_rejects_neighbour_hit_only_during_closure(adapter):
    from scipy.spatial.transform import Rotation

    from robots.libero.v5_geometric_grasp import collision_counts

    adapter.geometry['boxes'] = [
        {'name': 'leftfinger_pad', 'lower': [-.001, -.001, .003],
         'upper': [.001, .001, .005], 'slide_per_half_opening': [1., 0., 0.]},
        {'name': 'rightfinger_pad', 'lower': [-.001, -.001, .003],
         'upper': [.001, .001, .005], 'slide_per_half_opening': [-1., 0., 0.]}]
    y, x = np.mgrid[:20, :20]
    points = np.stack([x.ravel()*.003, y.ravel()*.003, np.full(x.size, .9)], axis=-1)
    original = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    site = Rotation.from_quat(original['quat_xyzw']).as_matrix()@Rotation.from_euler('z', -np.pi/2).as_matrix()
    obstacle = np.array([np.asarray(original['xyz_m'])+site@[.02, 0., .004]])
    for opening in (.08, 0.):
        assert not any(collision_counts(obstacle, original['xyz_m'], site,
            adapter.geometry, opening, clearance_m=.004).values())
    screen = adapter._cloud_and_ik()
    screen.points = obstacle
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    first = adapter.candidate_diagnostics[-1]['candidates'][0]
    assert first['screen'] is None and first['closure']['scene']['leftfinger_pad']
    assert plan is not None
    assert not np.allclose(plan['quat_xyzw'], original['quat_xyzw'])


def test_thin_surface_uses_another_measured_patch_when_nearest_rim_is_blocked(adapter):
    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.001, -.001, .003],
        'upper': [.001, .001, .005], 'slide_per_half_opening': [sign, 0., 0.]}
        for name, sign in [('leftfinger', 1.), ('rightfinger', -1.)]]
    y, x = np.mgrid[:20, :20]
    points = np.stack([x.ravel()*.003, y.ravel()*.003, np.full(x.size, .9)], axis=-1)
    original = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    first_contact = adapter.candidate_diagnostics[-1]['contact_xyz_m']
    screen = adapter._cloud_and_ik()
    screen.points = np.array([np.asarray(first_contact)+[0., 0., .001]])
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    report = adapter.candidate_diagnostics[-1]
    assert plan is not None
    assert np.linalg.norm(np.array(report['contact_xyz_m'])-first_contact) >= .01
    # Oblique routes across the contour are ranked before top-face fallbacks.
    # Unvisited fallback poses make no collision claim; every screened pose
    # at the obstructed preferred patch must still have been rejected.
    attempted = [c for c in report['candidates'] if c['patch_index'] == 0
        and (c.get('closure') or c.get('screen') is not None)]
    assert attempted and all(c.get('closure') or not c['screen']['passed'] for c in attempted)
    assert not np.allclose(original['xyz_m'], plan['xyz_m'])
    assert any(np.allclose(report['contact_xyz_m'], p) for p in report['contact_patches_xyz_m'])


def test_thin_surface_contact_keeps_finger_tip_above_support(adapter):
    from scipy.spatial.transform import Rotation

    adapter.geometry['boxes'] = [
        {'name': 'leftfinger_pad', 'lower': [-.01, -.01, .003], 'upper': [.01, .01, .005]},
        {'name': 'rightfinger_pad', 'lower': [-.01, -.01, .003], 'upper': [.01, .01, .005]},
        {'name': 'leftfinger', 'lower': [-.01, -.01, -.02], 'upper': [.01, .01, .017]},
        {'name': 'rightfinger', 'lower': [-.01, -.01, -.02], 'upper': [.01, .01, .017]}]
    y, x = np.mgrid[:20, :20]
    points = np.stack([x.ravel()*.003, y.ravel()*.003, np.full(x.size, .9)], axis=-1)
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    site = Rotation.from_quat(plan['quat_xyzw']).as_matrix()@Rotation.from_euler('z', -np.pi/2).as_matrix()
    tip_world = np.asarray(plan['xyz_m'])+site@[0., 0., .017]
    assert tip_world[2] == pytest.approx(.9)
    pad_world = np.asarray(plan['xyz_m'])+site@[0., 0., .004]
    assert pad_world[2] > .9
    assert plan['contact_kind'] == 'surface' and plan['width_m'] is None


def test_contour_approach_does_not_invent_a_side_surface_and_keeps_screened_top_fallback(adapter):
    from scipy.spatial.transform import Rotation

    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.001, -.001, .003],
        'upper': [.001, .001, .005]} for name in ('leftfinger', 'rightfinger')]
    y, x = np.mgrid[:20, :20]
    points = np.stack([x.ravel()*.003, y.ravel()*.003, np.full(x.size, .9)], axis=-1)
    checked = []
    def screen(poses):
        direction = -Rotation.from_quat(poses[-1]['quat_xyzw']).as_matrix()[:, 2]
        passed = direction[2] > .99
        checked.append((direction, passed))
        return {'passed': passed, 'reason': 'clear' if passed else 'measured_sweep_collision',
            'collision': not passed, 'ik_reachable': True, 'path_min_clearance_m': .01 if passed else 0.}
    screen.points = screen.target = np.empty((0, 3))
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    assert any(not passed and direction[2] < .9 for direction, passed in checked)
    assert plan['approach_basis'] == 'measured_surface_normal'
    np.testing.assert_allclose(plan['surface_measurement']['normal_xyz'], [0., 0., 1.], atol=1e-12)
    np.testing.assert_allclose(plan['contact_approach_xyz'], [0., 0., 1.], atol=1e-12)
    assert plan['width_m'] is None


@pytest.mark.parametrize('parent_x', [.3, 0.])
@pytest.mark.parametrize('handle_blocked', [False, True])
def test_measured_vertical_panel_offers_screened_contact_from_hand_side(adapter, parent_x, handle_blocked):
    from robots.libero.bounded_oracle import BoundedOracle

    adapter.scene.entities.clear()
    parent = Entity('e2', 'microwave', (parent_x, .2, 1.), (.2, .1, .9), (.4, .3, 1.1), True, 0)
    door = Entity('e3', 'microwave door', (.1, .2, 1.), (.099, .1, .9), (.101, .3, 1.1),
                  True, 0, part_of=parent.id)
    adapter.scene.entities.update({parent.id: parent, door.id: door})
    y, z = np.mgrid[:20, :20]
    points = np.stack([np.full(y.size, .1), .1+y.ravel()*.008, .9+z.ravel()*.008], axis=-1)
    adapter.scene.measurement_clouds[door.id] = points
    adapter.scene.measure_fixture_handle_pose = lambda *args: {'pose': {
        'xyz': [.1, .2, 1.], 'approach_normal_xyz': [-1., 0., 0.]
    } if handle_blocked else None}
    handle_checks = []
    def blocked_handle(entity, plan):
        handle_checks.append(entity.id)
        return None
    adapter._screen_fixture_approaches = blocked_handle
    adapter._handle_pixels = lambda handle: np.empty((0, 3))
    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.01, -.01, .003],
        'upper': [.01, .01, .005]} for name in ('leftfinger', 'rightfinger')]
    adapter._instance_pixels = lambda key: points if key == door.id else np.empty((0, 3))
    request = adapter.request(k=1)
    plan = adapter.plans[door.id]
    assert bool(handle_checks) == handle_blocked
    np.testing.assert_allclose(plan['surface_measurement']['normal_xyz'], [-1., 0., 0.], atol=1e-12)
    assert plan['contact_kind'] == 'surface' and plan['width_m'] is None
    assert plan['approach_xyz_m'][0] < plan['xyz_m'][0]
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: {
        'done': False, 'goals': [['close', 'microwave_1']], 'satisfied': [False]}), adapter)
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['parameters']['anchor_id'] == door.id
    assert chosen['parameters']['path'] == plan['preferred_path'] == 'direct'
    route = adapter._route('move_to', chosen['parameters'])
    assert len(route) == 1
    np.testing.assert_allclose(route[-1]['xyz_m'], plan['approach_xyz_m'])
    adapter.p.env.raw_obs = lambda: {'robot0_eef_pos': plan['xyz_m'],
        'robot0_eef_quat': plan['quat_xyzw'], 'robot0_gripper_qpos': [.01, -.01],
        'robot0_joint_pos': np.zeros(7)}
    adapter.active = door.id
    request = adapter.request(k=1)
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['skill'] == 'nudge'
    assert chosen['parameters']['axis'] == 'x' and chosen['parameters']['distance_m'] > 0


@pytest.mark.parametrize('capture', ['fresh', 'recessed_panel', 'stale', 'occluded', 'thin_handle'])
def test_committed_panel_direction_uses_only_a_fresh_measured_plane(adapter, capture):
    from dataclasses import replace

    from scipy.spatial.transform import Rotation

    entity = replace(adapter.scene.entities['e1'], name='microwave door',
                     visible=capture != 'occluded', source_step=3 if capture == 'stale' else 4)
    adapter.scene.entities['e1'] = entity
    y, z = np.mgrid[:20, :20]
    patch = np.stack([np.zeros(y.size), (y.ravel()-10)*.008, (z.ravel()-10)*.008], axis=-1)
    if capture == 'thin_handle':
        patch[:, 1] *= .05
    elif capture == 'recessed_panel':
        patch = np.concatenate([patch+[depth, 0., 0.] for depth in (-.0115, 0., .0115)])
    rotation = Rotation.from_euler('z', 40, degrees=True)
    adapter.scene.measurement_clouds['e1'] = rotation.apply(patch)+[.1, .1, .9]
    adapter.ex.toolkit._state.latest_step = 4
    adapter.active = 'e1'
    adapter.p.env.position[:] = entity.xyz
    raw = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**raw(), 'robot0_gripper_qpos': [.01, -.01]}
    adapter.scene.measure_fixture_handle_pose = lambda *args: {'pose': None}
    original_surface = {'xyz_world': patch.tolist(), 'source_step': 0, 'normal_xyz': [-1., 0., 0.]}
    plan = {'xyz_m': list(entity.xyz), 'quat_xyzw': [0., 0., 0., 1.], 'width_m': None,
            'contact_kind': 'surface', 'surface_measurement': original_surface}
    adapter.committed_grasps['e1'] = {'plan': plan, 'anchor_xyz': np.asarray(entity.xyz)}
    adapter.request(k=1)
    measured = adapter.plans['e1']['surface_measurement']
    measured_plane = capture in {'fresh', 'recessed_panel'}
    expected = rotation.apply([-1., 0., 0.]) if measured_plane else [-1., 0., 0.]
    np.testing.assert_allclose(measured['normal_xyz'], expected, atol=1e-12)
    assert measured.get('normal_source_step') == (4 if measured_plane else None)
    assert measured['source_step'] == 0
    assert measured['xyz_world'] == original_surface['xyz_world']
    assert original_surface['normal_xyz'] == [-1., 0., 0.]
    if measured_plane:
        # A later occlusion keeps the last measured direction and its age;
        # it must not restore the initial committed contact normal.
        adapter.scene.entities['e1'] = replace(entity, visible=False)
        adapter.ex.toolkit._state.latest_step = 5
        adapter.request(k=1)
        cached = adapter.plans['e1']['surface_measurement']
        np.testing.assert_allclose(cached['normal_xyz'], expected, atol=1e-12)
        assert cached['normal_source_step'] == 4
        assert cached['source_step'] == 0
        assert original_surface['normal_xyz'] == [-1., 0., 0.]


def test_surface_contact_screens_symmetric_wrist_instead_of_discarding_it(adapter):
    from scipy.spatial.transform import Rotation

    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.01, -.01, .003],
        'upper': [.01, .01, .005]} for name in ('leftfinger', 'rightfinger')]
    y, x = np.mgrid[:20, :20]
    points = np.stack([x.ravel()*.003, y.ravel()*.003, np.full(x.size, .9)], axis=-1)
    # The nearest symmetric orientation is rejected by IK. The opposing
    # closing-axis orientation remains a distinct executable wrist pose.
    nearest = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    close_axis = Rotation.from_quat(nearest['quat_xyzw']).as_matrix()[:, 1]
    checks = []
    screened_poses = []
    def screen(poses):
        axis = Rotation.from_quat(poses[-1]['quat_xyzw']).as_matrix()[:, 1]
        passed = np.dot(axis, close_axis) < -.99
        checks.append(passed)
        screened_poses.append(poses[-1])
        return {'passed': passed, 'reason': 'clear' if passed else 'numerical_ik_not_found',
            'collision': False, 'ik_reachable': passed, 'path_min_clearance_m': .02}
    screen.points = screen.target = np.empty((0, 3))
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    assert plan is not None
    selected_index = next(i for i, pose in enumerate(screened_poses)
        if np.allclose(plan['xyz_m'], pose['xyz_m'], atol=1e-12)
        and (Rotation.from_quat(plan['quat_xyzw'])*Rotation.from_quat(pose['quat_xyzw']).inv()).magnitude() < 1e-12)
    assert selected_index > 0 and checks[selected_index] and not any(checks[:selected_index])
    selected_axis = Rotation.from_quat(plan['quat_xyzw']).as_matrix()[:, 1]
    assert np.dot(selected_axis, close_axis) < -.99


def test_private_push_selector_uses_public_target_direction_and_bounded_nudge(adapter):
    from robots.libero.bounded_oracle import BoundedOracle

    adapter.ex.instruction = 'push the box onto the plate'
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.3, .1, .9), (.25, .05, .89), (.35, .15, .91), True, 0)
    original_obs = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original_obs(), 'robot0_gripper_qpos': [.01, -.01]}
    adapter.active = 'e1'
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: {
        'done': False, 'goals': [['on', 'box_1', 'plate_1']], 'satisfied': [False]}), adapter)
    request = adapter.request(k=1)
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['skill'] == 'nudge'
    assert chosen['parameters'] == {'axis': 'x', 'distance_m': .02, 'anchor_id': 'e1'}


@pytest.mark.parametrize('predicate,sign', [('open', 1.), ('close', -1.)])
def test_private_fixture_selector_uses_shorter_screened_nudge(adapter, predicate, sign):
    from robots.libero.bounded_oracle import BoundedOracle

    original_obs = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original_obs(), 'robot0_gripper_qpos': [.01, -.01]}
    adapter.active = 'e1'
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: {
        'done': False, 'goals': [[predicate, 'wooden_cabinet_1_top_region']],
        'satisfied': [False]}), adapter)
    oracle.binding.bind = lambda *args, **kwargs: adapter.scene.entities['e1']
    request = adapter.request(k=1)
    adapter.plans['e1']['handle_measurement'] = {'pose': {'approach_normal_xyz': [0., 1., 0.]}}
    for candidate in request['candidates']:
        if candidate['skill'] == 'nudge' and candidate['parameters']['axis'] == 'y':
            candidate['consequences']['collision'] = candidate['parameters']['distance_m'] != .01*sign
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['skill'] == 'nudge'
    assert chosen['parameters'] == {'axis': 'y', 'distance_m': .01*sign, 'anchor_id': 'e1'}
    # A blocked pull releases the old contact through an existing option.
    # It does not invent an unchecked motion or scan with closed fingers.
    chosen['consequences']['collision'] = True
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['skill'] == 'set_gripper' and chosen['parameters']['mode'] == 'open'
    request['candidates'].remove(chosen)
    assert selected(request, oracle.choose(request))[0]['skill'] == 'observe'


@pytest.mark.parametrize('secondary', [.53, .01])
def test_private_fixture_selector_tries_measured_secondary_axis_before_release(adapter, secondary):
    from robots.libero.bounded_oracle import BoundedOracle

    original_obs = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original_obs(), 'robot0_gripper_qpos': [.01, -.01]}
    adapter.active = 'e1'
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: {
        'done': False, 'goals': [['close', 'microwave_1']], 'satisfied': [False]}), adapter)
    oracle.binding.bind = lambda *args, **kwargs: adapter.scene.entities['e1']
    request = adapter.request(k=1)
    adapter.plans['e1']['surface_measurement'] = {'normal_xyz': [-.85, -secondary, -.001]}
    for candidate in request['candidates']:
        if candidate['skill'] == 'nudge':
            candidate['consequences']['collision'] = not (
                candidate['parameters']['axis'] == 'y' and candidate['parameters']['distance_m'] == .01)
    chosen = selected(request, oracle.choose(request))[0]
    if secondary == .53:
        assert chosen['skill'] == 'nudge'
        assert chosen['parameters'] == {'axis': 'y', 'distance_m': .01, 'anchor_id': 'e1'}
    else:
        assert chosen['skill'] == 'set_gripper' and chosen['parameters']['mode'] == 'open'


@pytest.mark.parametrize('predicate,direction', [('turnon', 1), ('turnoff', -1)])
@pytest.mark.parametrize('wrist_flip', [False, True])
def test_private_rotary_selector_converts_outward_turn_to_local_wrist_axis(
        adapter, predicate, direction, wrist_flip):
    from scipy.spatial.transform import Rotation

    from robots.libero.bounded_oracle import BoundedOracle

    original_obs = adapter.p.env.raw_obs
    quat = Rotation.from_euler('x', 180 if wrist_flip else 0, degrees=True).as_quat()
    adapter.p.env.raw_obs = lambda: {**original_obs(),
        'robot0_gripper_qpos': [.01, -.01], 'robot0_eef_quat': quat}
    adapter.active = 'e1'
    oracle = BoundedOracle(SimpleNamespace(call=lambda _: {
        'done': False, 'goals': [[predicate, 'flat_stove_1']], 'satisfied': [False]}), adapter)
    oracle.binding.bind = lambda *args, **kwargs: adapter.scene.entities['e1']
    request = adapter.request(k=1)
    adapter.plans['e1']['handle_measurement'] = {'pose': {'approach_normal_xyz': [0., 0., 1.]}}
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['skill'] == 'rotate_wrist'
    expected = 45*direction*(-1 if wrist_flip else 1)
    assert chosen['parameters'] == {'angle_deg': expected, 'anchor_id': 'e1'}

    # Release an obstructed rotary contact before attempting a new view.
    # The original run instead scanned with closed fingers and got stuck.
    for candidate in request['candidates']:
        if candidate['skill'] == 'rotate_wrist':
            candidate['consequences']['collision'] = True
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['skill'] == 'set_gripper' and chosen['parameters']['mode'] == 'open'


def test_gripper_can_precede_a_measured_suffix(adapter):
    request = adapter.request(k=4)
    close = next(c for c in request["candidates"] if c["skill"] == "set_gripper" and c["parameters"]["mode"] == "close")
    observe = next(c for c in request["candidates"] if c["skill"] == "observe")
    assert [c['skill'] for c in selected(request, decision(request, [close['id'], observe['id']]))] == ['set_gripper', 'observe']
    with pytest.raises(ValueError, match='boundary'):
        selected(request, decision(request, [observe['id'], close['id']]))


@pytest.mark.parametrize('skill', ['nudge', 'rotate_wrist'])
def test_anchored_motion_allows_suffix_but_keeps_contact_measurement_off_async_worker(adapter, monkeypatch, skill):
    adapter.active = 'e1'
    request = adapter.request(k=4)
    contact = next(c for c in request['candidates'] if c['skill'] == skill
        and c['parameters'].get('anchor_id') == 'e1')
    observe = next(c for c in request['candidates'] if c['skill'] == 'observe')
    assert len(selected(request, decision(request, [contact['id'], observe['id']]))) == 2
    lookaheads = []
    def execute_motion(*args, **kwargs):
        lookaheads.append(kwargs.get('lookahead'))
        return {'executed': True, 'stop_reason': 'endpoint', 'endpoint_error_m': 0.}
    monkeypatch.setattr('robots.libero.bounded_skills.SmoothMotion.run', execute_motion)
    adapter.execute(request, decision(request, [contact['id']]), async_decisions=object())
    assert lookaheads == [None]
    assert adapter._last_free_chunk is None


def test_k4_motion_prefix_is_actually_blended(adapter):
    request = adapter.request(k=4)
    moves = [next(c for c in request["candidates"] if c["skill"] == "nudge" and c["parameters"] == {"axis": axis, "distance_m": .01}) for axis in ("x", "y")]
    adapter.execute(request, decision(request, [c["id"] for c in moves]))
    assert adapter.details[-1]["blended"]
    assert len(adapter.details[-1]["candidate_ids"]) == 2
    np.testing.assert_allclose(adapter.robot()["eef_xyz_m"], [.01, .01, 1.], atol=1e-8)


def test_k4_descend_is_a_measured_checkpoint_and_publishes_active(adapter, monkeypatch):
    blended = []
    original = adapter._execute_motion_group
    def trace_group(request, candidates, **kwargs):
        blended.append([c['skill'] for c in candidates])
        return original(request, candidates, **kwargs)
    monkeypatch.setattr(adapter, '_execute_motion_group', trace_group)
    request = adapter.request(k=4)
    prefix = [next(c for c in request["candidates"]
        if c["skill"] == skill and c["parameters"].get("anchor_id") == "e1")
        for skill in ("move_to", "align", "descend")]
    receipts = adapter.execute(request, decision(request, [c["id"] for c in prefix]))
    assert [r["outcome"] for r in receipts] == ["success", "success", "success"]
    assert adapter.active == "e1"
    assert blended == [['move_to', 'align']]


def test_k4_fixed_position_rotation_passages_use_time_and_measured_angle(adapter):
    from scipy.spatial.transform import Rotation

    p = adapter.p
    p.env.quat = np.array([0., 0., 0., 1.])
    original_obs = p.env.raw_obs
    p.env.raw_obs = lambda: {**original_obs(), 'robot0_eef_quat': p.env.quat}
    def step(action):
        p.actions.append(action)
        p.env.position += action[:3]*.05
        p.env.quat = (Rotation.from_rotvec(action[3:6]*.5)*Rotation.from_quat(p.env.quat)).as_quat()
    p._step_env = step
    request = adapter.request(k=4)
    turns = [next(c for c in request['candidates'] if c['skill'] == 'rotate_wrist'
        and c['parameters']['angle_deg'] == angle) for angle in (45, 90)]
    receipts = adapter.execute(request, decision(request, [c['id'] for c in turns]))
    assert [r['outcome'] for r in receipts] == ['success', 'success']
    assert all(r['steps_used'] > 0 for r in receipts)


def test_k4_stalled_rotation_is_not_reported_success_from_position_alone(adapter):
    request = adapter.request(k=4)
    turns = [next(c for c in request['candidates'] if c['skill'] == 'rotate_wrist'
        and c['parameters']['angle_deg'] == angle) for angle in (45, 90)]
    receipts = adapter.execute(request, decision(request, [c['id'] for c in turns]))
    assert len(receipts) == 1  # Fail the first turn before executing its suffix.
    assert receipts[0]['outcome'] == 'failure' and receipts[0]['stop_reason'] == 'angular_waypoint_not_reached'


def test_held_payload_skips_unused_contact_search_and_keeps_carry_options(adapter):
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.3, .1, .9), (.25, .05, .89), (.35, .15, .91), True, 0)
    adapter.held = 'e1'
    adapter.grasp_geometry = lambda e: pytest.fail('held request has no new grasp candidates')
    request = adapter.request(k=4)
    assert any(c['skill'] == 'carry_to' and c['parameters']['target_id'] == 'e2' for c in request['candidates'])
    assert not any(c['skill'] in {'move_to', 'align', 'descend'} for c in request['candidates'])


def test_lift_keeps_selected_finger_contact_allowed(adapter):
    seen = []
    def screen(anchor=None, *, contact=False):
        seen.append((anchor, contact))
        return lambda poses: {"passed": contact, "reason": "test_selected_contact",
            "collision": not contact, "ik_reachable": True, "path_min_clearance_m": .01}
    adapter._cloud_and_ik = screen
    adapter.active = "e1"
    request = adapter.request(k=1)
    lift = next(c for c in request["candidates"] if c["skill"] == "lift")
    assert lift["consequences"]["collision"] is False
    assert ("e1", True) in seen


def test_rejected_wrist_scan_is_a_failure(adapter):
    request = adapter.request(k=1)
    adapter._cloud_and_ik = lambda *args, **kwargs: lambda poses: {
        "passed": False, "reason": "measured_sweep_collision"}
    scan = next(c for c in request["candidates"] if c["skill"] == "observe" and c["parameters"]["mode"] == "wrist_scan")
    receipt = adapter.execute(request, decision(request, [scan["id"]]))[0]
    assert receipt["outcome"] == "failure"
    assert receipt["phase"] == "collision"
    assert receipt["steps_used"] == 0


@pytest.mark.parametrize('mode,held,blocked,retained', [
    ('wrist_scan', None, False, False), ('wrist_scan', 'e1', False, True),
    ('refresh', None, False, True), ('wrist_scan', None, True, True)])
def test_scan_withdrawal_clears_only_unverified_contact(adapter, mode, held, blocked, retained):
    adapter.active, adapter.held = 'e1', held
    adapter.grasp_reference = (adapter.scene.entities['e1'], np.zeros(3))
    request = adapter.request(k=1)
    if blocked:
        adapter._cloud_and_ik = lambda *args, **kwargs: lambda poses: {
            'passed': False, 'reason': 'measured_sweep_collision'}
    scan = next(c for c in request['candidates'] if c['skill'] == 'observe'
        and c['parameters']['mode'] == mode)
    adapter.execute(request, decision(request, [scan['id']]))
    assert (adapter.active == 'e1') is retained
    assert (adapter.grasp_reference is not None) is retained
    assert adapter.held == held


@pytest.mark.parametrize('native_success', [False, True])
def test_native_task_stop_is_success_but_truncation_is_not(adapter, monkeypatch, native_success):
    request = adapter.request(k=1)
    turn = next(c for c in request['candidates'] if c['skill'] == 'rotate_wrist')
    def interrupted(*args, **kwargs):
        adapter.p.env.terminated = native_success
        adapter.p.env.truncated = not native_success
        return {'executed': True, 'steps_used': 1, 'stop_reason': 'native_stop',
            'endpoint_error_m': .04, 'trace': []}
    monkeypatch.setattr('robots.libero.bounded_skills.SmoothMotion.run', interrupted)
    receipt = adapter.execute(request, decision(request, [turn['id']]))[0]
    assert receipt['outcome'] == ('success' if native_success else 'failure')
    assert receipt['stop_reason'] == ('native_success' if native_success else 'native_stop')
    assert (receipt['phase'] is None) is native_success


@pytest.mark.parametrize('native_success', [False, True])
@pytest.mark.parametrize('blended', [False, True])
def test_native_stop_never_records_unexecuted_chunk_suffix(adapter, monkeypatch, native_success, blended):
    from robots.libero.bounded_motion import measured_robot

    request = adapter.request(k=4)
    first = next(c for c in request['candidates'] if c['skill'] == 'nudge')
    second = next(c for c in request['candidates']
        if c['skill'] == ('rotate_wrist' if blended else 'descend'))
    def interrupted(*args, **kwargs):
        before = measured_robot(adapter.p)
        adapter.p._step_env(np.zeros(7))
        adapter.p.env.terminated = native_success
        adapter.p.env.truncated = not native_success
        return {'executed': True, 'steps_used': 1, 'stop_reason': 'native_stop',
            'endpoint_error_m': .04, 'waypoint_times_s': [.5, 1.],
            'trace': [{'time_s': .05, 'before': before, 'after': measured_robot(adapter.p)}]}
    monkeypatch.setattr('robots.libero.bounded_skills.SmoothMotion.run', interrupted)
    receipts = adapter.execute(request, decision(request, [first['id'], second['id']]))
    assert len(receipts) == 1 and receipts[0]['candidate_id'] == first['id']
    assert receipts[0]['outcome'] == ('success' if native_success else 'failure')
    assert receipts[0]['steps_used'] == 1


def test_wrist_scan_reference_endpoint_does_not_imply_measured_arrival(adapter, monkeypatch):
    request = adapter.request(k=1)
    monkeypatch.setattr('robots.libero.bounded_skills.SmoothMotion.run', lambda *args, **kwargs: {
        'executed': True, 'stop_reason': 'endpoint', 'endpoint_error_m': .0256})
    scan = next(c for c in request['candidates'] if c['skill'] == 'observe'
        and c['parameters']['mode'] == 'wrist_scan')
    receipt = adapter.execute(request, decision(request, [scan['id']]))[0]
    assert receipt['outcome'] == 'failure'
    assert receipt['stop_reason'] == 'scan_waypoint_not_reached'
    assert receipt['phase'] == 'planning_unreachable'


def test_target_mask_uses_same_public_self_filter_as_scene(adapter, monkeypatch):
    target = np.array([[.1, .1, .9], [0., 0., 1.]])
    adapter.scene.measurement_clouds['e1'] = target
    ik = SimpleNamespace(remove_measured_arm=lambda points: (points, 0))
    adapter._base_geometry = (np.array([[.3, .3, .9]]), ik)
    calls = []
    def hand_filter(points, *args):
        calls.append(np.array(points))
        return points[:1], len(points)-1
    monkeypatch.setattr('robots.libero.bounded_skills.remove_current_gripper', hand_filter)
    monkeypatch.setattr('robots.libero.bounded_skills.remove_visual_robot', lambda points, ik: (points, {}))
    monkeypatch.setattr('robots.libero.bounded_skills.PublicRouteScreen', lambda scene, geometry, ik, **kwargs: kwargs)
    # Use the real method, rather than this fixture's no-collision stub.
    screen = MeasuredSkillAdapter._cloud_and_ik(adapter, 'e1', contact=True)
    assert len(calls) == 1
    assert len(screen['contact_points']) == 1
    np.testing.assert_allclose(screen['contact_points'][0], target[0])


def test_instance_boundary_recovers_continuous_rim_but_keeps_depth_jump(adapter):
    yy, xx = np.mgrid[:9, :12]
    world = np.stack([.1+xx*.001, .1+yy*.001, np.full(xx.shape, .9)], axis=-1)
    world[:, 10:, 2] += .005  # A nearby external surface is not a target rim.
    points = world[:, :8].reshape(-1, 3)
    adapter.scene.measurement_clouds_by_view = {'e1': {'agentview': {
        'source_step': 0, 'xyz_world': points}}}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=0,
        load=lambda name: world if name.startswith('agentview') else np.full_like(world, np.nan)))
    completed = adapter._instance_pixels('e1')
    assert len(completed) == 9*10
    assert np.allclose(completed[:, 2], .9)
    assert adapter.instance_boundary_evidence['e1'][0]['added_pixels_per_round'] == [9, 9, 0]
    assert adapter.instance_boundary_evidence['e1'][0]['local_plane']['version'] == 'public-local-plane-instance-boundary/1-dev'


def test_uncontacted_instance_recovers_curved_seam_without_owning_table_or_neighbour(adapter):
    from dataclasses import replace

    yy, xx = np.mgrid[:22, :28]
    world = np.stack([.1+xx*.001, .1+yy*.001, .9+.0015*(xx % 2)], axis=-1)
    world[:, 24:, 2] += .01  # Separate nearby object, even inside the image crop.
    world[20:, :, 2] = .88  # Table pixels included in the raw semantic mask.
    mask = (xx < 22) & ~((xx >= 6) & (xx <= 16) & (yy >= 5) & (yy <= 15))
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'],
        xyz=(.111, .11, .9), lower=(.1, .1, .899), upper=(.122, .12, .903))
    adapter.scene.measurement_clouds_by_view = {'e1': {'agentview': {
        'source_step': 0, 'xyz_world': world[mask]}}}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=0,
        load=lambda name: world if name.startswith('agentview') else np.full_like(world, np.nan)))
    assert adapter.active is None and adapter.held is None
    completed = adapter._instance_pixels('e1')
    assert np.linalg.norm(completed-world[10, 11], axis=1).min() < 1e-9
    assert completed[:, 2].min() >= .9
    assert completed[:, 0].max() < .124
    detail = adapter.instance_boundary_evidence['e1'][0]
    assert detail['connected_surface']['added_pixels'] > 0
    assert any(c.get('rejected') == 'outside_stationary_measured_identity'
               for c in detail['held_component']['components'])


def test_two_current_views_recover_occluded_connected_rim_without_owning_depth_gap(adapter, monkeypatch):
    from dataclasses import replace

    yy, xx = np.mgrid[:24, :40]
    world = np.stack([.1+xx*.001, .1+yy*.001, .9+.0008*(xx+yy)], axis=-1)
    world[12:16, 20:24, 2] -= .006  # Neighbour lies inside the combined extent.
    main = world.copy()
    main[8:] = np.nan  # The rim below this occlusion has no opposite projection.
    main_mask = (yy < 6) & (xx < 31)
    wrist_mask = xx < 6
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'],
        xyz=(.115, .11, .915), lower=(.1, .1, .89), upper=(.14, .13, .94))
    adapter.scene.measurement_clouds_by_view = {'e1': {
        'agentview': {'source_step': 0, 'xyz_world': main[main_mask]},
        'wrist': {'source_step': 0, 'xyz_world': world[wrist_mask]}}}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=0,
        load=lambda name: {} if name.endswith('.json') else main if name.startswith('agentview') else world))
    # Test depth-supported ownership when the calibrated opposite-view
    # projection contributes no additional pixels behind the occlusion.
    monkeypatch.setattr('robots.libero.bounded_skills.complete_crossview_boundary',
        lambda world, mask, *args, **kwargs: (mask.copy(), {}))
    completed = adapter._instance_pixels('e1')
    assert np.linalg.norm(completed-world[18, 14], axis=1).min() < 1e-9
    assert np.linalg.norm(completed-world[13, 21], axis=1).min() > .003
    assert np.linalg.norm(completed-world[10, 38], axis=1).min() > .003


def test_scene_instance_subtraction_precedes_voxel_centroids(adapter, monkeypatch):
    adapter.geometry['site_offset_in_gripper_m'] = [0., 0., 0.]
    target = np.array([[.1001, .1, .9], [.1009, .1, .9]])
    held = np.array([[.2001, .1, .9], [.2009, .1, .9]])
    obstacle = np.array([[.1019, .1, .9]])  # Same voxel; not the same instance pixel.
    world = np.concatenate([target, held, obstacle])
    adapter.scene.measurement_clouds.update(e1=target, e2=held)
    adapter.held = 'e2'
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(load=lambda _: world))
    ik = SimpleNamespace(remove_measured_arm=lambda points: (points, 0))
    monkeypatch.setattr('robots.libero.bounded_skills.PublicPoseScreen', lambda *args, **kwargs: ik)
    monkeypatch.setattr('robots.libero.bounded_skills.remove_current_gripper', lambda points, *args: (points, 0))
    monkeypatch.setattr('robots.libero.bounded_skills.remove_visual_robot', lambda points, ik: (points, {}))
    monkeypatch.setattr('robots.libero.bounded_skills.PublicRouteScreen',
        lambda scene, geometry, ik, **kwargs: {'scene': scene, **kwargs})
    screen = MeasuredSkillAdapter._cloud_and_ik(adapter, 'e1', contact=True)
    np.testing.assert_allclose(screen['scene'], obstacle)
    assert len(screen['contact_points']) == 1
    assert len(screen['payload_local']) == 1


def test_old_instance_pixels_are_not_extended_with_a_new_capture(adapter):
    points = np.array([[.1, .1, .9]])
    adapter.scene.measurement_clouds_by_view = {'e1': {'wrist': {
        'source_step': 0, 'xyz_world': points}}}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=1,
        load=lambda _: pytest.fail('cached target cannot be extended from a different capture')))
    np.testing.assert_array_equal(adapter._instance_pixels('e1'), points)
    assert adapter.instance_boundary_evidence['e1'] == []


@pytest.mark.parametrize("stage", ["held", "before_lift"])
def test_held_payload_does_not_include_disconnected_tabletop_mask(adapter, stage):
    from dataclasses import replace

    yy, xx = np.mgrid[:9, :20]
    world = np.stack([.1+xx*.001, .1+yy*.001, np.where(xx < 10, 1.02, .9)], axis=-1)
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'],
        xyz=(.105, .104, 1.02), lower=(.1, .1, 1.01), upper=(.11, .11, 1.03))
    adapter.held = 'e1' if stage == 'held' else None
    adapter.active = 'e1'
    adapter.scene.measurement_clouds_by_view = {'e1': {'agentview': {
        'source_step': 0, 'xyz_world': world.reshape(-1, 3)}}}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=0,
        load=lambda name: world if name.startswith('agentview') else np.full_like(world, np.nan)))
    payload = adapter._instance_pixels('e1')
    assert len(payload) == 90 and np.allclose(payload[:, 2], 1.02)
    evidence = adapter.instance_boundary_evidence['e1'][0]['held_component']
    assert any(c.get('rejected') == 'outside_stationary_measured_identity' for c in evidence['components'])


def test_temporal_payload_membership_augments_only_the_verified_held_instance(adapter):
    robot = adapter.robot()
    adapter.payload_reference = {'robot': {**robot, 'eef_xyz_m': [0., 0., .9]},
        'target': [[.1, .1, .9]], 'scene': [[.1, .1, .9]], 'capture_step': 0}
    adapter._base_geometry = np.array([[.1, .1, 1.001], [.106, .1, 1.]]), None
    assert len(adapter._instance_pixels('e1')) == 0
    adapter._instance_cache.clear()
    adapter.held = 'e1'
    world = np.array([[[.1, .1, 1.001]]])
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=1, load=lambda _: world))
    np.testing.assert_allclose(np.unique(adapter._instance_pixels('e1'), axis=0), [[.1, .1, 1.001]])
    assert next(e for e in adapter.instance_boundary_evidence['e1'] if 'associated_points' in e)['associated_points'] == 1


def test_payload_reference_does_not_veto_its_own_small_motion(adapter, monkeypatch):
    from robots.libero.bounded_payload import moving_payload_pixels

    target = np.array([[.1, .1, .9], [.12, .1, .9]])
    neighbour = [.122, .1, .902]
    adapter._base_geometry = np.vstack([target, neighbour]), None
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=7))
    # The semantic mask also covers a robot pixel, already removed from the
    # scene by public proprioception/static-geometry self filtering.
    monkeypatch.setattr(adapter, '_contact_pixels', lambda key: np.vstack([target, [9., 9., 9.]]))
    reference = adapter._capture_payload_reference('e1')
    np.testing.assert_allclose(reference['target'], target)
    np.testing.assert_allclose(reference['scene'], [neighbour])
    moved_robot = {**reference['robot'],
        'eef_xyz_m': (np.array(reference['robot']['eef_xyz_m'])+[0., 0., .002]).tolist()}
    matched, evidence = moving_payload_pixels(
        [[.1, .1, .902], neighbour], reference, moved_robot)
    assert matched.tolist() == [True, False]
    assert evidence['stationary_points_retained'] == 1


def test_temporal_payload_refines_a_depth_view_without_a_sam_mask(adapter):
    y, x = np.mgrid[:8, :14]
    world = np.stack([.1+x*.001, .1+y*.001, np.where(x < 10, 1., 1.006)], axis=-1)
    target = world[:, :4].reshape(-1, 3)
    robot = adapter.robot()
    adapter.held = 'e1'
    adapter.payload_reference = {'robot': {**robot, 'eef_xyz_m': (np.array(robot['eef_xyz_m'])-[0., 0., .1]).tolist()},
        'target': target-[0., 0., .1], 'scene': world[:, 10:].reshape(-1, 3), 'capture_step': 0}
    adapter._base_geometry = world.reshape(-1, 3), None
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=1, load=lambda _: world))
    payload = adapter._instance_pixels('e1')
    assert np.any(np.all(np.isclose(payload, world[4, 6]), axis=1))
    assert not np.any(np.all(np.isclose(payload, world[4, 10]), axis=1))
    refined = [e for e in adapter.instance_boundary_evidence['e1'] if 'temporal_seed_pixels' in e]
    assert {e['camera'] for e in refined} == {'agentview', 'wrist'}
    assert all(e['added_pixels'] > 0 for e in refined)


def test_held_payload_interval_recovers_connected_edge_without_owning_neighbours(adapter, monkeypatch):
    # Image occlusion separates these pixels; their measured 3D component
    # still joins the omitted edge just outside the sampled mask extrema.
    seeds = np.array([[.1, .1, 1.], [.1, .11, 1.], [.11, .1, 1.], [.11, .11, 1.]])
    rim = [[.0995, .1, 1.], [.097, .1, 1.]]
    outside = [.0945, .1, 1.]  # Connected, but beyond the measured interval.
    disconnected = [.105, .105, 1.]
    stationary = [.1045, .105, 1.]
    points = np.vstack([seeds, rim, outside, disconnected, stationary])
    world = np.full((1, len(points)*3, 3), np.nan)
    world[0, ::3] = points
    adapter._base_geometry = points, None
    adapter.held = 'e1'
    adapter.payload_reference = {'robot': adapter.robot(), 'target': seeds,
        'scene': [stationary], 'capture_step': 0}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=1,
        load=lambda name: np.zeros((*world.shape[:2], 3), np.uint8)
            if name.endswith('.png') else world))
    monkeypatch.setattr('robots.libero.bounded_payload.moving_payload_pixels',
        lambda *args, **kwargs: (np.arange(len(points)) < len(seeds), {'surface_residual_m': .004}))
    payload = adapter._instance_pixels('e1')
    for point in rim:
        assert np.linalg.norm(payload-point, axis=1).min() < 1e-9
    for point in (outside, disconnected, stationary):
        assert np.linalg.norm(payload-point, axis=1).min() > 1e-6


def test_identical_refreshes_are_no_effect_and_eventually_removed(adapter):
    for _ in range(2):
        request = adapter.request(k=1)
        refresh = next(c for c in request['candidates'] if c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh')
        receipt = adapter.execute(request, decision(request, [refresh['id']]))[0]
        assert receipt['outcome'] == 'no_effect'
    request = adapter.request(k=1)
    assert not any(c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh' for c in request['candidates'])


def test_held_surface_normalisation_is_not_a_scene_change(adapter):
    from dataclasses import replace

    measured = adapter.scene.entities['e1']
    raw_mask_centre = replace(measured, xyz=(.13, .13, .9))
    adapter.held = 'e1'
    adapter.scene.refresh = lambda _: adapter.scene.entities.update(e1=raw_mask_centre)
    adapter._refresh_held_measurement = lambda: adapter.scene.entities.update(e1=measured)
    adapter.refresh()
    for _ in range(2):
        request = adapter.request(k=1)
        candidate = next(c for c in request['candidates']
            if c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh')
        receipt = adapter.execute(request, decision(request, [candidate['id']]))[0]
        assert receipt['outcome'] == 'no_effect'
        assert receipt['changes'][0]['displacement_m'] == [0., 0., 0.]
    assert not any(c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh'
                   for c in adapter.request(k=1)['candidates'])


@pytest.mark.parametrize('reason', ['contact_no_measured_progress', 'contact_surface_motion_ambiguous'])
def test_unrelated_mask_centre_drift_does_not_reenable_no_effect_contact(adapter, reason):
    from dataclasses import replace

    adapter.scene.entities['background'] = Entity('background', 'table', (0., 0., .8),
        (-.5, -.5, .799), (.5, .5, .801), True, 0)
    adapter.refresh()
    action = {'skill': 'nudge', 'parameters': {'anchor_id': 'e1', 'axis': 'y', 'distance_m': .02}}
    route = {'skill': 'move_to', 'parameters': {'anchor_id': 'e1', 'approach': 'above', 'path': 'over'}}
    for _ in range(2):
        adapter.memory.record(action, 'no_effect', reason)
        adapter.memory.record(route, 'failure', 'measured_sweep_collision')
    for x in (.02, -.02, .03):
        entity = adapter.scene.entities['background']
        adapter.scene.entities['background'] = replace(entity, xyz=(x, 0., .8))
        adapter.refresh()
        assert not adapter.memory.apply([action])
    assert adapter.memory.apply([route])  # A changed obstacle can reopen a route.
    source = adapter.scene.entities['e1']
    adapter.scene.entities['e1'] = replace(source, xyz=(.12, .1, .9))
    adapter.refresh()
    assert adapter.memory.apply([action])


def test_contact_mask_jitter_cannot_unlock_failed_nudge_but_measured_motion_can(adapter):
    from dataclasses import replace

    surface = np.random.default_rng(973).uniform([-.02, -.015, -.01], [.02, .015, .01], (900, 3))
    shift = np.zeros(3)
    screen = adapter._cloud_and_ik()
    def geometry(*args, **kwargs):
        screen.target = surface+shift
        adapter._base_geometry = (screen.target, None)
        return screen
    adapter._cloud_and_ik = geometry
    def refresh(_):
        entity = adapter.scene.entities['e1']
        adapter.scene.entities['e1'] = replace(entity,
            xyz=tuple(np.asarray(entity.xyz)+[.012, 0., 0.]), source_step=entity.source_step+1)
    adapter.scene.refresh = refresh
    adapter.active = 'e1'
    for _ in range(2):
        request = adapter.request(k=1)
        action = next(c for c in request['candidates'] if c['skill'] == 'nudge'
            and c['parameters'] == {'anchor_id': 'e1', 'axis': 'y', 'distance_m': .02})
        assert adapter.execute(request, decision(request, [action['id']]))[0]['outcome'] == 'no_effect'
    assert not adapter.memory.apply([action])
    for _ in range(2):
        request = adapter.request(k=1)
        observe = next(c for c in request['candidates']
            if c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh')
        assert adapter.execute(request, decision(request, [observe['id']]))[0]['outcome'] == 'no_effect'
        assert not adapter.memory.apply([action])
    # Public depth now independently supports movement of the source.
    shift[:] = [0., .02, 0.]
    adapter.refresh()
    assert adapter.memory.apply([action])


def test_stationary_entity_reappearing_does_not_reset_failures_or_observe_progress(adapter):
    from dataclasses import replace

    entity = adapter.scene.entities['e1']
    request = adapter.request(k=1)
    move = next(c for c in request['candidates'] if c['skill'] == 'move_to')
    for _ in range(2):
        adapter.memory.record(move, 'failure', 'measured_sweep_collision')
    adapter.previous_scene['e1'] = np.asarray(entity.xyz)
    for visible in (False, True):
        request = adapter.request(k=1)
        refresh = next(c for c in request['candidates']
            if c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh')
        adapter.scene.refresh = lambda _, visible=visible: adapter.scene.entities.update(
            e1=replace(entity, visible=visible))
        receipt = adapter.execute(request, decision(request, [refresh['id']]))[0]
        assert receipt['outcome'] == 'no_effect'
        assert not adapter.memory.apply([move])
    assert not any(c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh'
                   for c in adapter.request(k=1)['candidates'])
    adapter.scene.refresh = lambda _: adapter.scene.entities.update(
        e1=replace(entity, xyz=(.12, .1, .9)))
    adapter.refresh()
    assert adapter.memory.apply([move])


def test_wrist_motion_without_new_scene_evidence_is_not_scan_progress(adapter):
    for _ in range(2):
        request = adapter.request(k=1)
        scan = next(c for c in request['candidates'] if c['skill'] == 'observe' and c['parameters']['mode'] == 'wrist_scan')
        receipt = adapter.execute(request, decision(request, [scan['id']]))[0]
        assert np.linalg.norm(np.array(receipt['after']['eef_xyz_m'])-receipt['before']['eef_xyz_m']) > .01
        assert receipt['outcome'] == 'no_effect'
    assert not any(c['skill'] == 'observe' and c['parameters']['mode'] == 'wrist_scan'
                   for c in adapter.request(k=1)['candidates'])


def test_velocity_is_measured_or_unknown_never_fabricated_zero(adapter):
    assert adapter.robot()['velocity_m_s'] is None
    adapter.p._step_env(np.array([.2, 0., 0., 0., 0., 0., -1.]))
    np.testing.assert_allclose(adapter.robot()['velocity_m_s'], [.2, 0., 0.])


def test_chosen_contact_patch_stays_fixed_until_measured_object_moves(adapter):
    from dataclasses import replace

    request = adapter.request(k=1)
    move = next(c for c in request['candidates'] if c['skill'] == 'move_to')
    adapter.execute(request, decision(request, [move['id']]))
    original_plan = adapter.plans['e1']
    adapter.grasp_geometry = lambda e: {**original_plan, 'xyz_m': [.13, .1, .9]}
    adapter.request(k=1)
    assert adapter.plans['e1'] == original_plan
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], xyz=(.12, .1, .9))
    adapter.request(k=1)
    assert adapter.plans['e1']['xyz_m'] == [.13, .1, .9]


def test_hold_reference_is_captured_after_gripper_contact(adapter):
    from dataclasses import replace

    adapter.active = 'e1'
    request = adapter.request(k=1)
    close = next(c for c in request['candidates'] if c['skill'] == 'set_gripper' and c['parameters']['mode'] == 'close')
    original_refresh = adapter.refresh
    def contact_refresh():
        adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], xyz=(.12, .1, .9))
        original_refresh()
    adapter.refresh = contact_refresh
    adapter.execute(request, decision(request, [close['id']]))
    source, robot = adapter.grasp_reference
    assert source.xyz == (.12, .1, .9)
    np.testing.assert_allclose(robot['eef_xyz_m'], adapter.robot()['eef_xyz_m'])
    np.testing.assert_allclose(robot['eef_quat_xyzw'], adapter.robot()['eef_quat_xyzw'])


@pytest.mark.parametrize('mode,expected', [
    ('visible_centre_change', 'success'), ('stationary', 'failure'),
    ('separated_surface', 'failure'), ('empty_closed', 'failure'), ('stale', 'unmeasured'),
])
def test_lift_checks_transported_surface_bounds_instead_of_visible_centre(adapter, monkeypatch, mode, expected):
    from dataclasses import replace

    adapter.active = 'e1'
    prior = adapter.scene.entities['e1']
    robot = adapter.robot()
    adapter.grasp_reference = (prior, robot)
    monkeypatch.setattr(adapter, '_capture_payload_reference', lambda key: None)
    monkeypatch.setattr(adapter, 'holding_aperture', lambda opening: (mode != 'empty_closed', {}))
    def refresh(_):
        delta = np.asarray(adapter.robot()['eef_xyz_m'])-robot['eef_xyz_m']
        if mode == 'stationary':
            delta = np.zeros(3)
        if mode == 'separated_surface':
            delta += [.1, 0., 0.]
        centre_change = np.array([.02, 0., 0.]) if mode == 'visible_centre_change' else np.zeros(3)
        adapter.scene.entities['e1'] = replace(prior, xyz=tuple(np.asarray(prior.xyz)+delta+centre_change),
            lower=tuple(np.asarray(prior.lower)+delta), upper=tuple(np.asarray(prior.upper)+delta),
            source_step=prior.source_step+(mode != 'stale'))
    adapter.scene.refresh = refresh
    request = adapter.request(k=1)
    lift = next(c for c in request['candidates'] if c['skill'] == 'lift')
    receipt = adapter.execute(request, decision(request, [lift['id']]))[0]
    assert receipt['outcome'] == expected
    evidence = adapter.details[-1]['execution']['public_hold']
    if mode == 'visible_centre_change':
        assert evidence['relative_displacement_m'] > .015
        assert evidence['bounds_co_motion']['extent_gap_m'] == pytest.approx(0.)
        assert adapter.held == 'e1'
    else:
        assert adapter.held is None


def test_vla_success_lost_during_handoff_is_not_final_success(adapter, monkeypatch):
    adapter.allow_vla = True
    monkeypatch.setattr('robots.libero.bounded_skills.run_fallback', lambda **kwargs: {
        'outcome': 'success', 'stop_reason': 'measured_success', 'skill_stop_reason': 'measured_success'})
    result = adapter.call_vla({'anchor_id': 'e1', 'mode': 'pick'})
    assert result['post_handoff_measurement']['completed'] is False
    assert result['outcome'] == 'failure'
    assert result['stop_reason'] == 'completion_lost_during_handoff'
    assert adapter.held is None


def test_vla_prompt_preserves_selected_identity_in_the_policy_image_frame(adapter, monkeypatch):
    from dataclasses import replace

    adapter.allow_vla = True
    adapter.scene.view_axes = ((0., 1., 0.), (1., 0., 0.))
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], name='bowl', xyz=(0., 0., 1.))
    adapter.scene.entities['e2'] = replace(adapter.scene.entities['e1'], id='e2', xyz=(0., .32, 1.))
    captured = {}
    def fallback(**kwargs):
        captured['prompt'] = kwargs['prompt']
        return {'outcome': 'failure', 'stop_reason': 'probe'}
    monkeypatch.setattr('robots.libero.bounded_skills.run_fallback', fallback)
    result = adapter.call_vla({'anchor_id': 'e1', 'mode': 'pick'})
    assert captured['prompt'] == 'pick up the rightmost bowl'
    assert result['template']['version'] == 'measured-libero-subtask/3-pi05-view'
    assert adapter.scene.view_axes == ((0., 1., 0.), (1., 0., 0.))


@pytest.mark.parametrize('opening,move_after_lift,expected', [
    (.00458, True, True), (.0018, True, False), (.079, True, False), (.00458, False, False),
])
def test_vla_pick_uses_calibrated_aperture_and_observed_motion(
        adapter, monkeypatch, opening, move_after_lift, expected):
    from dataclasses import replace

    adapter.allow_vla = True
    monkeypatch.setattr(adapter, '_capture_payload_reference', lambda key: {
        'capture_step': 17, 'scene': np.empty((0, 3)), 'artifacts': {'scene': None}})
    monkeypatch.setattr(adapter, '_refresh_held_measurement', lambda: None)
    adapter.ex.grasp_measurement_calibration = {'opening_calibration': {
        'closed_empty_max_m': .0018488315399736166, 'tolerance_m': .000853613018989563,
        'open_empty_min_m': .07815118134021759},
        'source_report': {'sha256': '0'*64}}
    original = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original(), 'robot0_gripper_qpos': [opening/2, -opening/2]}
    def fallback(**kwargs):
        observe = kwargs['observe']
        assert not observe()['completed']
        source = adapter.scene.entities['e1']
        def lift(distance):
            nonlocal source
            delta = np.array([0., 0., distance])
            source = replace(source, xyz=tuple(np.array(source.xyz)+delta),
                lower=tuple(np.array(source.lower)+delta), upper=tuple(np.array(source.upper)+delta))
            adapter.scene.entities['e1'] = source
            adapter.p.env.position += delta
        lift(.04)
        assert not observe()['completed']
        if move_after_lift:
            lift(.01)
        measured = observe()
        assert measured['completed'] is expected
        assert measured['public_hold']['aperture']['empty_closed_upper_m'] < .00458
        return {'outcome': 'success' if expected else 'failure',
                'stop_reason': 'measured_success' if expected else 'no_progress_blocks'}
    monkeypatch.setattr('robots.libero.bounded_skills.run_fallback', fallback)
    result = adapter.call_vla({'anchor_id': 'e1', 'mode': 'pick'})
    assert result['post_handoff_measurement']['completed'] is expected
    assert (adapter.held == 'e1') is expected


def test_vla_handoff_retains_the_measured_payload_before_settling(adapter, monkeypatch):
    from dataclasses import replace

    adapter.allow_vla = True
    reference = {'capture_step': 17, 'scene': np.empty((0, 3)), 'artifacts': {'scene': None}}
    monkeypatch.setattr(adapter, '_capture_payload_reference', lambda key: reference)
    monkeypatch.setattr(adapter, '_refresh_held_measurement', lambda: None)
    original = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original(), 'robot0_gripper_qpos': [.01, -.01]}
    braking = []
    def settle(primitives, gripper, config):
        assert adapter.held == adapter.active == 'e1'
        assert adapter.payload_reference is reference
        braking.append(True)
        return {'executed': True, 'completed': True, 'steps_used': 1, 'reason': 'osc_hold_settled'}
    monkeypatch.setattr('robots.libero.bounded_skills.settle_osc_hold', settle)
    def fallback(**kwargs):
        observe = kwargs['observe']
        assert not observe()['completed']
        for distance in [.04, .01]:
            source = adapter.scene.entities['e1']
            delta = np.array([0., 0., distance])
            adapter.scene.entities['e1'] = replace(source,
                xyz=tuple(np.array(source.xyz)+delta), lower=tuple(np.array(source.lower)+delta),
                upper=tuple(np.array(source.upper)+delta))
            adapter.p.env.position += delta
            measured = observe()
            if distance == .04:
                assert not measured['completed'] and adapter.held is None
        assert measured['completed']
        state = adapter.robot()
        assert kwargs['handoff']([{'before': state, 'after': state}])['executed']
        return {'outcome': 'success', 'stop_reason': 'measured_success'}
    monkeypatch.setattr('robots.libero.bounded_skills.run_fallback', fallback)
    result = adapter.call_vla({'anchor_id': 'e1', 'mode': 'pick'})
    assert result['outcome'] == 'success' and braking == [True]
    assert result['payload_reference_capture_step'] == 17


def test_vla_static_obstacles_precede_contact_while_target_motion_reference_stays_lifted(adapter, monkeypatch):
    from dataclasses import replace

    adapter.allow_vla = True
    before_scene = np.array([[.1, .1, .9]])
    lifted_target = np.array([[.1, .1, .95]])
    lifted_robot = {**adapter.robot(), 'eef_xyz_m': [.1, .1, .95]}
    initial = {'capture_step': 1, 'scene': before_scene, 'artifacts': {'scene': {'path': 'before'}}}
    lifted = {'capture_step': 56, 'target': lifted_target, 'scene': np.array([[.1, .1, .949]]),
        'robot': lifted_robot, 'artifacts': {'scene': {'path': 'after'}}}
    references = iter([initial, lifted])
    monkeypatch.setattr(adapter, '_capture_payload_reference', lambda _: next(references))
    monkeypatch.setattr(adapter, '_refresh_held_measurement', lambda: None)
    monkeypatch.setattr(adapter.scene, 'refresh', lambda names, **kwargs: None)
    original = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original(), 'robot0_gripper_qpos': [.01, -.01]}
    def fallback(**kwargs):
        observe = kwargs['observe']
        assert observe()['completed'] is False
        for distance in (.04, .01):
            source = adapter.scene.entities['e1']
            delta = np.array([0., 0., distance])
            adapter.scene.entities['e1'] = replace(source,
                xyz=tuple(np.array(source.xyz)+delta), lower=tuple(np.array(source.lower)+delta),
                upper=tuple(np.array(source.upper)+delta))
            adapter.p.env.position += delta
            measured = observe()
        assert measured['completed'] is True
        assert adapter.payload_reference is lifted
        assert lifted['scene'] is before_scene
        assert lifted['target'] is lifted_target
        assert lifted['robot'] is lifted_robot
        assert lifted['artifacts']['scene'] == {'path': 'before'}
        return {'outcome': 'success', 'stop_reason': 'measured_success'}
    monkeypatch.setattr('robots.libero.bounded_skills.run_fallback', fallback)
    result = adapter.call_vla({'anchor_id': 'e1', 'mode': 'pick'})
    assert result['payload_stationary_capture_step'] == 1
    assert result['payload_reference_capture_step'] == 56


def test_held_payload_excludes_raw_pixels_not_fusion_centroids(adapter, monkeypatch):
    pixels = np.array([[.1, .1, .9], [.1005, .1, .9]])
    adapter.held = 'e1'
    adapter.scene.measurement_clouds['e1'] = pixels.mean(0, keepdims=True)
    adapter.scene.measurement_clouds_by_view = {'e1': {'main': {'xyz_world': pixels}}}
    ik = SimpleNamespace(remove_measured_arm=lambda points: (points, {}))
    obstacle = np.array([[.2, .1, .9]])
    adapter._base_geometry = (np.r_[pixels, obstacle], ik)
    monkeypatch.setattr('robots.libero.bounded_skills.remove_current_gripper', lambda points, *args: (points, 0))
    monkeypatch.setattr('robots.libero.bounded_skills.remove_visual_robot', lambda points, *args: (points, {}))
    monkeypatch.setattr('robots.libero.bounded_skills.PublicRouteScreen', lambda scene, *args, **kwargs: (scene, kwargs))
    scene, options = MeasuredSkillAdapter._cloud_and_ik(adapter)
    np.testing.assert_allclose(scene, obstacle)
    assert len(options['payload_local']) > 0
    scene, handoff = MeasuredSkillAdapter._cloud_and_ik(adapter, 'e1', contact=True)
    np.testing.assert_allclose(scene, obstacle)
    assert len(handoff['contact_points']) == 0
    assert len(handoff['payload_local']) > 0


def test_shared_held_pixels_do_not_remain_in_a_stationary_target_mask(adapter, monkeypatch):
    from dataclasses import replace

    held = np.array([[.1, .1, .9]])
    target = np.array([[.3, .1, .9]])
    adapter.scene.entities['e2'] = replace(adapter.scene.entities['e1'], id='e2', name='plate')
    adapter.held = 'e1'
    adapter._instance_pixels = lambda key: held if key == 'e1' else np.r_[held, target]
    adapter._base_geometry = np.r_[held, target, [[.4, .1, .9]]], SimpleNamespace(
        remove_measured_arm=lambda points: (points, {}))
    monkeypatch.setattr('robots.libero.bounded_skills.remove_current_gripper', lambda points, *args: (points, 0))
    monkeypatch.setattr('robots.libero.bounded_skills.remove_visual_robot', lambda points, *args: (points, {}))
    monkeypatch.setattr('robots.libero.bounded_skills.PublicRouteScreen', lambda scene, *args, **kwargs: kwargs)
    screen = MeasuredSkillAdapter._cloud_and_ik(adapter, 'e2', contact=True)
    np.testing.assert_allclose(screen['contact_points'], target)
    assert len(screen['payload_local']) == 1


def test_refresh_uses_transport_prediction_only_to_associate_fresh_measurements(adapter, monkeypatch):
    source = adapter.scene.entities['e1']
    adapter.held = 'e1'
    points = np.array([[.09, .09, .89], [.11, .11, .91]])
    adapter.payload_reference = {'target': points,
        'robot': {'eef_xyz_m': [0., 0., 1.], 'eef_quat_xyzw': [0., 0., 0., 1.]}}
    adapter.p.env.position = np.array([.3, .2, 1.2])
    calls = []
    def refresh(names, *, association_positions):
        assert adapter.scene.entities['e1'] is source
        calls.append(association_positions)
    adapter.scene.refresh = refresh
    monkeypatch.setattr(adapter, '_refresh_held_measurement', lambda: None)
    adapter.refresh()
    np.testing.assert_allclose(calls[0]['e1'], [.4, .3, 1.1])
    assert adapter.scene.entities['e1'] is source


def test_held_anchor_and_lower_route_use_the_cleaned_current_payload(adapter):
    from dataclasses import replace

    y, x = np.mgrid[:8, :10]
    local = np.stack([.1+x*.002, .1+y*.002, np.full(x.shape, -.1)], axis=-1).reshape(-1, 3)
    adapter.held = 'e1'
    adapter.payload_reference = {'capture_step': 0}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=0))
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'],
        xyz=(.1, .1, .8), lower=(-.1, -.1, .7), upper=(.3, .3, 1.))
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.3, .1, .8), (.25, .05, .79), (.35, .15, .81), True, 0)
    adapter._cloud_and_ik = lambda *args, **kwargs: SimpleNamespace(payload=local)
    before = adapter._route('lower', {'target_id': 'e2'})[0]['xyz_m']
    adapter._refresh_held_measurement()
    measured = adapter.scene.entities['e1']
    assert np.ptp(local[:, 0]) == pytest.approx(measured.upper[0]-measured.lower[0])
    assert measured.xyz[2] == pytest.approx(.9)
    assert measured.geometry == 'current_rgbd_clean_payload_surface'
    after = adapter._route('lower', {'target_id': 'e2'})[0]['xyz_m']
    assert after[2] == pytest.approx(.922) and before[2] > after[2]
    adapter.ex.toolkit._state.latest_step = 1
    adapter.scene.entities['e1'] = replace(measured, visible=False)
    # Current temporal RGB-D membership remains a real measurement when
    # this capture has lost its SAM identity. A stale pose alone is not.
    adapter._cloud_and_ik = lambda *args, **kwargs: SimpleNamespace(payload=np.empty((0, 3)))
    adapter._refresh_held_measurement()
    assert not adapter.scene.entities['e1'].visible
    adapter._cloud_and_ik = lambda *args, **kwargs: SimpleNamespace(payload=local)
    adapter._refresh_held_measurement()
    assert adapter.scene.entities['e1'].visible
    assert adapter.scene.entities['e1'].source_step == 1
    assert not next(a for a in adapter.anchors() if a['id'] == 'e1')['cached']


@pytest.mark.parametrize('active,held,opening,expected', [
    ('e1', None, .025, 'set_gripper'),
    (None, None, .025, 'set_gripper'),
    ('another', None, .025, 'set_gripper'),
    ('e1', 'another', .025, 'observe'),
    (None, 'another', .025, 'observe'),
    ('e1', None, .08, 'move_to'),
    (None, None, .08, 'move_to'),
])
def test_oracle_reopens_lost_active_contact_without_dropping_a_held_payload(
        adapter, active, held, opening, expected):
    from robots.libero.bounded_oracle import BoundedOracle

    original_obs = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original_obs(), 'robot0_gripper_qpos': [opening/2, -opening/2]}
    adapter.grasp_geometry = lambda _: None
    adapter.active, adapter.held = active, held
    request = adapter.request(k=1)
    oracle = BoundedOracle(None, adapter)
    oracle.binding.bind = lambda *args, **kwargs: adapter.scene.entities['e1']
    status = {'done': False, 'goals': [['open', 'fixture_1']], 'satisfied': [False]}
    chosen = oracle._choose_one(request, status)
    assert chosen['skill'] == expected
    if expected == 'set_gripper':
        assert chosen['parameters'] == {'mode': 'open'}
        assert oracle.private_trace[-1]['recovery'] == 'open_lost_contact_before_reapproach'
    elif expected == 'move_to':
        assert chosen['parameters']['anchor_id'] == 'e1'
        assert oracle.private_trace[-1]['recovery'] == 'measured_anchor_approach_without_contact_fit'
    else:
        assert 'recovery' not in oracle.private_trace[-1]
    assert adapter.held == held


def test_oracle_releases_a_payload_already_inside_a_measured_container(adapter):
    from robots.libero.bounded_oracle import BoundedOracle

    adapter.scene.entities['e2'] = Entity('e2', 'basket', (.1, .06, .9),
        (.02, -.02, .85), (.18, .14, .95), True, 0)
    adapter.held = 'e1'  # Box footprint is inside, 4cm away from centre.
    adapter.target_cache['e2'] = adapter.scene.entities['e2']
    oracle = BoundedOracle(SimpleNamespace(call=lambda _: {
        'done': False, 'goals': [['in', 'box_1', 'basket_1']], 'satisfied': [False]}), adapter)
    request = adapter.request(k=1)
    assert selected(request, oracle.choose(request))[0]['skill'] == 'release'
