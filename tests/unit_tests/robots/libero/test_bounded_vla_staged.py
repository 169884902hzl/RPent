"""A compound invocation reuses public primitives without inventing a grip."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator, ValidationError

from robots.libero import bounded_vla_staged as staged


def adapter():
    counter={'steps':0}
    entity=lambda key:SimpleNamespace(id=key,name=key,lower=[0.,0.,.8],upper=[.1,.1,.9])
    value=SimpleNamespace(held='source',receipts=['external'],details=[],_incremental_touched=set(),
        scene=SimpleNamespace(entities={key:entity(key) for key in ('source','target')}),
        latest_request={'observation_id':'selected-call'},
        config=SimpleNamespace(translation_speed_m_s=.15,hz=20.,endpoint_settle_steps=30),
        p=SimpleNamespace(env=SimpleNamespace(terminated=False,truncated=False,
            execution_budget=lambda:{'used_sim_steps':counter['steps']})),
        robot=lambda:{'eef_xyz_m':[.2,.2,1.],'gripper_opening_m':.04},
        holding_aperture=lambda opening:(.003<opening<.077,{}),
        last_policy_outcome='failure')
    value._candidate=lambda skill,parameters,**_: {'skill':skill,'parameters':parameters}
    value._vla_measurement_names=lambda source,target:[e.name for e in (source,target) if e]
    value.refresh=lambda **_:None
    def execute(request,candidate):
        assert request is value.latest_request
        counter['steps']+=5
        receipt={'outcome':'success','stop_reason':'endpoint','skill':candidate['skill']}
        value.receipts.append(receipt);value.details.append({'execution':candidate})
        if candidate['skill']=='release':value.held=None
        return receipt
    value._execute_one=execute
    return value


def test_transfer_preparation_uses_the_measured_destination_and_keeps_its_trace():
    value=adapter()
    result=staged.prepare(value,{'anchor_id':'source','target_id':'target','mode':'on'})
    assert result['success'] and result['steps_used']==5
    assert value.details[0]['execution']=={'skill':'carry_to','parameters':{'target_id':'target'}}
    assert value.receipts==['external']
    assert value._incremental_touched=={'source','target'}


def test_empty_hand_preparation_uses_the_selected_source():
    value=adapter();value.held=None
    result=staged.prepare(value,{'anchor_id':'source','mode':'pick'})
    assert result['success']
    assert value.details[0]['execution']=={'skill':'move_to','parameters':{'anchor_id':'source'}}


def test_a_failed_policy_does_not_suppress_screened_transport_of_a_public_grip():
    value=adapter()
    result=staged.transport(value,{'anchor_id':'source','target_id':'target','mode':'on'})
    assert value.last_policy_outcome=='failure'
    assert [r['skill'] for r in result['components']]==['carry_to','lower','release']
    assert result['steps_used']==15 and value.held is None
    assert value.receipts==['external'] and len(value.details)==3


def test_an_empty_gripper_never_acquires_a_scripted_payload():
    value=adapter();value.holding_aperture=lambda _:(False,{})
    result=staged.transport(value,{'anchor_id':'source','target_id':'target','mode':'in'})
    assert result['components']==[] and result['steps_used']==0
    assert result['reason']=='public_grip_unverified' and value.details==[]


def test_rejected_public_preparation_issues_no_control():
    value=adapter();value._candidate=lambda *_,**__:None
    result=staged.prepare(value,{'anchor_id':'source','target_id':'target','mode':'on'})
    assert not result['success'] and result['steps_used']==0 and value.details==[]
    assert value.receipts==['external']


def test_v7_measured_preparation_requires_an_anchored_subtask():
    root=Path(__file__).resolve().parents[4]
    schema=json.loads((root/'rpent/skill_package/schema7.json').read_bytes())
    validator=Draft202012Validator({'$defs':schema['$defs'],'$ref':'#/$defs/candidate'})
    candidate={'id':'selected','skill':'call_vla',
        'parameters':{'mode':'pick','anchor_id':'source','preparation':'measured_anchor'},
        'consequences':{'path_min_clearance_m':None,'collision':None,'ik_reachable':None,
            'expected_width_m':None,'expected_gripper_opening_m':None,'expected_steps':300,
            'evidence_ids':[],'screen_scope':'unmeasured'},'expected_receipt':[],
        'history':{'n':0,'success_rate':None,'expected_steps':None,'source_manifest_sha256':None},
        'recent_failures':0,'last_failure':None}
    validator.validate(candidate)
    candidate['parameters']={'mode':'task','preparation':'measured_anchor'}
    with pytest.raises(ValidationError):validator.validate(candidate)
