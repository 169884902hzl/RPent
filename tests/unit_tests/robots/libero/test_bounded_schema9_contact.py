"""New measured contact options preserve finite public legality and old menus."""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest

from rpent.skill_package.contract import legal_after, selected, validate
from rpent.skill_package.feedback import FeedbackConfig, SuccessFeedback, configure
from tests.unit_tests.robots.libero.test_bounded_skills import adapter, decision  # noqa: F401
from tests.unit_tests.robots.libero.test_bounded_schema6 import enable


def activate(adapter):
    enable(adapter)
    adapter.adaptive_contact_skills = True
    configure(adapter, SuccessFeedback(FeedbackConfig(True), native_success=lambda: False), aggressive=True)


def test_new_push_menu_uses_all_measured_regions_and_is_opt_in(adapter):
    adapter.active = 'e1'
    for key, x in [('left', -.2), ('right', .3)]:
        adapter.scene.entities[key] = replace(adapter.scene.entities['e1'], id=key,
            name='area '+key, xyz=(x,.1,.9))
    assert not any(c['skill']=='push_to' for c in adapter.request()['candidates'])
    activate(adapter)
    request = adapter.request(k=4)
    validate(request)
    options = [c for c in request['candidates'] if c['skill']=='push_to']
    assert request['schema_version']=='bounded-skills/9'
    assert {c['parameters']['target_id'] for c in options} == {'left','right'}
    for c in options:
        assert c['id'] in legal_after(request, [])
        assert legal_after(request, [c['id']]) == ()


def test_oracle_can_choose_new_handle_skill_without_predicting_its_endpoint(adapter):
    from robots.libero.bounded_oracle import BoundedOracle
    activate(adapter)
    original_obs=adapter.p.env.raw_obs
    adapter.p.env.raw_obs=lambda:{**original_obs(),'robot0_gripper_qpos':[.01,-.01]}
    adapter.active='e1'
    adapter.scene.entities['e1']=replace(adapter.scene.entities['e1'],
        name='cabinet drawer',part_of='cabinet')
    adapter.scene.measure_fixture_handle_pose=lambda *_:{}
    request=adapter.request(k=4)
    options=[c for c in request['candidates'] if c['skill']=='open_close_articulated']
    assert len(options)==6
    adapter.plans['e1']={'xyz_m':[.1,.1,.9],'quat_xyzw':[0.,0.,0.,1.],
        'handle_measurement':{'pose':{'approach_normal_xyz':[0.,1.,0.]}}}
    oracle=BoundedOracle(SimpleNamespace(call=lambda _:{'done':False,
        'goals':[['open','wooden_cabinet_1_top_region']],'satisfied':[False]}),adapter)
    oracle.binding.bind=lambda *_args,**_kwargs:adapter.scene.entities['e1']
    decision=oracle.choose(request)
    chosen,=selected(request,decision)
    assert chosen['skill']=='open_close_articulated'
    assert chosen['parameters']=={'anchor_id':'e1','axis':'y','direction':1}
    assert len(decision['candidate_ids'])==1


def test_unexecuted_contact_receipt_does_not_report_a_measured_displacement(adapter, monkeypatch):
    activate(adapter)
    adapter.active='e1'
    adapter.scene.entities['e1']=replace(adapter.scene.entities['e1'],
        name='cabinet drawer',part_of='cabinet')
    adapter.scene.measure_fixture_handle_pose=lambda *_:{}
    request=adapter.request(k=1)
    option=next(c for c in request['candidates'] if c['skill']=='open_close_articulated')
    monkeypatch.setattr('robots.libero.bounded_adaptive_contact.run',lambda *a,**k:{
        'steps_used':0,'advance_m':0.,'stop_reason':'measured_sweep_collision','checks':[],
        'motion_attempts':[{'screen':{'passed':False,'collision':True}}]})
    receipt,=adapter.execute(request,decision(request,[option['id']]))
    validate(receipt)
    assert receipt['steps_used']==0 and receipt['phase']=='planning_unreachable'
    assert receipt['contact_displacement_m'] is None
    assert not adapter.p.actions


@pytest.mark.parametrize('registration', [None, {'accepted':False}])
def test_executed_but_unmeasured_contact_displacement_is_unknown(adapter, monkeypatch, registration):
    activate(adapter)
    adapter.active='e1'
    adapter.scene.entities['e1']=replace(adapter.scene.entities['e1'],
        name='cabinet drawer',part_of='cabinet')
    adapter.scene.measure_fixture_handle_pose=lambda *_:{}
    request=adapter.request(k=1)
    option=next(c for c in request['candidates'] if c['skill']=='open_close_articulated')
    def run(*args,**kwargs):
        adapter.p._step_env(np.array([0.,0.,0.,0.,0.,0.,1.]))
        return {'steps_used':1,'advance_m':0.,'stop_reason':'contact_motion_unmeasured',
            'contact_surface_displacement_m':[0.,0.,0.],
            'checks':[{'registration':registration,'direction_displacement_m':None}]}
    monkeypatch.setattr('robots.libero.bounded_adaptive_contact.run',run)
    monkeypatch.setattr(adapter,'refresh',lambda **kwargs:None)
    receipt,=adapter.execute(request,decision(request,[option['id']]))
    assert receipt['steps_used']==1 and receipt['contact_displacement_m'] is None
    validate(receipt)


def test_missing_contact_plan_is_remembered_so_oracle_can_try_another_method(adapter,monkeypatch):
    activate(adapter);adapter.active='e1'
    adapter.scene.entities['e1']=replace(adapter.scene.entities['e1'],name='cabinet drawer',part_of='cabinet')
    adapter.scene.measure_fixture_handle_pose=lambda *_:{}
    request=adapter.request(k=1)
    option=next(c for c in request['candidates'] if c['skill']=='open_close_articulated')
    monkeypatch.setattr('robots.libero.bounded_adaptive_contact.run',lambda *a,**k:{
        'steps_used':0,'advance_m':0.,'stop_reason':'public_contact_plan_missing','checks':[]})
    monkeypatch.setattr(adapter,'refresh',lambda **kwargs:None)
    receipt,=adapter.execute(request,decision(request,[option['id']]))
    assert receipt['outcome']=='failure' and receipt['phase']=='perception'
    assert receipt['contact_displacement_m'] is None and not adapter.p.actions
    follow=adapter.request(k=1)
    current=next(c for c in follow['candidates'] if c['id']==option['id'])
    assert current['recent_failures']==1 and current['last_failure']=='public_contact_plan_missing'
