"""Bounded preparation and observed contact direction regressions."""
import numpy as np
from types import SimpleNamespace

from robots.libero.bounded_motion import MotionConfig
from robots.libero.bounded_permissive import move
from robots.libero.bounded_adaptive_contact import dominant_direction, in_target
from tests.unit_tests.robots.libero.test_bounded_motion import FakePrimitives


def test_permissive_preparation_goes_to_measured_endpoint_with_vector_clipping():
    p = FakePrimitives()
    result = move(p, {'xyz_m':[.1,.1,1.]},gripper=-1.,config=MotionConfig())
    assert result['arrived'] and result['endpoint_error_m'] <= .012
    assert not result['sweep_veto'] and not result['tracking_error_veto']
    assert max(np.linalg.norm(action[:3])*.05 for action in p.actions) <= .02000001


def test_blocked_preparation_hands_off_after_budget_without_tracking_abort():
    p = FakePrimitives();p._step_env=lambda action:p.actions.append(action)
    result = move(p, {'xyz_m':[.1,0.,1.]},gripper=1.,config=MotionConfig(),max_steps=7)
    assert result['success'] and not result['arrived'] and result['steps_used']==7
    assert result['stop_reason']=='preparation_step_budget' and result['endpoint_error_m']==.1


def test_articulated_direction_uses_observed_largest_axis():
    np.testing.assert_array_equal(dominant_direction([.004,-.012,.001],[1,0,0]),[0,-1,0])
    np.testing.assert_array_equal(dominant_direction([.0001,0,0],[1,0,0]),[1,0,0])


def test_push_arrival_uses_public_target_footprint():
    target=SimpleNamespace(lower=[.1,.2,.8],upper=[.2,.3,.9])
    assert in_target(SimpleNamespace(xyz=[.15,.25,.85]),target)
    assert not in_target(SimpleNamespace(xyz=[.21,.25,.85]),target)


def test_duplicated_fixture_resolves_only_with_unique_observed_child():
    from robots.libero.bounded_adaptive_contact import unique_handle_parent
    entities={key:SimpleNamespace(id=key,name='microwave',visible=True,part_of=None)
              for key in ('a','b')}
    entities['part']=SimpleNamespace(id='part',name='microwave door',visible=True,part_of='a')
    assert unique_handle_parent(entities,'open').id=='a'
    entities['part2']=SimpleNamespace(id='part2',name='microwave door',visible=True,part_of='b')
    assert unique_handle_parent(entities,'open') is None


def test_adaptive_contact_executes_only_a_screened_clear_prefix(monkeypatch):
    import robots.libero.bounded_adaptive_contact as contact
    p=FakePrimitives()
    p.env.execution_budget=lambda:{'used_sim_steps':len(p.actions)}
    entity=SimpleNamespace(xyz=[0.,0.,1.],name='handle')
    captures=SimpleNamespace(latest_step=1)
    surfaces=[np.ones((40,3)),np.ones((40,3))+[.001,.012,0.]]
    adapter=SimpleNamespace(p=p,scene=SimpleNamespace(entities={'handle':entity}),
        ex=SimpleNamespace(toolkit=SimpleNamespace(_state=captures)),config=MotionConfig(),
        gripper_command=1.,_contact_pixels=lambda *a,**k:surfaces.pop(0),
        _cloud_and_ik=lambda *a,**k:None)
    distances=[]
    class ScreenedMotion:
        def __init__(self,*args):pass
        def run(self,points,**kwargs):
            distance=points[0]['xyz_m'][0]-p.env.position[0]
            distances.append(distance)
            if distance>.015:
                return {'executed':False,'steps_used':0,'stop_reason':'measured_sweep_collision',
                    'screen':{'collision':True,'passed':False,'counts':{'leftfinger':1}}}
            p._step_env(np.array([distance/.05,0.,0.,0.,0.,0.,1.]))
            return {'executed':True,'steps_used':1,'stop_reason':'endpoint','screen':{'passed':True}}
    monkeypatch.setattr(contact,'SmoothMotion',ScreenedMotion)
    def refresh(**kwargs):
        p.env.terminated=True
        return {'accepted':True,'translation_m':[.01,0.,0.]}
    adapter.refresh=refresh
    result=contact.run(adapter,{'anchor_id':'handle','axis':'x','direction':1})
    np.testing.assert_allclose(distances,[.02,.01])
    assert result['steps_used']==1 and result['advance_m']==.01
    assert result['motion_attempts'][0]['screen']['counts']=={'leftfinger':1}
    np.testing.assert_allclose(result['checks'][0]['direction_displacement_m'],[.001,.012,0.])
    assert len(p.actions)==1 and p.actions[0][-1]==1.


def test_contact_native_stop_precedes_refresh_and_truncation_is_not_success(monkeypatch):
    import robots.libero.bounded_adaptive_contact as contact
    p=FakePrimitives();p.env.execution_budget=lambda:{'used_sim_steps':len(p.actions)}
    adapter=SimpleNamespace(p=p,scene=SimpleNamespace(entities={
        'handle':SimpleNamespace(xyz=[0.,0.,1.],name='handle')}),
        ex=SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=1))),
        config=MotionConfig(),gripper_command=1.,_contact_pixels=lambda *a,**k:np.ones((40,3)),
        _cloud_and_ik=lambda *a,**k:None)
    adapter.refresh=lambda **k:(_ for _ in ()).throw(AssertionError('refresh after native stop'))
    class NativeMotion:
        def __init__(self,*args):pass
        def run(self,*args,**kwargs):
            p._step_env(np.array([.2,0.,0.,0.,0.,0.,1.]))
            p.env.terminated=True
            return {'executed':True,'steps_used':1,'stop_reason':'native_success'}
    monkeypatch.setattr(contact,'SmoothMotion',NativeMotion)
    result=contact.run(adapter,{'anchor_id':'handle','axis':'x','direction':1})
    assert result['stop_reason']=='native_stop' and result['success']
    p.env.terminated=False;p.env.truncated=True
    result=contact.run(adapter,{'anchor_id':'handle','axis':'x','direction':1})
    assert result['stop_reason']=='environment_budget' and not result['success']
