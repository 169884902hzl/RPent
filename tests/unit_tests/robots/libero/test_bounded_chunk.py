"""Conditional contact chunks, runtime cutoffs and private set supervision."""
import copy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_oracle import BoundedOracle
from robots.libero.bounded_screen import PublicRouteScreen
from rpent.skill_package.contract import legal_after, selected, validate, validate_labels
from tests.unit_tests.robots.libero.test_bounded_skills import adapter as adapter, decision


def physical_grip(adapter, *, empty=False):
    """Fake sensors model an object carried only after a measured jaw closure."""
    p = adapter.p
    aperture = [.08]
    raw_obs = p.env.raw_obs
    step = p._step_env
    p.env.raw_obs = lambda: {**raw_obs(), 'robot0_gripper_qpos': [aperture[0]/2, -aperture[0]/2]}
    def control(action):
        step(action)
        if action[-1] > 0:
            aperture[0] = 0. if empty else .04
        elif action[-1] < 0:
            aperture[0] = .08
    p._step_env = control
    entity = adapter.scene.entities['e1']
    def refresh(_):
        rise = max(0., p.env.position[2]-.9) if .005 < aperture[0] < .075 else 0.
        delta = np.array([0., 0., rise])
        adapter.scene.entities['e1'] = replace(entity, xyz=tuple(np.array(entity.xyz)+delta),
            lower=tuple(np.array(entity.lower)+delta), upper=tuple(np.array(entity.upper)+delta),
            source_step=adapter.ex.toolkit._state.latest_step)
    adapter.scene.refresh = refresh


def grip_sequence(request):
    return [next(c for c in request['candidates'] if c['skill'] == skill and (
        c['parameters'].get('anchor_id') == 'e1' if skill != 'set_gripper'
        else c['parameters']['mode'] == 'close') and (
        skill != 'move_to' or c['parameters']['approach'] == 'above' and c['parameters']['path'] == 'direct'))
        for skill in ('move_to', 'descend', 'set_gripper', 'lift')]


def directional_surface(adapter):
    """A measured flat object with distinct screened contact sides."""
    base = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
            'width_m': None, 'contact_kind': 'surface'}
    options = {}
    for name, xy in {'above': [.1, .1], 'front': [.08, .05],
                     'left': [.05, .1], 'right': [.15, .1]}.items():
        contact = [*xy, .9]
        entry = [*xy, 1.02]
        options[name] = {**base, 'xyz_m': contact, 'contact_point_xyz_m': contact,
            'approach_xyz_m': entry, 'approach_route': [{'xyz_m': entry, 'quat_xyzw': base['quat_xyzw']}],
            'preferred_approach': name, 'preferred_path': 'over'}
    adapter.grasp_geometry = lambda _: {**options['above'], 'surface_contact_options': options}
    return options


@pytest.mark.parametrize('in_flight', [False, True])
def test_directional_surface_prefix_and_execution_keep_selected_contact(adapter, in_flight):
    options = directional_surface(adapter)
    request = adapter.request(k=4)
    move = next(c for c in request['candidates'] if c['skill'] == 'move_to'
        and c['parameters'] == {'anchor_id': 'e1', 'approach': 'left', 'path': 'over'})
    descend = next(c for c in request['candidates'] if c['skill'] == 'descend')
    assert adapter._route('move_to', move['parameters'])[-1]['xyz_m'] == options['left']['approach_xyz_m']
    prediction = PublicPrefixPrediction(adapter, request)
    endpoint = adapter._route('move_to', move['parameters'])[-1] if in_flight else None
    prediction.advance(move, commanded_endpoint=endpoint)
    assert prediction.adapter._route('descend', descend['parameters'])[-1]['xyz_m'] == options['left']['xyz_m']
    assert adapter.plans['e1']['xyz_m'] == options['above']['xyz_m']
    receipts = adapter.execute(request, decision(request, [move['id'], descend['id']]))
    assert all(r['outcome'] == 'success' for r in receipts)
    np.testing.assert_allclose(adapter.robot()['eef_xyz_m'], options['left']['xyz_m'], atol=.012)
    assert adapter.committed_grasps['e1']['plan']['xyz_m'] == options['left']['xyz_m']


def test_push_oracle_chooses_opposite_contact_and_excludes_receding_side_from_labels(adapter):
    from robots.libero.v5_state import Entity

    directional_surface(adapter)
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.3, .1, .9),
        (.25, .05, .89), (.35, .15, .91), True, 0)
    adapter.ex.instruction = 'push the box onto the plate'
    request = adapter.request(k=4)
    status = {'done': False, 'goals': [['on', 'box_1', 'plate_1']], 'satisfied': [False]}
    oracle = BoundedOracle(SimpleNamespace(call=lambda *_: status), adapter)
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['skill'] == 'move_to' and chosen['parameters']['approach'] == 'left'
    positive = oracle.last_labels['positions'][0]['rule_acceptable']
    approaches = {c['parameters']['approach'] for c in request['candidates'] if c['id'] in positive}
    assert approaches == {'front', 'left'}
    assert oracle.last_legality_audit['selected_outside_legal'] == 0


def test_four_actions_cross_gripper_only_when_actual_measurements_pass(adapter):
    physical_grip(adapter)
    request = adapter.request(k=4)
    choices = grip_sequence(request)
    receipts = adapter.execute(request, decision(request, [c['id'] for c in choices]))
    assert [r['skill'] for r in receipts] == ['move_to', 'descend', 'set_gripper', 'lift']
    assert all(r['outcome'] == 'success' for r in receipts)
    assert adapter.held == 'e1' and adapter.last_chunk['actual_actions'] == 4
    assert adapter.last_chunk['discarded_ids'] == []
    assert all(c['passed'] for r in receipts for c in r['expectation_checks'])


def test_empty_close_discards_lift_and_reports_failed_width(adapter):
    physical_grip(adapter, empty=True)
    request = adapter.request(k=4)
    choices = grip_sequence(request)
    receipts = adapter.execute(request, decision(request, [c['id'] for c in choices]))
    assert len(receipts) == 3 and receipts[-1]['outcome'] == 'failure'
    assert receipts[-1]['stop_reason'] == 'expected_receipt_gripper_opening_m'
    assert adapter.last_chunk['discarded_ids'] == [choices[-1]['id']]
    assert adapter.held is None and adapter.robot()['eef_xyz_m'][2] == pytest.approx(.9)


@pytest.mark.parametrize('empty', [True, False])
def test_fingertip_contact_expects_empty_closure_without_a_payload(adapter, empty):
    physical_grip(adapter, empty=empty)
    adapter.active = 'e1'
    plan = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
            'width_m': None, 'contact_kind': 'surface'}
    adapter.committed_grasps['e1'] = {'plan': plan, 'anchor_xyz': np.array([.1, .1, .9])}
    request = adapter.request(k=4)
    close = next(c for c in request['candidates'] if c['skill'] == 'set_gripper'
                 and c['parameters']['mode'] == 'close')
    prediction = PublicPrefixPrediction(adapter, request)
    prediction.advance(prediction.candidate(close))
    assert prediction.pending is prediction.payload_id is prediction.payload_local is None
    assert prediction.adapter.held is None
    receipts = adapter.execute(request, decision(request, [close['id']]))
    assert receipts[0]['outcome'] == ('success' if empty else 'failure')
    assert receipts[0]['expectation_checks'][0]['passed'] is empty
    assert adapter.held is None


@pytest.mark.parametrize('moved', [False, True])
def test_fresh_surface_not_a_view_dependent_centre_controls_chunk_cutoff(adapter, moved):
    physical_grip(adapter)
    entity = adapter.scene.entities['e1']
    source = np.random.default_rng(97).uniform([.08, .085, .89], [.12, .115, .91], (900, 3))
    partial = source[source[:, 0] > .11]
    adapter.precontact_instance_surface_v1 = True
    adapter._instance_pixels = lambda key: source if adapter.ex.toolkit._state.latest_step == 0 else (
        partial+[.02, 0., 0.] if moved else partial)
    adapter.scene.refresh = lambda _: adapter.scene.entities.update(e1=replace(entity,
        xyz=tuple(np.array(entity.xyz)+[.02, 0., 0.]),
        source_step=adapter.ex.toolkit._state.latest_step))
    original_screen = adapter._cloud_and_ik
    def screen(*args, **kwargs):
        result = original_screen(*args, **kwargs)
        adapter._base_geometry = (source+[.02, 0., 0.] if moved else source, None)
        return result
    adapter._cloud_and_ik = screen
    request = adapter.request(k=4)
    choices = grip_sequence(request)[:2]
    receipts = adapter.execute(request, decision(request, [c['id'] for c in choices]))
    assert len(receipts) == 2
    assert receipts[-1]['stop_reason'] == ('predicted_anchor_changed' if moved else 'endpoint')
    assert (receipts[-1]['steps_used'] == 0) is moved
    recheck = next(d['anchor_recheck'] for d in adapter.details if 'anchor_recheck' in d)
    assert recheck['accepted'] is (not moved)


def test_lift_without_fresh_object_evidence_cannot_authorize_suffix(adapter):
    request = adapter.request(k=4)
    lift = next(c for c in request['candidates'] if c['skill'] == 'lift')
    open_jaws = next(c for c in request['candidates'] if c['skill'] == 'set_gripper' and c['parameters']['mode'] == 'open')
    receipts = adapter.execute(request, decision(request, [lift['id'], open_jaws['id']]))
    assert len(receipts) == 1 and receipts[0]['outcome'] == 'unmeasured'
    assert receipts[0]['stop_reason'] == 'expected_receipt_object_rise_m'


def test_contact_prefix_checks_translated_surface_despite_partial_mask_centre_drift(adapter):
    adapter.active = 'e1'
    entity = adapter.scene.entities['e1']
    surface = np.random.default_rng(981).uniform([.08, .085, .89], [.12, .115, .91], (1200, 3))
    initial_eef = np.array(adapter.robot()['eef_xyz_m'])
    screen = adapter._cloud_and_ik()
    def current_surface():
        return surface+np.array(adapter.robot()['eef_xyz_m'])-initial_eef
    adapter._instance_pixels = adapter._contact_pixels = lambda key, **kwargs: current_surface()
    def geometry(*args, **kwargs):
        screen.target = current_surface()
        adapter._base_geometry = (screen.target, None)
        return screen
    adapter._cloud_and_ik = geometry
    def refresh(_):
        delta = np.array(adapter.robot()['eef_xyz_m'])-initial_eef
        # Contact geometry follows the hand; a partial mask moves the
        # reported centre sideways by 25mm. It must not veto actual depth.
        bias = np.array([-.025, 0., 0.]) if delta[1] > 0. else np.zeros(3)
        adapter.scene.entities['e1'] = replace(entity,
            xyz=tuple(np.array(entity.xyz)+delta+bias),
            lower=tuple(np.array(entity.lower)+delta), upper=tuple(np.array(entity.upper)+delta),
            source_step=adapter.ex.toolkit._state.latest_step)
    adapter.scene.refresh = refresh
    request = adapter.request(k=4)
    choices = [next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'anchor_id': 'e1', 'axis': 'y', 'distance_m': distance})
        for distance in (.02, .01)]
    receipts = adapter.execute(request, decision(request, [c['id'] for c in choices]))
    assert len(receipts) == 2 and all(r['outcome'] == 'success' for r in receipts)
    np.testing.assert_allclose(np.array(adapter.robot()['eef_xyz_m'])-initial_eef, [0., .03, 0.], atol=1e-8)
    recheck = next(d['anchor_recheck'] for d in adapter.details if 'anchor_recheck' in d)
    assert recheck['accepted']
    np.testing.assert_allclose(recheck['conditional_prefix_translation_m'], [0., .02, 0.])


def test_prefix_consequences_start_from_predicted_not_initial_pose(adapter):
    request = adapter.request(k=4)
    first = next(c for c in request['candidates'] if c['skill'] == 'nudge' and c['parameters'] == {'axis':'x', 'distance_m':.01})
    second = next(c for c in request['candidates'] if c['skill'] == 'nudge' and c['parameters'] == {'axis':'y', 'distance_m':.01})
    plan = adapter.plan_chunk(request, decision(request, [first['id'], second['id']]))
    assert plan[1]['prefix'] == [first['id']]
    assert plan[1]['predicted_robot']['eef_xyz_m'] == [.01, 0., 1.]
    assert adapter.robot()['eef_xyz_m'] == [0., 0., 1.]
    assert len(adapter.p.actions) == 0
    assert plan[1]['conditional_on'] == first['expected_receipt']


@pytest.mark.parametrize('angular_residual_rad', [0., .02])
def test_conditional_ik_residual_cannot_move_the_captured_robot_base(adapter, angular_residual_rad):
    from scipy.spatial.transform import Rotation

    from robots.libero.v5_grasp_kinematics import PublicPoseScreen
    from tests.unit_tests.robots.libero.test_v5_grasp_kinematics import (
        measured_pose,
        robot_fixture,
    )

    path, model, body, addresses = robot_fixture()
    joints = np.array([.2, -.4, .3, -2.2, .1, 2., .6])
    xyz, quat, _ = measured_pose(model, body, addresses, joints)
    ik = PublicPoseScreen(path, joints, xyz, quat, [0., 0., .097], warm_start=True)
    measured = {'robot0_joint_pos': joints, 'robot0_eef_pos': xyz,
                'robot0_eef_quat': quat, 'robot0_gripper_qpos': [.04, -.04]}
    adapter.p.env.raw_obs = lambda: measured
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}],
                'max_opening_m': .08}
    adapter._cloud_and_ik = lambda *args, **kwargs: PublicRouteScreen(
        np.empty((0, 3)), geometry, ik)
    candidate = {'id': 'nudge', 'skill': 'nudge', 'parameters': {'axis': 'x', 'distance_m': .01},
                 'consequences': {'expected_steps': 1}, 'expected_receipt': []}
    prediction = PublicPrefixPrediction(adapter, {'candidates': [candidate]})
    # Warm IK accepts small pose residuals. They are numerical error, not a
    # new base/hand calibration or permission to move captured scene pixels.
    desired = Rotation.from_rotvec([0., 0., angular_residual_rad])*Rotation.from_quat(quat)
    endpoint = {'xyz_m': (xyz+[.004, 0., 0.]).tolist(), 'quat_xyzw': desired.as_quat().tolist()}
    prediction.advance(candidate, commanded_endpoint=endpoint)
    np.testing.assert_array_equal(prediction.ik.world_rotation, ik.world_rotation)
    np.testing.assert_array_equal(prediction.ik.world_offset, ik.world_offset)
    np.testing.assert_array_equal(prediction.sensor['eef_xyz_m'], endpoint['xyz_m'])
    np.testing.assert_array_equal(prediction.ik.joints, prediction.sensor['joint_positions_rad'])
    np.testing.assert_array_equal(adapter.p.env.raw_obs()['robot0_eef_pos'], xyz)
    assert not adapter.p.actions


def test_prediction_screens_payload_instead_of_hand_alone(adapter):
    # A payload point 6cm ahead of the hand reaches an obstacle; the 1cm
    # hand hull remains clear. Both geometry sources are public point clouds.
    geometry = {'boxes':[{'name':'palm', 'lower':[-.005]*3, 'upper':[.005]*3}],
                'max_opening_m': .08}
    adapter.geometry = geometry
    target = np.array([[.16, .1, .9], [.17, .1, .9]])
    obstacle = np.array([[.16, .1, 1.]])
    class IK:
        cache = {}
        last_solution = None
        def check(self, *_):
            return {'solution_found': True}
    ik = IK()
    def screen(anchor=None, *, contact=False):
        return PublicRouteScreen(obstacle, geometry, ik, contact_points=target if anchor else None,
            contact_allowed=contact)
    adapter._cloud_and_ik = screen
    adapter.active = 'e1'
    adapter.p.env.position[:] = [.1, .1, .9]
    request = adapter.request(k=4)
    close = next(c for c in request['candidates'] if c['skill'] == 'set_gripper' and c['parameters']['mode'] == 'close')
    lift = next(c for c in request['candidates'] if c['skill'] == 'lift')
    prediction = PublicPrefixPrediction(adapter, request)
    prediction.advance(prediction.candidate(close))
    consequence = prediction.candidate(lift)['consequences']
    assert consequence['collision'] is True
    assert lift['consequences']['collision'] is False  # initial hand-only screen
    assert adapter.held is None and not adapter.p.actions


@pytest.mark.parametrize('obstacle', [False, True])
def test_prefix_subtracts_raw_instance_before_independent_voxel_samples(adapter, obstacle):
    from robots.libero.v5_geometric_grasp import _voxel
    from robots.libero.v5_grasp_route import separate_target_points

    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}],
                'max_opening_m': .08}
    adapter.geometry = geometry
    target = np.array([[.16, .1, .9], [.161, .1, .9]])
    neighbour = np.array([[.16, .1, .905]]) if obstacle else np.empty((0, 3))
    # Scene and mask have different pixel orders. Sampling each first loses
    # exact instance identity, leaving the object's second pixel as obstacle.
    distant = np.array([[.5, .5, .5]])
    raw_scene = np.concatenate([target[::-1], neighbour, distant])
    class IK:
        cache = {}
        last_solution = None

        def check(self, *_):
            return {'solution_found': True}

    def screen(anchor=None, *, contact=False):
        pixels = target if anchor else np.empty((0, 3))
        own, scene = separate_target_points(pixels, raw_scene)
        return PublicRouteScreen(scene, geometry, IK(), contact_points=own,
            measured_scene_points=raw_scene, measured_target_points=pixels,
            contact_allowed=contact)

    adapter._cloud_and_ik = screen
    adapter.active = 'e1'
    adapter.p.env.position[:] = [.1, .1, .9]
    request = adapter.request(k=4)
    close = next(c for c in request['candidates']
                 if c['skill'] == 'set_gripper' and c['parameters']['mode'] == 'close')
    lift = next(c for c in request['candidates'] if c['skill'] == 'lift')
    prediction = PublicPrefixPrediction(adapter, request)
    prediction.advance(prediction.candidate(close))
    consequence = prediction.candidate(lift)['consequences']
    assert consequence['collision'] is obstacle
    current = prediction._screen('e1', contact=True)
    np.testing.assert_array_equal(current.points, _voxel(np.concatenate([neighbour, distant])))
    assert adapter.held is None and not adapter.p.actions


def test_prefix_reuses_exact_pixel_subtraction_but_rechecks_moved_surfaces(adapter, monkeypatch):
    from robots.libero import bounded_chunk
    from robots.libero.v5_geometric_grasp import _voxel

    target = np.array([[.1, .1, .9], [.101, .1, .9]])
    obstacle = np.array([[.5, .5, .5]])
    world = np.concatenate([target, obstacle])
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}],
                'max_opening_m': .08}
    class IK:
        cache = {}
        last_solution = None
    request = adapter.request(k=4)
    adapter.geometry = geometry
    adapter._cloud_and_ik = lambda anchor=None, **_: PublicRouteScreen(
        world, geometry, IK(), contact_points=target if anchor else None,
        measured_scene_points=world, measured_target_points=target if anchor else None)
    prediction = PublicPrefixPrediction(adapter, request)
    split = bounded_chunk.separate_target_points
    calls = []
    def counted(*args):
        calls.append(1)
        return split(*args)
    monkeypatch.setattr(bounded_chunk, 'separate_target_points', counted)

    first = prediction._screen('e1', contact=True)
    prediction.screens.clear()
    prediction.sensor['gripper_opening_m'] = .04
    second = prediction._screen('e1', contact=True)
    assert len(calls) == 1 and second is not first
    assert first.opening == .08 and second.opening == .04
    np.testing.assert_array_equal(second.points, _voxel(obstacle))

    baseline = prediction._screen()
    prediction.clouds['e1'] = target+[.02, 0., 0.]
    prediction.moved.add('e1')
    prediction.screens.clear()
    moved = prediction._screen()
    assert len(calls) == 3
    np.testing.assert_array_equal(baseline.points, _voxel(world))
    np.testing.assert_array_equal(moved.points,
        _voxel(np.concatenate([obstacle, target+[.02, 0., 0.]])))
    assert not adapter.p.actions


def test_relative_suffix_inherits_contact_from_measured_anchor_prefix(adapter):
    request = adapter.request(k=4)
    descend = next(c for c in request['candidates'] if c['skill'] == 'descend'
                   and c['parameters']['anchor_id'] == 'e1')
    relative = next(c for c in request['candidates'] if c['skill'] == 'nudge'
                    and c['parameters'] == {'axis': 'y', 'distance_m': .02})
    prediction = PublicPrefixPrediction(adapter, request)
    prediction.advance(prediction.candidate(descend))
    candidate = prediction.candidate(relative)
    assert candidate['parameters'] == relative['parameters']
    assert any(c['metric'] == 'contact_progress_m' and c['anchor_id'] == 'e1'
               for c in candidate['expected_receipt'])
    assert not prediction.adapter._free_motion(candidate)
    before = np.array(prediction.adapter.scene.entities['e1'].xyz)
    prediction.advance(candidate)
    np.testing.assert_allclose(prediction.adapter.scene.entities['e1'].xyz, before+[0., .02, 0.])
    assert 'e1' in prediction.moved
    assert adapter.active is None and not adapter.p.actions


def test_relative_contact_cannot_succeed_on_eef_arrival_without_surface_progress(adapter):
    request = adapter.request(k=4)
    relative = next(c for c in request['candidates'] if c['skill'] == 'nudge'
                    and c['parameters'] == {'axis': 'y', 'distance_m': .02})
    screen = adapter._cloud_and_ik()
    surface = np.random.default_rng(978).uniform([-.02, -.015, -.01], [.02, .015, .01], (900, 3))
    def geometry(*args, **kwargs):
        screen.target = surface
        adapter._base_geometry = (surface, None)
        return screen
    adapter._cloud_and_ik = geometry
    adapter.active = 'e1'
    receipts = adapter.execute(request, decision(request, [relative['id']]))
    assert receipts[0]['steps_used'] > 0
    assert receipts[0]['outcome'] == 'no_effect'
    assert receipts[0]['stop_reason'] == 'contact_no_measured_progress'
    assert any(c['condition']['metric'] == 'contact_progress_m'
               and c['condition']['anchor_id'] == 'e1' and c['passed'] is False
               for c in receipts[0]['expectation_checks'])
    assert adapter._last_free_chunk is None


def test_oracle_returns_prefix_specific_private_sets_without_public_labels(adapter):
    physical_grip(adapter)
    request = adapter.request(k=4)
    rpc = SimpleNamespace(call=lambda *_: {'done':False, 'goals':[['on','box_1','plate_1']], 'satisfied':[False]})
    # A simple original picking goal avoids a destination absent from the fixture.
    rpc.call = lambda *_: {'done':False, 'goals':[['on','box_1']], 'satisfied':[False]}
    oracle = BoundedOracle(rpc, adapter)
    answer = oracle.choose(request)
    validate_labels(request, oracle.last_labels)
    assert len(answer['candidate_ids']) == 4
    assert len(oracle.last_labels['positions']) == 4
    assert oracle.last_legality_audit['selected_outside_legal'] == 0
    assert oracle.last_legality_audit['rule_acceptable_outside_legal'] == 0
    for row in oracle.last_labels['positions']:
        assert tuple(row['legal']) == legal_after(request, row['prefix'])
    assert oracle.last_labels['positions'][1]['prefix'] == answer['candidate_ids'][:1]
    assert len(oracle.last_labels['positions'][0]['rule_acceptable']) > 1
    assert all(not row['measured_success'] and not row['measured_failure'] for row in oracle.last_labels['positions'])
    assert len(selected(request, answer)) == 4
    for field in ('rule_acceptable', 'oracle_labels', 'judge'):
        assert field not in request
        with pytest.raises(Exception):
            validate({**request, field: oracle.last_labels})
    corrupt = copy.deepcopy(oracle.last_labels)
    first = corrupt['positions'][0]
    first['measured_success'] = first['measured_failure'] = [first['selected']]
    with pytest.raises(ValueError, match='conflicting'):
        validate_labels(request, corrupt)
    narrowed = copy.deepcopy(oracle.last_labels)
    first = narrowed['positions'][0]
    first['legal'] = [cid for cid in first['legal'] if cid not in first['rule_acceptable']]
    with pytest.raises(ValueError, match='public legal_after'):
        validate_labels(request, narrowed)


@pytest.mark.parametrize('failed_lift', [False, True])
def test_oracle_refreshes_blocked_lift_before_discarding_unmeasured_grasp(adapter, failed_lift):
    physical_grip(adapter)
    adapter.active = 'e1'
    request = adapter.request(k=4)
    for candidate in request['candidates']:
        if candidate['skill'] == 'lift':
            candidate['consequences']['collision'] = True
    request['robot']['gripper_opening_m'] = .04
    if failed_lift:
        adapter.receipts = [dict(skill='lift', outcome='failure')]
    rpc = SimpleNamespace(call=lambda *_: {'done': False, 'goals': [['on', 'box_1']], 'satisfied': [False]})
    chosen = BoundedOracle(rpc, adapter)._choose_one(request, rpc.call())
    assert (chosen['skill'], chosen['parameters']) == (
        ('set_gripper', {'mode': 'open'}) if failed_lift else ('observe', {'mode': 'refresh'}))


@pytest.mark.parametrize('steps,reason,expected', [
    (0, 'predicted_anchor_changed', 'lift'),
    (1, 'predicted_anchor_changed', 'set_gripper'),
    (0, 'measured_sweep_collision', 'set_gripper'),
    (10, 'public_hold_lost', 'set_gripper'),
])
def test_oracle_retries_fresh_lift_after_zero_motion_anchor_guard(adapter, steps, reason, expected):
    physical_grip(adapter)
    adapter.active = 'e1'
    request = adapter.request(k=4)
    adapter.receipts = [dict(skill='lift', outcome='failure', steps_used=steps, stop_reason=reason)]
    request['robot']['gripper_opening_m'] = .04
    rpc = SimpleNamespace(call=lambda *_: {'done': False, 'goals': [['on', 'box_1']], 'satisfied': [False]})
    chosen = BoundedOracle(rpc, adapter)._choose_one(request, rpc.call())
    assert chosen['skill'] == expected
    if expected == 'lift':
        assert chosen['parameters']['anchor_id'] == 'e1'
        assert chosen['consequences']['collision'] is False
        assert chosen['consequences']['ik_reachable'] is True
    else:
        assert chosen['parameters'] == {'mode': 'open'}


@pytest.mark.parametrize('predicate', ['open', 'close', 'turnon', 'turnoff'])
@pytest.mark.parametrize('refresh_blocked', [False, True])
def test_oracle_executes_prefix_checks_before_blocked_contact_recovery(adapter, monkeypatch, predicate, refresh_blocked):
    physical_grip(adapter)
    request = adapter.request(k=4)
    if refresh_blocked:
        request['candidates'] = [c for c in request['candidates']
            if not (c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh')]
    adapter.plans['e1']['handle_measurement'] = {
        'pose': {'approach_normal_xyz': [0., 0., 1.] if predicate.startswith('turn') else [0., 1., 0.]}}
    original = type(adapter)._candidate

    def blocked_closed_contact(self, skill, parameters, **kwargs):
        result = original(self, skill, parameters, **kwargs)
        if (result is not None and skill in {'nudge', 'rotate_wrist'}
                and self.robot()['gripper_opening_m'] < .075):
            result['consequences']['collision'] = True
        return result

    monkeypatch.setattr(type(adapter), '_candidate', blocked_closed_contact)
    status = {'done': False, 'goals': [[predicate, 'fixture_1']], 'satisfied': [False]}
    oracle = BoundedOracle(SimpleNamespace(call=lambda *_: status), adapter)
    oracle.binding.bind = lambda *args, **kwargs: adapter.scene.entities['e1']
    choices = selected(request, oracle.choose(request))
    assert [c['skill'] for c in choices] == ['move_to', 'descend', 'set_gripper']
    assert choices[2]['parameters'] == {'mode': 'close'}
    assert len(oracle.last_labels['positions']) == 3
    assert oracle.private_trace[-1]['await_prefix_measurement']
    assert all(row['judge'] == 'libero-private-task-progress-rules/12'
               for row in oracle.last_labels['positions'])
    receipts = adapter.execute(request, decision(request, [c['id'] for c in choices]))
    assert len(receipts) == 3 and all(r['outcome'] == 'success' for r in receipts)
    assert all(r['expectation_checks'] for r in receipts)

    # The same obstruction confirmed in a current measured state still
    # allows the existing open-and-reapproach recovery.
    current = {**request, 'robot': {**request['robot'], 'gripper_opening_m': .04}}
    adapter.active = 'e1'
    for c in current['candidates']:
        if c['skill'] in {'nudge', 'rotate_wrist'}:
            c['consequences']['collision'] = True
    measured = oracle._choose_one(current, status)
    assert (measured['skill'], measured['parameters']) == ('set_gripper', {'mode': 'open'})


def test_oracle_retains_observe_when_source_has_no_measurement(adapter):
    request = adapter.request(k=4)
    status = {'done': False, 'goals': [['open', 'fixture_1']], 'satisfied': [False]}
    oracle = BoundedOracle(SimpleNamespace(call=lambda *_: status), adapter)
    oracle.binding.bind = lambda *args, **kwargs: None
    choices = selected(request, oracle.choose(request))
    assert [c['skill'] for c in choices] == ['observe']
    assert not any(row.get('await_prefix_measurement') for row in oracle.private_trace)


def test_oracle_prefix_clones_bindings_without_copying_live_rpc(adapter):
    from multiprocessing.process import AuthenticationString

    class LiveRPC:
        authkey = AuthenticationString(b'offline-regression')

        def call(self, *_):
            return {'done': False, 'goals': [['on', 'box_1']], 'satisfied': [False]}

    physical_grip(adapter)
    request = adapter.request(k=4)
    rpc = LiveRPC()
    oracle = BoundedOracle(rpc, adapter)
    original_binding = oracle.binding
    original_binding._bindings['existing'] = 'unchanged'
    original_binding._binding_peers['existing'] = {'peer'}

    answer = oracle.choose(request)

    assert len(answer['candidate_ids']) == 4
    assert oracle.binding.rpc is rpc
    assert original_binding._bindings == {'existing': 'unchanged'}
    assert oracle.binding._bindings['box_1'] == 'e1'
    oracle.binding._binding_peers['existing'].add('new-peer')
    assert original_binding._binding_peers['existing'] == {'peer'}
    validate_labels(request, oracle.last_labels)
