"""Schema6 public progress, merged approaches, and measurement-only caching."""
import copy
from dataclasses import replace

import numpy as np
import pytest

from robots.libero.bounded_incremental import roi_change
from rpent.skill_package.progress import PublicProgress
from rpent.skill_package.contract import legal_after, validate
from tests.unit_tests.robots.libero.test_bounded_skills import adapter, decision  # noqa: F401


def enable(adapter):
    adapter.schema6_v1 = adapter.lazy_planning_v1 = True
    adapter._cloud_and_ik().endpoint_screen = lambda *a: dict(passed=True,
        collision=None, ik_reachable=True, path_min_clearance_m=None, reason='endpoint')


def test_passive_observe_without_change_is_not_reoffered_until_action(adapter, monkeypatch):
    enable(adapter)
    request = adapter.request(k=1)
    refresh = next(c for c in request['candidates'] if c['skill'] == 'observe'
        and c['parameters']['mode'] == 'refresh')
    receipt = {'candidate_id': refresh['id'], 'skill': 'observe', 'outcome': 'no_effect',
        'stop_reason': 'no_measured_scene_change', 'steps_used': 0,
        'before': {'held_anchor_id': None}}
    monkeypatch.setattr(adapter, '_execute_chunk', lambda *_, **__: [receipt])
    adapter.execute(request, decision(request, [refresh['id']]))
    request = adapter.request(k=1)
    assert not any(c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh'
        for c in request['candidates'])
    assert any(c['skill'] == 'observe' and c['parameters']['mode'] == 'wrist_scan'
        for c in request['candidates'])
    close = next(c for c in request['candidates'] if c['skill'] == 'set_gripper'
        and c['parameters']['mode'] == 'close')
    receipt.update(candidate_id=close['id'], skill='set_gripper', outcome='success',
        stop_reason='gripper_command', steps_used=15)
    adapter.execute(request, decision(request, [close['id']]))
    assert any(c['skill'] == 'observe' and c['parameters']['mode'] == 'refresh'
        for c in adapter.request(k=1)['candidates'])


def test_schema6_defaults_enable_tracking_block_monitoring_and_original_progress_limit(adapter):
    from types import SimpleNamespace
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    adapter.scene.rpc=SimpleNamespace(call=lambda *args,**kwargs:None)
    current=MeasuredSkillAdapter(adapter.ex,'/static/grippers/panda_gripper.xml',allow_vla=False)
    assert current.schema6_v1 and current.lazy_planning_v1
    assert current.vla_budget.controls_per_check is None
    assert current.public_progress.limit==11
    assert current.scene.rgbd_mask_tracking_v1 and current.scene.rpc.refresh_captures is None


def test_one_move_per_anchor_and_only_failed_anchor_has_alternates(adapter):
    enable(adapter)
    adapter.scene.entities['peer'] = replace(adapter.scene.entities['e1'], id='peer', xyz=(.3,.1,.9))
    request = adapter.request()
    moves = [c for c in request['candidates'] if c['skill'] == 'move_to']
    assert len(moves) == 2 and all(set(c['parameters']) == {'anchor_id'} for c in moves)
    adapter._failed_move_anchors.add('e1')
    adapter.revision += 1
    request = adapter.request()
    moves = [c for c in request['candidates'] if c['skill'] == 'move_to']
    assert sum(c['parameters']['anchor_id'] == 'e1' for c in moves) == 4
    assert sum(c['parameters']['anchor_id'] == 'peer' for c in moves) == 1
    assert all('path' not in c['parameters'] for c in moves)


def test_provisional_merged_move_does_not_build_a_discarded_screen(adapter, monkeypatch):
    enable(adapter)
    request = adapter.request()
    original = next(c for c in request['candidates'] if c['skill'] == 'move_to')
    def unused(*args, **kwargs):
        raise AssertionError('provisional move constructed a discarded cloud/IK screen')
    monkeypatch.setattr(adapter, '_cloud_and_ik', unused)
    repeated = adapter._candidate('move_to', original['parameters'])
    assert repeated == original
    assert repeated['consequences']['screen_scope'] == 'planner_selected_variant_pending'
    assert repeated['consequences']['collision'] is None


def test_failed_empty_gripper_closure_offers_alternate_approach_to_contacted_anchor(adapter, monkeypatch):
    enable(adapter)
    adapter.active = 'e1'
    request = adapter.request(k=1)
    close = next(c for c in request['candidates']
        if c['skill'] == 'set_gripper' and c['parameters']['mode'] == 'close')
    receipt = {'candidate_id': close['id'], 'skill': 'set_gripper', 'outcome': 'failure',
        'before': {'held_anchor_id': None}, 'expectation_checks': [{
            'condition': {'metric': 'gripper_opening_m', 'anchor_id': 'e1'}, 'passed': False}]}
    monkeypatch.setattr(adapter, '_execute_chunk', lambda *_, **__: [receipt])
    adapter.execute(request, decision(request, [close['id']]))
    moves = [c for c in adapter.request()['candidates'] if c['skill'] == 'move_to']
    assert len(moves) == 4


def test_selected_move_resolves_first_passing_variant_in_fixed_order(adapter, monkeypatch):
    from robots.libero.bounded_motion import SmoothMotion
    enable(adapter)
    request = adapter.request(k=1)
    move = next(c for c in request['candidates'] if c['skill'] == 'move_to')
    seen = []
    original = adapter._route
    def route(skill, parameters, **kwargs):
        if skill == 'move_to':
            seen.append((parameters.get('approach'), parameters.get('path')))
        return original(skill, parameters, **kwargs)
    adapter._route = route
    def prepare(*args, **kwargs):
        passed = seen[-1] == ('right','over')
        from types import SimpleNamespace
        return SimpleNamespace(duration=1.), None, None, dict(passed=passed,
            collision=not passed, ik_reachable=True, path_min_clearance_m=.01 if passed else 0., reason='test')
    monkeypatch.setattr(SmoothMotion, 'prepare', prepare)
    resolved = adapter._candidate('move_to', move['parameters'], complete=True)
    assert seen == [('above','over'),('above','direct'),('above','around'),
        ('right','over')]
    assert resolved['id'] == move['id']
    assert resolved['parameters'] == {'anchor_id':'e1','approach':'right','path':'over'}


@pytest.mark.parametrize('label,parent,fixture', [
    ('box', None, False), ('stove', None, True), ('cabinet top drawer', 'cabinet', True)])
def test_merged_move_prechecks_contact_ingress_only_for_fixtures(adapter, monkeypatch, label, parent, fixture):
    from dataclasses import replace
    from types import SimpleNamespace
    from robots.libero.bounded_motion import SmoothMotion

    enable(adapter)
    request = adapter.request(k=1)
    candidate = next(c for c in request['candidates'] if c['skill'] == 'move_to')
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'], name=label, part_of=parent)
    monkeypatch.setattr(SmoothMotion, 'prepare', lambda *_: (SimpleNamespace(duration=1.), None, None,
        dict(passed=True, collision=False, ik_reachable=True, path_min_clearance_m=.01)))
    seen = []
    def screen(route):
        seen.append(route)
        above = route[0]['xyz_m'][2] > route[-1]['xyz_m'][2]+.05
        return dict(passed=not above, collision=above, ik_reachable=True,
            path_min_clearance_m=0. if above else .01,
            reason='measured_sweep_collision' if above else 'public_route_screen_passed')
    monkeypatch.setattr(adapter, '_cloud_and_ik', lambda *_args, **_kwargs: screen)
    resolved = adapter._candidate('move_to', candidate['parameters'], complete=True)
    if not fixture:
        assert resolved['parameters'] == {'anchor_id': 'e1', 'approach': 'above', 'path': 'over'}
        assert seen == []
        return
    assert resolved['parameters'] == {'anchor_id': 'e1', 'approach': 'right', 'path': 'over'}
    assert len(seen) == 4
    assert all(row[-1]['xyz_m'] == adapter.plans['e1']['xyz_m'] for row in seen)
    assert len([row for row in adapter.candidate_diagnostics
        if row['stage'] == 'move_contact_ingress' and row['screen']['passed'] is False]) == 3


def test_selected_handle_searches_contact_wrist_before_accepting_clear_entry(adapter, monkeypatch):
    from types import SimpleNamespace
    from robots.libero.bounded_motion import SmoothMotion

    enable(adapter)
    request = adapter.request(k=4)
    move = next(c for c in request['candidates'] if c['skill'] == 'move_to')
    adapter.plans['e1']['handle_measurement'] = {'source': 'perception'}
    original = adapter.plans['e1']['quat_xyzw']
    fitted_quat = [0., 1., 0., 0.]
    calls = []
    def fit(entity, plan, *, complete):
        calls.append((entity.id, complete))
        return {**plan, 'quat_xyzw': fitted_quat}
    monkeypatch.setattr(adapter, '_screen_fixture_approaches', fit)
    monkeypatch.setattr(SmoothMotion, 'prepare', lambda *_: (SimpleNamespace(duration=1.), None, None,
        dict(passed=True, collision=False, ik_reachable=True, path_min_clearance_m=.01)))
    monkeypatch.setattr(adapter, '_screen_contact_sequence', lambda *_args, **_kw:
        dict(passed=True, collision=False, ik_reachable=True, path_min_clearance_m=.01))

    adapter._candidate('move_to', move['parameters'], complete=False)
    assert calls == [] and adapter.plans['e1']['quat_xyzw'] == original
    resolved = adapter._candidate('move_to', move['parameters'], complete=True)
    assert calls == [('e1', True)]
    assert resolved['id'] == move['id']
    assert adapter.plans['e1']['quat_xyzw'] == fitted_quat
    assert adapter.plans['e1']['fixture_route_screened'] is True
    adapter._candidate('move_to', move['parameters'], complete=True)
    assert calls == [('e1', True)]


def test_selected_blocked_handle_defers_existing_contact_fit_until_execution(adapter, monkeypatch):
    from types import SimpleNamespace
    from robots.libero.bounded_motion import SmoothMotion

    enable(adapter)
    request = adapter.request(k=1)
    adapter.plans['e1']['handle_measurement'] = {'source_step': 0}
    called = []
    def fit(entity, plan, *, complete=False):
        called.append((entity.id, complete))
        return {**plan, 'xyz_m': [.15, .1, .9]}
    monkeypatch.setattr(adapter, '_screen_fixture_approaches', fit)
    def prepare(*_args):
        passed = adapter.plans['e1']['xyz_m'][0] == .15
        return SimpleNamespace(duration=1.), None, None, dict(passed=passed,
            collision=not passed, ik_reachable=True, path_min_clearance_m=.01)
    monkeypatch.setattr(SmoothMotion, 'prepare', prepare)
    candidate = next(c for c in request['candidates'] if c['skill'] == 'move_to')
    assert called == []
    resolved = adapter._candidate('move_to', candidate['parameters'], complete=True)
    assert called == [('e1', True)]
    assert resolved['consequences']['collision'] is False
    assert resolved['id'] == candidate['id']
    assert adapter.plans['e1']['fixture_route_screened']


def test_merged_move_uses_selected_endpoint_for_predicted_and_measured_contact_phase(adapter):
    from types import SimpleNamespace

    from robots.libero.bounded_oracle import BoundedOracle
    from rpent.skill_package.contract import selected

    enable(adapter)
    adapter.grasp_geometry = lambda _: {'xyz_m': [.1, .1, .9],
        'quat_xyzw': [0., 0., 0., 1.], 'width_m': .04,
        'preferred_approach': 'front', 'preferred_path': 'direct',
        'approach_xyz_m': [.1, -.02, .9],
        'approach_route': [{'xyz_m': [.1, -.02, .9], 'quat_xyzw': [0., 0., 0., 1.]}]}
    request = adapter.request(k=4)
    original_plan = copy.deepcopy(adapter.plans['e1'])
    status = {'done': False, 'goals': [['on', 'box_1']], 'satisfied': [False]}
    oracle = BoundedOracle(SimpleNamespace(call=lambda *_: status), adapter)
    choices = selected(request, oracle.choose(request))
    assert [c['skill'] for c in choices[:2]] == ['move_to', 'descend']
    # The speculative route must not mutate the live contact plan.
    assert adapter.plans['e1'] == original_plan
    receipt = adapter.execute(request, decision(request, [choices[0]['id']]))[0]
    assert receipt['outcome'] == 'success'
    np.testing.assert_allclose(adapter.committed_grasps['e1']['plan']['move_endpoint_xyz_m'],
        [.1, .1, 1.02])
    request = adapter.request(k=1)
    assert selected(request, oracle.choose(request))[0]['skill'] == 'descend'


def test_merged_move_failures_block_selected_public_option_after_two_attempts(adapter, monkeypatch):
    from types import SimpleNamespace
    from robots.libero.bounded_motion import SmoothMotion
    enable(adapter)
    def blocked(*args, **kwargs):
        return SimpleNamespace(duration=1.), None, None, dict(passed=False,
            collision=True, ik_reachable=True, path_min_clearance_m=0., reason='measured_sweep_collision')
    monkeypatch.setattr(SmoothMotion, 'prepare', blocked)
    for expected_failures in (0, 1):
        request = adapter.request(k=1)
        move = next(c for c in request['candidates'] if c['skill'] == 'move_to'
            and c['parameters'] == {'anchor_id': 'e1'})
        assert move['recent_failures'] == expected_failures
        receipts = adapter.execute(request, decision(request, [move['id']]))
        assert receipts[0]['outcome'] == 'failure' and receipts[0]['steps_used'] == 0
    request = adapter.request(k=1)
    assert not any(c['skill'] == 'move_to' and c['parameters'] == {'anchor_id': 'e1'}
        for c in request['candidates'])
    assert any(c['skill'] == 'move_to' and c['parameters'].get('approach')
        for c in request['candidates'])
    adapter.memory.tick(scene_changed=True)
    assert any(c['skill'] == 'move_to' and c['parameters'] == {'anchor_id': 'e1'}
        for c in adapter.request(k=1)['candidates'])


@pytest.mark.parametrize('human_available', [False, True])
def test_no_progress_terminal_legality_matches_source_catalog(adapter, human_available):
    adapter.human_available = human_available
    request = adapter.request()
    adapter.schema6_v1 = True
    adapter.public_progress = PublicProgress(2)
    adapter.public_progress.update(request)
    for revision in (1,2):
        row = copy.deepcopy(request); row['revision'] = revision
        adapter.public_progress.update(row)
    request['progress'] = {'version':'public-measured-progress/1','stagnant_decisions':2,'limit':2}
    assert {c['skill'] for c in request['candidates'] if c['id'] in legal_after(request, [])} == (
        {'finish', 'ask_help'} if human_available else {'finish'})
    validate(request)


def test_repeated_receipt_does_not_refresh_progress_and_cache_is_not_new_measurement():
    monitor = PublicProgress(2)
    row = {'revision':0,'anchors':[],'robot':{'held_anchor_id':None},'relations':[],
        'receipts':[{'observation_id':'a','candidate_id':'c', 'expectation_checks':[
            {'condition':{'metric':'contact_progress_m'}, 'passed':True}]}]}
    assert monitor.update(row) == 0
    row['revision'] = 1
    assert monitor.update(row) == 1
    row['anchors'] = [{'id':'a','xyz_m':[1.,2.,3.],'cached':True}]
    row['revision'] = 2
    assert monitor.update(row) == 2 and monitor.exhausted


def test_roi_missing_or_moving_depth_cannot_be_cached():
    rgb = np.zeros((64,64,3),np.uint8)
    world = np.ones((64,64,3))
    assert not roi_change(rgb,rgb,world,world,[.9,.9,.9],[1.1,1.1,1.1])['changed']
    moved = world.copy(); moved[...,0] += .02
    assert roi_change(rgb,rgb,world,moved,[.9,.9,.9],[1.1,1.1,1.1])['changed']
    assert roi_change(rgb,rgb,world,world,[3.,3.,3.],[4.,4.,4.])['changed']


def test_guarded_candidate_only_for_measured_active_furniture(adapter):
    enable(adapter)
    adapter.active = 'e1'
    assert not any(c['skill']=='guarded_move' for c in adapter.request()['candidates'])
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'],name='cabinet drawer',part_of='cabinet')
    adapter.scene.measure_fixture_handle_pose = lambda *args: {}
    request = adapter.request()
    guarded = [c for c in request['candidates'] if c['skill']=='guarded_move']
    assert len(guarded)==6
    assert all(c['consequences']['expected_steps']==400 for c in guarded)
    assert legal_after(request,[guarded[0]['id']]) == ()


def test_guarded_route_rejection_counts_as_failure_and_stops_identical_retries(adapter, monkeypatch):
    enable(adapter)
    adapter.active = 'e1'
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'],
        name='cabinet drawer', part_of='cabinet')
    adapter.scene.measure_fixture_handle_pose = lambda *args: {}
    monkeypatch.setattr('robots.libero.bounded_guarded.run_guarded', lambda *args: {
        'guarded_stop_reason': 'guarded_route_blocked', 'advance_m': 0.,
        'executed': False, 'steps_used': 0, 'trace': []})
    monkeypatch.setattr(adapter, 'refresh', lambda **kwargs: None)
    for attempt in range(2):
        request = adapter.request(k=1)
        option = next(c for c in request['candidates'] if c['skill'] == 'guarded_move')
        receipt, = adapter.execute(request, decision(request, [option['id']]))
        assert receipt['outcome'] == 'failure' and receipt['stop_reason'] == 'guarded_route_blocked'
        assert receipt['phase'] == 'planning_unreachable'
    assert option['id'] not in {c['id'] for c in adapter.request(k=1)['candidates']}


def test_private_drawer_selector_accepts_guarded_direction_without_nudge_distance(adapter):
    from types import SimpleNamespace
    from robots.libero.bounded_oracle import BoundedOracle
    from rpent.skill_package.contract import selected

    enable(adapter)
    original_obs = adapter.p.env.raw_obs
    adapter.p.env.raw_obs = lambda: {**original_obs(), 'robot0_gripper_qpos': [.01, -.01]}
    adapter.active = 'e1'
    adapter.scene.entities['e1'] = replace(adapter.scene.entities['e1'],
        name='cabinet drawer', part_of='cabinet')
    adapter.scene.measure_fixture_handle_pose = lambda *_: {}
    request = adapter.request(k=1)
    adapter.plans['e1'] = {'xyz_m': [.1, .1, .9], 'quat_xyzw': [0., 0., 0., 1.],
        'handle_measurement': {'pose': {'approach_normal_xyz': [0., 1., 0.]}}}
    oracle = BoundedOracle(SimpleNamespace(call=lambda _: {
        'done': False, 'goals': [['open', 'wooden_cabinet_1_top_region']],
        'satisfied': [False]}), adapter)
    oracle.binding.bind = lambda *_args, **_kwargs: adapter.scene.entities['e1']
    chosen = selected(request, oracle.choose(request))[0]
    assert chosen['skill'] == 'guarded_move'
    assert chosen['parameters'] == {'anchor_id': 'e1', 'axis': 'y', 'direction': 1}


def test_public_progress_accumulates_only_goal_directed_subcentimetre_motion():
    monitor = PublicProgress()
    row = {'revision':0,'anchors':[{'id':'a','xyz_m':[0.,0.,0.],'cached':False}],
        'robot':{'held_anchor_id':None},'relations':[],'receipts':[]}
    monitor.update(row, [{'key':'target_distance','value':1.,'resolution':.01}])
    for revision, position in ((1,.004),(2,.008),(3,.012)):
        row['revision'] = revision; row['anchors'][0]['xyz_m'][0] = position
        monitor.update(row, [{'key':'target_distance','value':1.-position,'resolution':.01}])
    assert monitor.stagnant == 0 and monitor.last_reasons == ['closer_to_goal:target_distance']
    row['revision'] = 4
    row['anchors'][0]['xyz_m'][1] = .5  # unrelated motion is not goal progress
    monitor.update(row, [{'key':'target_distance','value':.99,'resolution':.01}])
    assert monitor.stagnant == 1


def test_guarded_motion_stops_on_two_public_no_progress_checks(adapter, monkeypatch):
    from types import SimpleNamespace
    from robots.libero.bounded_guarded import run_guarded
    adapter._contact_pixels = lambda *args, **kwargs: np.zeros((40,3))
    adapter.refresh = lambda **kwargs: {'accepted':True,
        'compatible_axis_interval_m':[-.001,.001], 'translation_m':[0.,0.,0.]}
    calls=[]
    class Motion:
        def __init__(self,*args): pass
        def prepare(self,*args,**kwargs): return None,None,None,{'passed':True}
        def run(self, waypoints, **kwargs):
            for index in range(len(waypoints)):
                reason=kwargs['waypoint_check'](index,{})
                calls.append(reason)
                if reason: break
            return {'executed':True,'steps_used':10,'stop_reason':'public_contact_stop','trace':[]}
    monkeypatch.setattr('robots.libero.bounded_guarded.SmoothMotion',Motion)
    detail = run_guarded(adapter, {'anchor_id':'e1','axis':'y','direction':-1})
    assert calls == [None,'no_measured_progress']
    assert detail['advance_m']==0. and detail['guarded_stop_reason']=='no_measured_progress'
    assert detail['settling']['settled'] and detail['settling']['steps_used'] == 4
    assert detail['steps_used'] == 14
