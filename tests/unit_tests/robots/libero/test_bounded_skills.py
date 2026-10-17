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


def test_derived_part_recovers_other_view_surface_but_not_neighbour(adapter):
    part = Entity('e2', 'cabinet top drawer', (.1, .1, .9), (.08, .08, .88), (.12, .12, .92),
        True, 3, part_of='e1', geometry='measured_front_band')
    adapter.scene.entities[part.id] = part
    y, x = np.mgrid[:8, :20]
    primary = np.stack([x*.0005, y*.0005, np.ones_like(x)], axis=-1)
    secondary = primary.copy()
    secondary[..., 2] += .0008
    secondary[:, 12:, 2] += .003
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=3,
        load=lambda name: primary if name.startswith('agentview') else secondary))
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
    adapter.active = None
    assert len(adapter._contact_pixels('e1')) == 0


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
    assert [choice['stand_off_m'] for choice in choices[:5]] == [.12, .12, .08, .08, .04]
    assert all(choice['screen']['collision'] for choice in choices[:4])
    assert choices[4]['screen']['passed']


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
    assert all(c['screen']['collision'] for c in choices['candidates'][:12])


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


def test_surface_contact_can_select_a_clear_wrist_orientation(adapter):
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
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    assert len(checks) == 2
    np.testing.assert_allclose(plan['quat_xyzw'], checks[-1][-1]['quat_xyzw'], atol=1e-12)
    np.testing.assert_allclose(plan['xyz_m'], checks[-1][-1]['xyz_m'], atol=1e-12)
    assert adapter.candidate_diagnostics[-1]['candidates'][0]['screen']['collision'] is True


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


def test_k4_descend_is_a_separate_contact_boundary_and_publishes_active(adapter, monkeypatch):
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
    assert all(r['outcome'] == 'failure' and r['stop_reason'] == 'angular_waypoint_not_reached'
        for r in receipts)


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
    assert adapter.instance_boundary_evidence['e1'][0]['local_plane']['version'] == 'public-local-plane-instance-boundary/1-dev'


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


def test_temporal_payload_membership_augments_only_the_verified_held_instance(adapter):
    robot = adapter.robot()
    adapter.payload_reference = {'robot': {**robot, 'eef_xyz_m': [0., 0., .9]},
        'target': [[.1, .1, .9]], 'scene': [[.1, .1, .9]], 'capture_step': 0}
    adapter._base_geometry = np.array([[.1, .1, 1.001], [.106, .1, 1.]]), None
    assert len(adapter._instance_pixels('e1')) == 0
    adapter._instance_cache.clear()
    adapter.held = 'e1'
    np.testing.assert_allclose(adapter._instance_pixels('e1'), [[.1, .1, 1.001]])
    assert adapter.instance_boundary_evidence['e1'][-1]['associated_points'] == 1


def test_identical_refreshes_are_no_effect_and_eventually_removed(adapter):
    for _ in range(2):
        request = adapter.request(k=1)
        refresh = next(c for c in request['candidates'] if c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh')
        receipt = adapter.execute(request, decision(request, [refresh['id']]))[0]
        assert receipt['outcome'] == 'no_effect'
    request = adapter.request(k=1)
    assert not any(c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh' for c in request['candidates'])


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


@pytest.mark.parametrize('opening,move_after_lift,expected', [
    (.00458, True, True), (.0018, True, False), (.079, True, False), (.00458, False, False),
])
def test_vla_pick_uses_calibrated_aperture_and_observed_motion(
        adapter, monkeypatch, opening, move_after_lift, expected):
    from dataclasses import replace

    adapter.allow_vla = True
    monkeypatch.setattr(adapter, '_capture_payload_reference', lambda key: {'capture_step': 17})
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


def test_vla_handoff_screens_the_measured_payload_before_braking(adapter, monkeypatch):
    from dataclasses import replace

    adapter.allow_vla = True
    reference = {'capture_step': 17}
    monkeypatch.setattr(adapter, '_capture_payload_reference', lambda key: reference)
    original = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original(), 'robot0_gripper_qpos': [.01, -.01]}
    braking = []
    def brake(motion, rows, gripper):
        assert adapter.held == adapter.active == 'e1'
        assert adapter.payload_reference is reference
        braking.append(True)
        return {'executed': True, 'steps_used': 1, 'reason': 'screened_brake'}
    monkeypatch.setattr('robots.libero.bounded_skills.SmoothMotion._brake', brake)
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
