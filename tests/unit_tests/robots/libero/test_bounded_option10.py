"""Regressions for explicit permissive options and public source relations."""
from dataclasses import replace
from types import SimpleNamespace

from robots.libero.v5_oracle_policy import OriginalOraclePolicy
from robots.libero.v5_state import Entity
from robots.libero.bounded_storage_progress import ordered_status
from rpent.skill_package.feedback import FeedbackConfig, SuccessFeedback, configure
from rpent.skill_package.contract import validate, legal_after
from tests.unit_tests.robots.libero.test_bounded_skills import adapter  # noqa: F401
from tests.unit_tests.robots.libero.test_bounded_schema6 import enable


def test_not_between_selects_the_other_measured_bowl():
    def e(key,name,x,y):return Entity(key,name,(x,y,.93),(x-.03,y-.03,.9),(x+.03,y+.03,.96),True,0)
    entities=[e('between','bowl',-.055,.209),e('outside','bowl',-.207,.333),
        e('p','plate',.071,.191),e('r','ramekin',-.216,.207)]
    binder=OriginalOraclePolicy(None);axes=((0.,1.,0.),(1.,0.,0.))
    selected=binder.bind('akita_black_bowl_2',entities,
        'Pick the akita black bowl not between the plate and the ramekin',axes)
    assert selected.id=='outside'
    selected=binder.bind('akita_black_bowl_1',entities,
        'Pick the akita black bowl between the plate and the ramekin',axes)
    assert selected.id=='between'


def test_storage_open_insert_close_order_is_private_and_generic():
    goals=[['close','cabinet_bottom_region'],['in','bowl','cabinet_bottom_region']]
    initial={'done':False,'goals':goals,'satisfied':[True,False]}
    assert ordered_status(initial)['goals']==[['open','cabinet_bottom_region'],goals[1],goals[0]]
    assert initial['goals']==goals and initial['satisfied']==[True,False]
    opened={**initial,'satisfied':[False,False],'storage_open':{'cabinet_bottom_region':True}}
    assert ordered_status(opened)['goals']==[goals[1],goals[0]]
    inserted={**initial,'satisfied':[False,True]}
    assert ordered_status(inserted)['goals'][0]==goals[0]


def test_explicit_permissive_variant_and_contact_menu_are_opt_in(adapter):
    enable(adapter);adapter.allow_vla=True;adapter.vla_options_v2=True
    adapter.scene.entities['e1']=replace(adapter.scene.entities['e1'],name='cabinet drawer',part_of='cabinet')
    adapter.scene.measure_fixture_handle_pose=lambda *_:{}
    adapter.adaptive_contact_skills=True;adapter.permissive_preparation_options=True
    configure(adapter,SuccessFeedback(FeedbackConfig(True),native_success=lambda:False),aggressive=True)
    request=adapter.request(k=4);validate(request)
    assert request['schema_version']=='bounded-skills/10'
    choices=[c for c in request['candidates'] if c['skill']=='call_vla' and c['parameters'].get('anchor_id')=='e1']
    assert {'measured_anchor','measured_anchor_permissive'} <= {c['parameters']['preparation'] for c in choices}
    compound=[c for c in request['candidates'] if c['skill']=='open_close_articulated'
        and c['parameters'].get('preparation')=='measured_anchor_permissive']
    assert len(compound)==6
    assert all(c['id'] in legal_after(request,[]) for c in compound)


def test_distinct_support_is_visible_in_selected_instance_description():
    from robots.libero.v5_subtasks import measured_instance_description
    def e(key,name,z,lo,hi):return Entity(key,name,(0.,0.,z),(-.03,-.03,lo),(.03,.03,hi),True,0)
    high=e('high','bowl',1.15,1.13,1.18);low=e('low','bowl',1.09,1.07,1.11)
    support=replace(e('surface','cabinet top surface',1.125,1.12,1.13),part_of='cabinet',geometry='measured_top_surface')
    desc=measured_instance_description(high,[high,low,support])
    assert desc=='bowl on the cabinet top surface'


def test_partially_open_storage_must_reach_the_native_open_predicate():
    status={'done':False,'goals':[['close','drawer_region'],['in','box','drawer_region']],
        'satisfied':[False,False],'storage_open':{'drawer_region':False}}
    assert ordered_status(status)['goals'][0]==['open','drawer_region']
    status['storage_open']['drawer_region']=True
    assert ordered_status(status)['goals'][0]==['in','box','drawer_region']


def test_repeated_observations_yield_to_a_different_legal_method(adapter):
    from robots.libero.bounded_success_loop import choose
    enable(adapter);adapter.allow_vla=True;adapter.vla_options_v2=True
    configure(adapter,SuccessFeedback(FeedbackConfig(True),native_success=lambda:False),aggressive=True)
    request=adapter.request(k=1)
    observe=next(c for c in request['candidates'] if c['skill']=='observe')
    policy=SimpleNamespace(choose=lambda r:{'schema_version':r['schema_version'],'kind':'decision',
        'revision':r['revision'],'observation_id':r['observation_id'],'candidate_ids':[observe['id']]})
    facade=SimpleNamespace(goal_status=lambda:{'done':False,'goals':[['on','box','plate']],'satisfied':[False]})
    probe=SimpleNamespace(split_subtasks=lambda *_:([{'goal_index':0,'id':'g0:pick','mode':'pick',
        'source_symbol':'box','target_symbol':None}],[]),bind_subtask=lambda *_:(None,None))
    options={c['id']:c for c in request['candidates']}
    decisions=[choose(probe,facade,adapter,policy,request)[0] for _ in range(3)]
    assert [options[d['candidate_ids'][0]]['skill'] for d in decisions]==['observe','observe','call_vla']
    assert 'storage_open' not in request and 'subgoal_status' not in request


def test_historical_schema6_does_not_gain_the_new_preparation_menu(adapter):
    enable(adapter);adapter.allow_vla=True;adapter.vla_options_v2=True
    request=adapter.request(k=1);validate(request)
    assert request['schema_version']=='bounded-skills/6'
    assert not any(c['parameters'].get('preparation') in {
        'measured_anchor','measured_anchor_permissive'} for c in request['candidates'])
