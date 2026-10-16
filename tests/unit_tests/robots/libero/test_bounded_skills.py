"""Public-only skill request and exact-ID execution checks."""
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.v5_state import Entity
from rpent.skill_package.contract import selected
from rpent.skill_package.contract import validate
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
    result = MeasuredSkillAdapter(ex, "/static/grippers/panda_gripper.xml", allow_vla=False)
    result.grasp_geometry = lambda e: {"xyz_m": [.1, .1, .9], "quat_xyzw": [0, 0, 0, 1], "width_m": .04}
    result._cloud_and_ik = lambda *args, **kwargs: lambda poses: {
        "passed": True, "reason": "test_public_geometry", "collision": False, "ik_reachable": True,
        "path_min_clearance_m": .05, "screen_scope": "test_measured_mesh"}
    return result


def decision(request, ids):
    return {"schema_version": request["schema_version"], "kind": "decision", "revision": request["revision"],
            "observation_id": request["observation_id"], "candidate_ids": ids}


def test_public_request_omits_whole_task_and_vla_disabled(adapter):
    request = adapter.request(k=4)
    assert not any(c["skill"] in {"vla_task", "call_vla"} for c in request["candidates"])
    assert len([c for c in request["candidates"] if c["skill"] == "move_to"]) == 12
    with pytest.raises(ValueError, match="unknown"):
        selected(request, decision(request, ["invented"]))
    with pytest.raises(ValueError, match="stale"):
        selected(request, {**decision(request, [request["candidates"][0]["id"]]), "revision": 100})


def test_private_upper_bound_retains_resolved_public_identity(adapter):
    from robots.libero.bounded_oracle import BoundedOracle
    status = {"done": False, "goals": [["on", "box_1", "plate_1"]], "satisfied": [False]}
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: status), adapter)
    request = adapter.request(k=1)
    oracle.choose(request)
    assert oracle.binding._bindings["box_1"] == "e1"
    assert oracle.private_trace[-1]["source_public_id"] == "e1"
    assert "box_1" not in str(request)


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


def test_thin_surface_contact_is_available_without_pretending_opposition(adapter):
    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.01, -.01, .003],
        'upper': [.01, .01, .005]} for name in ('leftfinger', 'rightfinger')]
    y, x = np.mgrid[:20, :20]
    points = np.stack([x.ravel()*.003, y.ravel()*.003, np.full(x.size, .9)], axis=-1)
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    assert plan['contact_kind'] == 'surface' and plan['width_m'] is None
    assert adapter._surface_contact_plan(adapter.scene.entities['e1'],
        np.concatenate([points, points+[0., 0., .08]])) is None


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


def test_contact_boundary_cannot_have_hidden_suffix(adapter):
    request = adapter.request(k=4)
    close = next(c for c in request["candidates"] if c["skill"] == "set_gripper" and c["parameters"]["mode"] == "close")
    observe = next(c for c in request["candidates"] if c["skill"] == "observe")
    with pytest.raises(ValueError, match="boundary"):
        selected(request, decision(request, [close["id"], observe["id"]]))


def test_k4_motion_prefix_is_actually_blended(adapter):
    request = adapter.request(k=4)
    moves = [next(c for c in request["candidates"] if c["skill"] == "nudge" and c["parameters"] == {"axis": axis, "distance_m": .01}) for axis in ("x", "y")]
    adapter.execute(request, decision(request, [c["id"] for c in moves]))
    assert adapter.details[-1]["blended"]
    assert len(adapter.details[-1]["candidate_ids"]) == 2
    np.testing.assert_allclose(adapter.robot()["eef_xyz_m"], [.01, .01, 1.], atol=1e-8)


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
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=0, load=lambda _: world))
    completed = adapter._instance_pixels('e1')
    assert len(completed) == 9*10
    assert np.allclose(completed[:, 2], .9)
    assert adapter.instance_boundary_evidence['e1'][0]['added_pixels_per_round'] == [9, 9, 0]


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


def test_held_payload_does_not_include_disconnected_tabletop_mask(adapter):
    from dataclasses import replace

    yy, xx = np.mgrid[:9, :20]
    world = np.stack([.1+xx*.001, .1+yy*.001, np.where(xx < 10, 1.02, .9)], axis=-1)
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'],
        xyz=(.105, .104, 1.02), lower=(.1, .1, 1.01), upper=(.11, .11, 1.03))
    adapter.held = 'e1'
    adapter.scene.measurement_clouds_by_view = {'e1': {'agentview': {
        'source_step': 0, 'xyz_world': world.reshape(-1, 3)}}}
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=0, load=lambda _: world))
    payload = adapter._instance_pixels('e1')
    assert len(payload) == 90 and np.allclose(payload[:, 2], 1.02)
    evidence = adapter.instance_boundary_evidence['e1'][0]['held_component']
    assert any(c.get('rejected') == 'outside_stationary_measured_identity' for c in evidence['components'])


def test_identical_refreshes_are_no_effect_and_eventually_removed(adapter):
    for _ in range(2):
        request = adapter.request(k=1)
        refresh = next(c for c in request['candidates'] if c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh')
        receipt = adapter.execute(request, decision(request, [refresh['id']]))[0]
        assert receipt['outcome'] == 'no_effect'
    request = adapter.request(k=1)
    assert not any(c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh' for c in request['candidates'])


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
    source, eef = adapter.grasp_reference
    assert source.xyz == (.12, .1, .9)
    np.testing.assert_allclose(eef, adapter.robot()['eef_xyz_m'])


def test_vla_success_lost_during_handoff_is_not_final_success(adapter, monkeypatch):
    adapter.allow_vla = True
    monkeypatch.setattr('robots.libero.bounded_skills.run_fallback', lambda **kwargs: {
        'outcome': 'success', 'stop_reason': 'measured_success', 'skill_stop_reason': 'measured_success'})
    result = adapter.call_vla({'anchor_id': 'e1', 'mode': 'pick'})
    assert result['post_handoff_measurement']['completed'] is False
    assert result['outcome'] == 'failure'
    assert result['stop_reason'] == 'completion_lost_during_handoff'
    assert adapter.held is None


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
