"""Schema6 public progress, merged approaches, and measurement-only caching."""
import copy
from dataclasses import replace

import numpy as np

from robots.libero.bounded_incremental import roi_change
from rpent.skill_package.progress import PublicProgress
from rpent.skill_package.contract import legal_after, validate
from tests.unit_tests.robots.libero.test_bounded_skills import adapter, decision  # noqa: F401


def enable(adapter):
    adapter.schema6_v1 = adapter.lazy_planning_v1 = True
    adapter._cloud_and_ik().endpoint_screen = lambda *a: dict(passed=True,
        collision=None, ik_reachable=True, path_min_clearance_m=None, reason='endpoint')


def test_schema6_defaults_enable_tracking_block_monitoring_and_original_progress_limit(adapter):
    from types import SimpleNamespace
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    adapter.scene.rpc=SimpleNamespace(call=lambda *args,**kwargs:None)
    current=MeasuredSkillAdapter(adapter.ex,'/static/grippers/panda_gripper.xml',allow_vla=False)
    assert current.schema6_v1 and current.lazy_planning_v1
    assert current.vla_budget.controls_per_check is None
    assert current.public_progress.limit==31
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
    assert seen == [('above','over'),('above','direct'),('above','around'),('right','over')]
    assert resolved['id'] == move['id']
    assert resolved['parameters'] == {'anchor_id':'e1','approach':'right','path':'over'}


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


def test_no_progress_terminal_legality_matches_source_catalog(adapter):
    request = adapter.request()
    adapter.schema6_v1 = True
    adapter.public_progress = PublicProgress(2)
    adapter.public_progress.update(request)
    for revision in (1,2):
        row = copy.deepcopy(request); row['revision'] = revision
        adapter.public_progress.update(row)
    request['progress'] = {'version':'public-measured-progress/1','stagnant_decisions':2,'limit':2}
    assert {c['skill'] for c in request['candidates'] if c['id'] in legal_after(request, [])} == {'finish','ask_help'}
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


def test_public_progress_accumulates_subcentimetre_motion():
    monitor = PublicProgress()
    row = {'revision':0,'anchors':[{'id':'a','xyz_m':[0.,0.,0.],'cached':False}],
        'robot':{'held_anchor_id':None},'relations':[],'receipts':[]}
    monitor.update(row)
    for revision, position in ((1,.004),(2,.008),(3,.012)):
        row['revision'] = revision; row['anchors'][0]['xyz_m'][0] = position
        monitor.update(row)
    assert monitor.stagnant == 0 and monitor.last_reasons == ['measured_anchor_displacement:a']


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
            return {'executed':True,'steps_used':10,'stop_reason':'public_contact_stop'}
    monkeypatch.setattr('robots.libero.bounded_guarded.SmoothMotion',Motion)
    detail = run_guarded(adapter, {'anchor_id':'e1','axis':'y','direction':-1})
    assert calls == [None,'no_measured_progress']
    assert detail['advance_m']==0. and detail['guarded_stop_reason']=='no_measured_progress'
