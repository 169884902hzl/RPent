"""A real exhausted screen must not be advertised as pending on an unchanged world."""
from types import SimpleNamespace

import numpy as np

from robots.libero.bounded_motion import SmoothMotion
from rpent.skill_package.contract import legal_after, validate
from tests.unit_tests.robots.libero.test_bounded_skills import adapter, decision  # noqa: F401


def test_same_world_zero_control_failure_updates_next_request(adapter, monkeypatch):
    adapter.route_failure_feedback = True
    adapter.lazy_planning_v1 = True
    adapter._cloud_and_ik().endpoint_screen = lambda *a: dict(
        passed=True,collision=None,ik_reachable=True,path_min_clearance_m=None)
    request=adapter.request(k=1)
    candidate=next(c for c in request['candidates'] if c['skill']=='move_to')
    def blocked(*args, **kwargs):
        return SimpleNamespace(duration=1.),None,None,dict(passed=False,collision=True,ik_reachable=None,
            path_min_clearance_m=0.,reason='measured_sweep_collision')
    monkeypatch.setattr(SmoothMotion,'prepare',blocked)
    receipts=adapter.execute(request,decision(request,[candidate['id']]))
    assert receipts[0]['steps_used']==0
    follow=adapter.request(k=1);validate(follow)
    updated=next(c for c in follow['candidates'] if c['id']==candidate['id'])
    assert updated['consequences']['collision'] is True
    assert updated['last_failure']=='measured_sweep_collision'
    assert updated['id'] not in legal_after(follow,[])
    assert not adapter.p.actions


def test_changed_depth_or_robot_releases_old_rejection(adapter):
    from robots.libero.bounded_route_feedback import apply, public_context, remember
    frame=np.ones((2,2,3))
    adapter.ex.toolkit._state.load=lambda _:frame
    request=adapter.request(k=1)
    candidate=next(c for c in request['candidates'] if c['skill']=='move_to')
    detail={'screen':{'passed':False,'collision':False,'ik_reachable':False,'path_min_clearance_m':.01}}
    receipt={'outcome':'failure','steps_used':0,'stop_reason':'numerical_ik_not_found'}
    key=public_context(adapter);remember(adapter,candidate,receipt,detail,key)
    assert apply(adapter,[candidate])[0]['consequences']['ik_reachable'] is False
    frame[0,0,0]+=.001
    assert apply(adapter,[candidate])[0]==candidate
    assert adapter._route_rejections is None
    remember(adapter,candidate,receipt,detail,public_context(adapter))
    adapter.p.env.position[0]+=.01
    assert apply(adapter,[candidate])[0]==candidate


def test_executed_failure_is_not_frozen_as_an_unreachable_start(adapter):
    from robots.libero.bounded_route_feedback import apply, public_context, remember
    request=adapter.request(k=1)
    candidate=next(c for c in request['candidates'] if c['skill']=='move_to')
    receipt={'outcome':'failure','steps_used':3,'stop_reason':'tracking_error'}
    detail={'screen':{'passed':False,'collision':True,'ik_reachable':True,'path_min_clearance_m':0.}}
    remember(adapter,candidate,receipt,detail,public_context(adapter))
    assert apply(adapter,[candidate])[0]==candidate


def test_capture_evidence_ids_are_not_a_changed_route(adapter):
    from robots.libero.bounded_route_feedback import public_context,remember,apply
    request=adapter.request(k=1)
    candidate=next(c for c in request['candidates'] if c['skill']=='move_to')
    key=candidate['parameters']['anchor_id']
    plan=adapter.plans[key]
    plan['contact_evidence']={'measurement_id':'rgbd:0:'+key,'capture_step':0}
    before=public_context(adapter)
    plan['contact_evidence']={'measurement_id':'rgbd:1:'+key,'capture_step':1}
    plan.setdefault('handle_measurement',{})['source_step']=1
    assert public_context(adapter)==before
    remember(adapter,candidate,{'outcome':'failure','steps_used':0,'stop_reason':'numerical_ik_not_found'},
        {'screen':{'passed':False,'collision':False,'ik_reachable':False}},before)
    assert apply(adapter,[candidate])[0]['consequences']['ik_reachable'] is False
    plan['xyz_m'][0]+=.001
    assert apply(adapter,[candidate])[0]==candidate


def test_planning_another_anchor_keeps_the_first_failed_route(adapter):
    from robots.libero.bounded_route_feedback import public_context,remember,apply
    request=adapter.request(k=1);candidate=next(c for c in request['candidates'] if c['skill']=='move_to')
    remember(adapter,candidate,{'outcome':'failure','steps_used':0,'stop_reason':'numerical_ik_not_found'},
        {'screen':{'passed':False,'collision':False,'ik_reachable':False}},public_context(adapter))
    adapter.plans['another_public_anchor']={'xyz_m':[.1,.2,.9],'quat_xyzw':[0.,0.,0.,1.]}
    adapter.committed_grasps['another_public_anchor']={'plan':adapter.plans['another_public_anchor']}
    assert apply(adapter,[candidate])[0]['consequences']['ik_reachable'] is False


def test_other_association_does_not_change_the_selected_route_screen(adapter):
    from dataclasses import replace
    from robots.libero.bounded_route_feedback import public_context,remember,apply
    request=adapter.request(k=1);candidate=next(c for c in request['candidates'] if c['skill']=='move_to')
    remember(adapter,candidate,{'outcome':'failure','steps_used':0,'stop_reason':'numerical_ik_not_found'},
        {'screen':{'passed':False,'collision':False,'ik_reachable':False}},public_context(adapter))
    adapter.scene.entities['unrelated']=replace(adapter.scene.entities['e1'],id='unrelated',xyz=(.7,.7,.9))
    adapter.scene.measurement_clouds['unrelated']=np.ones((40,3))
    assert apply(adapter,[candidate])[0]['consequences']['ik_reachable'] is False
    screen=adapter._cloud_and_ik('e1',contact=False)
    screen.points=np.array([[.001,0.,0.]])
    assert apply(adapter,[candidate])[0]==candidate


def test_rejected_planning_reuses_its_capture_and_explicit_observe_still_refreshes(adapter,monkeypatch):
    adapter.route_failure_feedback=True;adapter.lazy_planning_v1=True
    adapter._cloud_and_ik().endpoint_screen=lambda *args:dict(passed=True,collision=None,ik_reachable=True,path_min_clearance_m=None)
    request=adapter.request(k=1);candidate=next(c for c in request['candidates'] if c['skill']=='move_to')
    def blocked(*args,**kwargs):
        return SimpleNamespace(duration=1.),None,None,dict(passed=False,collision=True,ik_reachable=None,
            path_min_clearance_m=0.,reason='measured_sweep_collision')
    monkeypatch.setattr(SmoothMotion,'prepare',blocked)
    step=adapter.ex.toolkit._state.latest_step
    receipt,=adapter.execute(request,decision(request,[candidate['id']]))
    assert receipt['steps_used']==0 and adapter.ex.toolkit._state.latest_step==step
    follow=adapter.request(k=1)
    assert candidate['id'] not in legal_after(follow,[])
    observe=next(c for c in follow['candidates'] if c['skill']=='observe' and c['parameters']['mode']=='refresh')
    adapter.execute(follow,decision(follow,[observe['id']]))
    assert adapter.ex.toolkit._state.latest_step>step
