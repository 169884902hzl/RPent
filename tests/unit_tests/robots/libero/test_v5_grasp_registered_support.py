import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import mujoco
import numpy as np
import pytest
from robots.libero.v5_grasp_support_worker import evaluate, descendants, mass_weighted_com, default_mask_filter
from robots.libero.v5_grasp_truth import sustained_grasp_v3, grasp_trace_summary_v3


def scene(*, support=False, explicit=False, side=False):
    table = '<geom name="table" type="plane" size="2 2 .01" pos="0 0 .125"/>' if support else ''
    wall = '<geom name="wall" type="box" size=".01 .4 .4" pos=".036 0 .2" friction="0 0 0"/>' if side else ''
    pairs = '<contact><pair geom1="target_g" geom2="left_g"/><pair geom1="target_g" geom2="right_g"/></contact>' if explicit else ''
    xml=f'''<mujoco><option timestep=".001"/><worldbody>{table}{wall}
    <body name="robot"><joint name="arm_x" type="slide" axis="1 0 0"/><geom type="sphere" size=".01" pos="0 1 .2" contype="0" conaffinity="0"/>
      <body name="gripper"><geom name="palm" type="box" size=".01 .01 .01" pos="0 0 .23"/>
      <body name="left"><geom name="left_g" type="box" size=".005 .03 .04" pos="-.029 0 .15"/></body>
      <body name="right"><geom name="right_g" type="box" size=".005 .03 .04" pos=".029 0 .15"/></body></body></body>
    <body name="target" pos="0 0 .15"><freejoint/><geom name="target_g" type="box" size=".025 .02 .025" mass=".1"/></body>
    </worldbody>{pairs}</mujoco>'''
    model=mujoco.MjModel.from_xml_string(xml); data=mujoco.MjData(model);mujoco.mj_forward(model,data)
    ids={name:mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,name) for name in ('target','robot','gripper')}
    target_bodies=descendants(model,ids['target']); grip_bodies=descendants(model,ids['gripper'])
    spec=int(mujoco.mjtState.mjSTATE_INTEGRATION); state=np.empty(mujoco.mj_stateSize(model,spec));mujoco.mj_getState(model,data,state,spec)
    metadata={'state_spec':spec,'target_root_body_id':ids['target'],'robot_root_body_id':ids['robot'],'gripper_root_body_ids':[ids['gripper']],
              'target_geom_ids':[i for i in range(model.ngeom) if model.geom_bodyid[i] in target_bodies],
              'gripper_geom_ids':[i for i in range(model.ngeom) if model.geom_bodyid[i] in grip_bodies],
              'target_body_ids':target_bodies,'robot_body_ids':descendants(model,ids['robot']),
              'robot_qpos_ids':[0], 'robot_dof_ids':[0], 'target_free_dof_ids':list(range(1,7)),
              'complete_gripper_geometry':True,'unserialised_callback_present':False}
    return model,data,state,metadata


@pytest.mark.parametrize('support,side,expected',[(False,False,False),(True,False,True),(False,True,False)])
def test_counterfactual_keeps_external_support_and_incidental_contact(support,side,expected):
    model,data,state,meta=scene(support=support,side=side)
    original=data.qpos.copy(); masks=model.geom_contype.copy(); cb=mujoco.get_mjcb_contactfilter()
    result=evaluate(model,state,meta)
    assert result['status']=='known',result
    assert result['value'] is expected,result
    assert result['duration_s']>=.5
    assert result['target_gripper_contacts_after_removal']==0
    assert np.array_equal(data.qpos,original)
    assert np.array_equal(model.geom_contype,masks)
    assert mujoco.get_mjcb_contactfilter() is cb


def test_explicit_pairs_are_removed_and_model_restored():
    model,data,state,meta=scene(explicit=True); margin=model.pair_margin.copy()
    result=evaluate(model,state,meta)
    assert result['value'] is False,result
    assert len(result['removed_explicit_pair_ids'])==2
    assert result['target_gripper_contacts_after_removal']==0
    assert np.array_equal(model.pair_margin,margin)


def test_incomplete_state_geometry_and_callbacks_stay_unknown():
    model,data,state,meta=scene()
    assert evaluate(model,state[:-1],meta)['value'] is None
    bad=copy.deepcopy(meta);bad['gripper_geom_ids']=bad['gripper_geom_ids'][:-1]
    assert evaluate(model,state,bad)['reason']=='incomplete_target_or_gripper_subtree_geometry'
    bad=copy.deepcopy(meta);bad['unserialised_callback_present']=True
    assert evaluate(model,state,bad)['value'] is None


def test_native_collision_bitmasks_are_preserved():
    model,data,state,meta=scene()
    for a in range(model.ngeom):
        for b in range(model.ngeom):
            assert default_mask_filter(model,a,b)==(not ((model.geom_contype[a]&model.geom_conaffinity[b]) or (model.geom_contype[b]&model.geom_conaffinity[a])))


def test_mass_weighted_com_uses_inertial_centres_including_children():
    model=mujoco.MjModel.from_xml_string('''<mujoco><worldbody><body name="obj"><freejoint/><geom type="sphere" size=".01" mass="1" pos=".1 0 0"/>
    <body pos=".5 0 0"><geom type="sphere" size=".01" mass="3"/></body></body></worldbody></mujoco>''')
    data=mujoco.MjData(model);mujoco.mj_forward(model,data)
    com=mass_weighted_com(model,data,descendants(model,1))
    assert com[0]==pytest.approx(.4)
    assert com[0]!=data.xpos[1,0]


def test_isolated_worker_uses_complete_state_and_matching_model(tmp_path):
    model,data,state,meta=scene(explicit=True)
    mjb=tmp_path/'model.mjb';mujoco.mj_saveModel(model,str(mjb))
    states=tmp_path/'states.npz';np.savez(states,states=[state])
    output=tmp_path/'result.json';packet=tmp_path/'packet.json'
    packet.write_text(json.dumps({'model_path':str(mjb),'model_sha256':hashlib.sha256(mjb.read_bytes()).hexdigest(),
        'states_path':str(states),'metadata':meta,'output_path':str(output)}))
    worker=Path(__file__).parents[4]/'robots/libero/v5_grasp_support_worker.py'
    before=state.copy(); cb=mujoco.get_mjcb_contactfilter()
    run=subprocess.run([sys.executable,str(worker),str(packet)],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    result=json.loads(output.read_text())[0]
    assert result['value'] is False and result['worker_pid']!=os.getpid()
    assert result['integration_state_sha256']==hashlib.sha256(state.astype('<f8').tobytes()).hexdigest()
    after=np.empty(len(state));mujoco.mj_getState(model,data,after,meta['state_spec'])
    assert np.array_equal(before,after) and mujoco.get_mjcb_contactfilter() is cb


def samples(offset=0):
    evidence={'version':'isolated-target-gripper-removal/1','registration_id':'grasp_truth_v3_1153_20261009','status':'known',
              'model_sha256':'x','integration_state_sha256':'y','native_collision_masks_preserved':True,
              'pair_coverage_complete':True,'target_gripper_contacts_after_removal':0,
              'max_robot_drift_m':0,'max_robot_angle_drift_rad':0,'value':False}
    return [{'sim_time':i*.05,'lower_extent_m':.1,'dual_finger_contact':True,'relative_com_tcp':[offset,0,0],
             'counterfactual_load_bearing_support':False,'counterfactual_support_evidence':copy.deepcopy(evidence)} for i in range(11)]


REF={'lower_extent_m':0,'original_support_plane_z_m':0,'original_support_plane_evidence':{'source':'synthetic_plane','support_geom_ids':['floor']}}

def test_registered_hold_requires_plane_and_rejects_old_counterfactual():
    good=samples();assert sustained_grasp_v3(good,REF)['success'] is True
    assert sustained_grasp_v3(good,{'lower_extent_m':0})['success'] is None
    for s in good:s['counterfactual_support_evidence']['version']='old-live-process-removal'
    assert sustained_grasp_v3(good,REF)['success'] is None


def test_window_reference_resets_and_known_failed_window_is_false():
    bad=samples();bad[0]['dual_finger_contact']=False
    assert sustained_grasp_v3(bad,REF)['success'] is False
    trace=bad+[{**s,'sim_time':s['sim_time']+.55} for s in samples(.1)]
    assert grasp_trace_summary_v3(REF,trace)['true_sustained_grasp_during_skill'] is True
    assert grasp_trace_summary_v3(REF,bad)['true_sustained_grasp_during_skill'] is False


def test_repeated_or_gapped_samples_cannot_establish_hold():
    rows=samples();rows[5]['sim_time']=rows[4]['sim_time']
    assert sustained_grasp_v3(rows,REF)['success'] is None
    rows=samples();rows[-1]['sim_time']=.6
    assert sustained_grasp_v3(rows,REF)['success'] is None


def test_batch_archives_matching_model_without_changing_parent(tmp_path,monkeypatch):
    from types import SimpleNamespace as NS
    from robots.libero.v5_grasp_truth import _counterfactual_batch
    model,data,state,meta=scene(explicit=True)
    robot=NS(robot_model=NS(root_body='robot'),gripper=NS(root_body='gripper'))
    env=NS(objects_dict={'target':object()},obj_body_id={'target':meta['target_root_body_id']},robots=[robot],
           sim=NS(model=NS(_model=model),data=NS(_data=data)))
    monkeypatch.setenv('LIBERO_GRASP_DIAGNOSTIC_MODELS',str(tmp_path))
    results=_counterfactual_batch(env,'target',[state])
    assert len(results)==1 and results[0]['status']=='known',results
    assert results[0]['value'] is False
    assert Path(results[0]['model_path']).is_file()
    after=np.empty(len(state));mujoco.mj_getState(model,data,after,meta['state_spec'])
    assert np.array_equal(state,after)


def test_original_support_contact_plane_has_identity_and_no_origin_substitute():
    from types import SimpleNamespace as NS
    from robots.libero.v5_grasp_truth import contact_sample
    model,data,state,meta=scene(support=True)
    class Model:
        _model=model
        def __getattr__(self,name):return getattr(model,name)
        def geom_name2id(self,name):return mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_GEOM,name)
        def geom_id2name(self,i):return mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,i)
        def site_name2id(self,name):
            i=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_SITE,name)
            if i<0:raise KeyError(name)
            return i
    class Data:
        _data=data
        def __getattr__(self,name):return getattr(data,name)
    grip=NS(contact_geoms=['palm','left_g','right_g'],important_geoms={'left_finger':['left_g'],'right_finger':['right_g']})
    env=NS(sim=NS(model=Model(),data=Data()),objects_dict={'target':NS(contact_geoms=['target_g'])},
           obj_body_id={'target':meta['target_root_body_id']},robots=[NS(gripper=grip)],_check_grasp=lambda *args:False)
    ref=contact_sample(env,'target')
    assert ref['original_support_plane_z_m']==pytest.approx(.125,abs=.002),ref
    assert ref['original_support_plane_evidence']['support_geom_ids']==['table']
    assert 'relative_com_tcp' not in ref
    assert ref['support_proxy_source'].endswith('not_measured_plane')


def test_dual_finger_slip_and_load_bearing_support_fail_locked_predicate():
    rows=samples();rows[0]['dual_finger_contact']=False
    assert sustained_grasp_v3(rows,REF)['success'] is False
    rows=samples();rows[-1]['relative_com_tcp']=[.02,0,0]
    assert sustained_grasp_v3(rows,REF)['success'] is False
    rows=samples()
    for r in rows:
        r['counterfactual_load_bearing_support']=True;r['counterfactual_support_evidence']['value']=True
    assert sustained_grasp_v3(rows,REF)['success'] is False
