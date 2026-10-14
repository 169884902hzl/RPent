from types import SimpleNamespace as NS
import numpy as np
from robots.libero.tools import LiberoPrimitives
from robots.libero.v5_runtime import V5Executor


def test_pick_anchor_is_observed_bottom_pose_without_changing_pick_controls():
    poses=[(.7,.079),(.55,.04),(.62,.04)]
    actor=NS(_last_obs_eef_z=.8,_last_obs_eef_pos=np.array([0.,0.,.8]),_last_obs_gripper=.079,
             env=NS(terminated=False,truncated=False,raw_obs=lambda:{'robot0_eef_quat':np.array([1.,0.,0.,0.])}))
    calls=[]
    def chunk(prompt):
        z,grip=poses[len(calls)];calls.append(prompt)
        actor._last_obs_eef_z=z;actor._last_obs_eef_pos=np.array([.1,.2,z]);actor._last_obs_gripper=grip
    actor._vlm_chunk=chunk
    result=LiberoPrimitives.pi0_pick(actor,'pick up the bottle',max_chunks=10)
    assert result['success'] is True and result['chunks_used']==3
    assert calls==['pick up the bottle']*3
    assert result['measured_contact_anchor']['eef_xyz']==[.1,.2,.55]
    assert result['measured_contact_anchor']['eef_quat_xyzw']==[1.,0.,0.,0.]
    assert result['measured_contact_anchor']['is_success_evidence'] is False


def test_category_profile_passes_actual_contact_anchor_to_public_verifier():
    obj=NS(id='e1',name='wine bottle',xyz=(.1,.2,.8),lower=(.08,.18,.7),upper=(.12,.22,.9),visible=True)
    primitive={'chunks_used':4,'measured_contact_anchor':{'source':'robot_proprioception_at_minimum_pick_height','eef_xyz':[.1,.2,.81],'eef_quat_xyzw':[1.,0.,0.,0.]}}
    p=NS(pi0_pick=lambda *a,**k:primitive,_last_obs_eef_pos=np.array([.1,.2,1.]),_last_obs_gripper=.04)
    fake=NS(p=p,instruction='put the wine bottle on the rack',grasp_public_tracking_v1=True,
            grasp_public_coupled_lift_v1=True,grasp_public_closing_xyz=None,
            stage_category_start=lambda *a:True,_refresh=lambda *a:None,scene=NS(entities={'e1':obj}))
    def verify(source):
        assert np.array_equal(fake.grasp_public_closing_xyz,[.1,.2,.81])
        assert np.array_equal(fake.grasp_public_closing_quat,[1.,0.,0.,0.])
        return True
    fake.verify_grasp_measurement=verify
    receipt={};V5Executor.execute_category_grasp(fake,obj,'C',receipt)
    assert receipt['grasp_verified'] is True
    assert receipt['public_contact_anchor'] is primitive['measured_contact_anchor']
