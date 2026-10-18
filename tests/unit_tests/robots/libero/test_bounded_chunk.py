"""Conditional contact chunks, runtime cutoffs and private set supervision."""
import copy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_oracle import BoundedOracle
from robots.libero.bounded_screen import PublicRouteScreen
from rpent.skill_package.contract import selected, validate, validate_labels
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


def test_lift_without_fresh_object_evidence_cannot_authorize_suffix(adapter):
    request = adapter.request(k=4)
    lift = next(c for c in request['candidates'] if c['skill'] == 'lift')
    open_jaws = next(c for c in request['candidates'] if c['skill'] == 'set_gripper' and c['parameters']['mode'] == 'open')
    receipts = adapter.execute(request, decision(request, [lift['id'], open_jaws['id']]))
    assert len(receipts) == 1 and receipts[0]['outcome'] == 'unmeasured'
    assert receipts[0]['stop_reason'] == 'expected_receipt_object_rise_m'


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
