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
    def screen(poses):
        return {
            "passed": True, "reason": "test_public_geometry", "collision": False, "ik_reachable": True,
            "path_min_clearance_m": .05, "screen_scope": "test_measured_mesh"}
    screen.points = screen.target = np.empty((0, 3))
    result._cloud_and_ik = lambda *args, **kwargs: screen
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


@pytest.mark.parametrize('effect,expected', [
    ('stationary', 'no_effect'), ('moved', 'success'),
    ('occluded', 'unmeasured'), ('stale', 'unmeasured'),
    ('opposite', 'failure'), ('perpendicular', 'no_effect'),
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
        adapter._base_geometry = (original_screen.target, None)
        return original_screen
    adapter._cloud_and_ik = screen
    def refresh(_):
        entity = adapter.scene.entities['e1']
        delta = {'moved': [0., .02, 0.], 'opposite': [0., -.02, 0.],
            'perpendicular': [.02, 0., 0.], 'segmentation_drift': [0., .02, 0.]}.get(effect, [0., 0., 0.])
        shifted[:] = delta if effect != 'segmentation_drift' else [0., 0., 0.]
        adapter.scene.entities['e1'] = replace(entity,
            xyz=tuple(np.asarray(entity.xyz)+delta),
            visible=effect != 'occluded',
            source_step=entity.source_step+(effect != 'stale'))
    adapter.scene.refresh = refresh
    initial = adapter.robot()['eef_xyz_m']
    request = adapter.request(k=1)
    candidate = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'anchor_id': 'e1', 'axis': 'y', 'distance_m': .02})
    receipt = adapter.execute(request, decision(request, [candidate['id']]))[0]
    assert receipt['outcome'] == expected
    assert adapter.robot()['eef_xyz_m'][1]-initial[1] == pytest.approx(.02)
    assert adapter.details[-1]['execution']['public_contact_motion']['source'] == 'paired_public_rgbd_axis_surface_registration'
    if effect == 'opposite':
        assert receipt['stop_reason'] == 'contact_motion_opposes_command'
    if effect in {'moved', 'opposite', 'perpendicular'}:
        assert adapter.details[-1]['execution']['public_contact_motion']['axis_progress_m'] == pytest.approx(
            {'moved': .02, 'opposite': -.02, 'perpendicular': 0.}[effect])
    if effect == 'stationary':
        request = adapter.request(k=1)
        adapter.execute(request, decision(request, [candidate['id']]))
        assert all(c['id'] != candidate['id'] for c in adapter.request(k=1)['candidates'])


def test_free_space_nudge_reports_motion_arrival_without_object_effect(adapter):
    request = adapter.request(k=1)
    candidate = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'y', 'distance_m': .02})
    assert adapter.execute(request, decision(request, [candidate['id']]))[0]['outcome'] == 'success'


def test_nudge_measures_handle_motion_independently_of_stationary_parent_pixels(adapter):
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
    adapter._handle_pixels = lambda *args, **kwargs: handle.copy()
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
        assert adapter.details[-1]['blended'] and receipts[0]['outcome'] == 'success'
        assert len(receipts) == 2
    if mode == 'dropped':
        assert receipt['outcome'] == 'failure' and receipt['stop_reason'] == 'public_hold_lost'
        assert receipt['phase'] == 'contact_failure'
        assert adapter.held is adapter.active is adapter.ex.held is None
        assert adapter.payload_reference is adapter.grasp_reference is None
        assert next(c for c in receipt['changes'] if c['anchor_id'] == 'e1')['held'] is False
        assert not any(c['skill'] == 'carry_to' for c in adapter.request(k=1)['candidates'])
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


def test_derived_part_recovers_other_view_surface_but_not_neighbour(adapter):
    part = Entity('e2', 'cabinet top drawer', (.1, .1, .9), (.08, .08, .88), (.12, .12, .92),
        True, 3, part_of='e1', geometry='measured_front_band')
    adapter.scene.entities[part.id] = part
    y, x = np.mgrid[:8, :20]
    primary = np.stack([x*.0005, y*.0005, np.ones_like(x)], axis=-1)
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
def test_contacted_handle_refines_small_public_depth_motion_without_owning_neighbour(
        adapter, tmp_path, monkeypatch, shift_m, accepted, force_normal_fit):
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
    assert bool(len(pixels)) is accepted
    if accepted:
        np.testing.assert_allclose(pixels[:, 2], .904)
    evidence = next(v for v in adapter.instance_boundary_evidence['e1'] if 'registration' in v)
    assert evidence['registration']['accepted'] is accepted
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
    adapter.committed_grasps['e1'] = {'contact_robot': measured_robot(adapter.p)}
    adapter.plans['e1'] = {'handle_measurement': {'source_step': 3, 'views': {
        'main': {'pose': {'xyz': [.1, .1, .9]}, 'cloud': {
            'path': str(path), 'source': 'perception', 'source_step': 3}}}}}
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


def test_fixture_replans_a_symmetric_contact_after_measured_joint_limit_failure(adapter):
    from scipy.spatial.transform import Rotation

    plan = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
        'approach_xyz_m': [.1, -.02, .9], 'width_m': .01}
    adapter.failed_contact_poses['e1'] = [dict(plan)]
    result = adapter._screen_fixture_approaches(adapter.scene.entities['e1'], plan)
    turn = (Rotation.from_quat(result['quat_xyzw'])*Rotation.from_quat(plan['quat_xyzw']).inv()).magnitude()
    assert turn == pytest.approx(np.pi)
    choices = adapter.candidate_diagnostics[-1]['candidates']
    assert all(c['screen']['reason'] == 'measured_joint_limit_during_prior_descent' for c in choices[:6])
    assert choices[6]['screen']['passed']


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
    assert choices[0]['screen']['passed'] and choices[6]['screen']['passed']
    assert choices[0]['screen']['route_joint_margin_rad'] == 1e-6
    assert adapter.candidate_diagnostics[-1]['selected'] == 6


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
    screen.points = screen.target = np.empty((0, 3))
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    assert len(checks) == 2
    np.testing.assert_allclose(plan['quat_xyzw'], checks[-1][-1]['quat_xyzw'], atol=1e-12)
    np.testing.assert_allclose(plan['xyz_m'], checks[-1][-1]['xyz_m'], atol=1e-12)
    assert adapter.candidate_diagnostics[-1]['candidates'][0]['screen']['collision'] is True


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
    assert all(c.get('closure') for c in report['candidates'] if c['patch_index'] == 0)
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


def test_measured_vertical_panel_has_bounded_push_options_without_a_visible_handle(adapter):
    from robots.libero.bounded_oracle import BoundedOracle

    adapter.scene.entities.clear()
    parent = Entity('e2', 'microwave', (.3, .2, 1.), (.2, .1, .9), (.4, .3, 1.1), True, 0)
    door = Entity('e3', 'microwave door', (.1, .2, 1.), (.099, .1, .9), (.101, .3, 1.1),
                  True, 0, part_of=parent.id)
    adapter.scene.entities.update({parent.id: parent, door.id: door})
    y, z = np.mgrid[:20, :20]
    points = np.stack([np.full(y.size, .1), .1+y.ravel()*.008, .9+z.ravel()*.008], axis=-1)
    adapter.scene.measurement_clouds[door.id] = points
    adapter.scene.measure_fixture_handle_pose = lambda *args: {'pose': None}
    adapter.geometry['boxes'] = [{'name': name+'_pad', 'lower': [-.01, -.01, .003],
        'upper': [.01, .01, .005]} for name in ('leftfinger', 'rightfinger')]
    adapter._instance_pixels = lambda key: points if key == door.id else np.empty((0, 3))
    request = adapter.request(k=1)
    plan = adapter.plans[door.id]
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
    def screen(poses):
        axis = Rotation.from_quat(poses[-1]['quat_xyzw']).as_matrix()[:, 1]
        passed = np.dot(axis, close_axis) < -.99
        checks.append(passed)
        return {'passed': passed, 'reason': 'clear' if passed else 'numerical_ik_not_found',
            'collision': False, 'ik_reachable': passed, 'path_min_clearance_m': .02}
    screen.points = screen.target = np.empty((0, 3))
    adapter._cloud_and_ik = lambda *args, **kwargs: screen
    plan = adapter._surface_contact_plan(adapter.scene.entities['e1'], points)
    assert plan is not None and checks[-1] and not any(checks[:-1])
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


def test_contact_boundary_cannot_have_hidden_suffix(adapter):
    request = adapter.request(k=4)
    close = next(c for c in request["candidates"] if c["skill"] == "set_gripper" and c["parameters"]["mode"] == "close")
    observe = next(c for c in request["candidates"] if c["skill"] == "observe")
    with pytest.raises(ValueError, match="boundary"):
        selected(request, decision(request, [close["id"], observe["id"]]))


@pytest.mark.parametrize('skill', ['nudge', 'rotate_wrist'])
def test_anchored_motion_ends_chunk_and_cannot_prefetch_across_contact(adapter, monkeypatch, skill):
    adapter.active = 'e1'
    request = adapter.request(k=4)
    contact = next(c for c in request['candidates'] if c['skill'] == skill
        and c['parameters'].get('anchor_id') == 'e1')
    observe = next(c for c in request['candidates'] if c['skill'] == 'observe')
    with pytest.raises(ValueError, match='boundary'):
        selected(request, decision(request, [contact['id'], observe['id']]))
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
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=0, load=lambda _: world))
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
    adapter.ex.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=0, load=lambda _: world))
    assert adapter.active is None and adapter.held is None
    completed = adapter._instance_pixels('e1')
    assert np.linalg.norm(completed-world[10, 11], axis=1).min() < 1e-9
    assert completed[:, 2].min() >= .9
    assert completed[:, 0].max() < .124
    detail = adapter.instance_boundary_evidence['e1'][0]
    assert detail['connected_surface']['added_pixels'] > 0
    assert any(c.get('rejected') == 'outside_stationary_measured_identity'
               for c in detail['held_component']['components'])


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


def test_unrelated_mask_centre_drift_does_not_reenable_no_effect_contact(adapter):
    from dataclasses import replace

    adapter.scene.entities['background'] = Entity('background', 'table', (0., 0., .8),
        (-.5, -.5, .799), (.5, .5, .801), True, 0)
    adapter.refresh()
    action = {'skill': 'nudge', 'parameters': {'anchor_id': 'e1', 'axis': 'y', 'distance_m': .02}}
    route = {'skill': 'move_to', 'parameters': {'anchor_id': 'e1', 'approach': 'above', 'path': 'over'}}
    for _ in range(2):
        adapter.memory.record(action, 'no_effect', 'contact_no_measured_progress')
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


@pytest.mark.parametrize('opening,move_after_lift,expected', [
    (.00458, True, True), (.0018, True, False), (.079, True, False), (.00458, False, False),
])
def test_vla_pick_uses_calibrated_aperture_and_observed_motion(
        adapter, monkeypatch, opening, move_after_lift, expected):
    from dataclasses import replace

    adapter.allow_vla = True
    monkeypatch.setattr(adapter, '_capture_payload_reference', lambda key: {'capture_step': 17})
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


def test_vla_handoff_screens_the_measured_payload_before_braking(adapter, monkeypatch):
    from dataclasses import replace

    adapter.allow_vla = True
    reference = {'capture_step': 17}
    monkeypatch.setattr(adapter, '_capture_payload_reference', lambda key: reference)
    monkeypatch.setattr(adapter, '_refresh_held_measurement', lambda: None)
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
