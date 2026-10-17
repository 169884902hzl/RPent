"""Public planned contact comparison; private contact labels never control either branch."""
from pathlib import Path
from types import SimpleNamespace
import hashlib,json,os,pickle,runpy,sys
os.environ.update(CUDA_VISIBLE_DEVICES='',OPENBLAS_NUM_THREADS='1',LIBERO_TYPE='standard')
root=Path('/public/home/sunyihan/rpent_libero_eval');prep=root/'results/bounded_skills/feasibility_20261017/preparation'
ns=runpy.run_path(str(prep/'box8071_sparse_production_route_CPU_20261018.py'))
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.bounded_motion import SmoothMotion,measured_robot,public_control
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_self_filter import gripper_at_measured_fingers
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_grasp_truth import contact_sample
from robots.libero.v5_reset_seed import attach_reset_seed
path,row,diag,geometry,xml=ns['p'],ns['row'],ns['diag'],ns['adapter'].geometry,ns['xml']
base_screen=ns['screen'];saved_ref=row['private_pre_execution_snapshot'];raw=Path(saved_ref['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==saved_ref['sha256'];saved=pickle.loads(raw)
manifest=json.loads((prep/'original20_manifest_cee33e8_calibrated.json').read_text()); case=next(c for c in manifest['cases'] if c['name']==path.parent.name.removesuffix('_oracle_k4')); episode={'case':case}
robot_keys=('robot0_eef_pos','robot0_eef_quat','robot0_gripper_qpos','robot0_joint_pos')
class PublicPrimitives:
    def __init__(self,env,obs):
        self.simulator=env;self.obs={k:obs[k] for k in robot_keys};self.truth=[]
        self.env=SimpleNamespace(raw_obs=lambda:self.obs,terminated=False,truncated=False)
    def _step_env(self,action):
        obs,_,_,_=self.simulator.step(np.asarray(action,dtype=np.float32));self.obs={k:obs[k] for k in robot_keys}
        self.truth.append(contact_sample(self.simulator.env,'alphabet_soup_1'))
    def screen(self,contact=False):
        robot=measured_robot(self)
        ik=PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',robot['joint_positions_rad'],robot['eef_xyz_m'],robot['eef_quat_xyzw'],geometry['site_offset_in_gripper_m'],warm_start=True)
        return PublicRouteScreen(base_screen.points,gripper_at_measured_fingers(geometry,robot['finger_positions_m']),ik,opening=robot['gripper_opening_m'],contact_points=base_screen.target,contact_allowed=contact,initial_pose={'xyz_m':robot['eef_xyz_m'],'quat_xyzw':robot['eef_quat_xyzw']})
results=[]
for candidate_id in ('s7_a0_oblique_-1','s0_a0_side_1_orient_at_pregrasp'):
    candidate=next(c for c in diag['candidates'] if c['id']==candidate_id)
    env=ControlEnv(bddl_file_name=episode['case']['bddl']['path'],use_camera_obs=False,has_renderer=False,has_offscreen_renderer=False,camera_names=[],ignore_done=True,horizon=10015)
    attach_reset_seed(env);env.seed(0);env.reset()
    try:
        env.set_init_state(saved['sim_state']);restore_actuators(env,saved['actuator_state']);obs=env.env._get_observations(force_update=True)
        flat_error=float(np.max(np.abs(env.env.sim.get_state().flatten()-saved['sim_state'])))
        p=PublicPrimitives(env,obs);start=measured_robot(p)
        phases=[]
        route=[{'xyz_m':w['xyz'],'quat_xyzw':w['body_quat_xyzw']} for w in candidate['route']]
        approach=SmoothMotion(p,p.screen(contact=True)).run(route,gripper=-1.)
        phases.append({'name':'approach','result':{k:v for k,v in approach.items() if k not in ('trace','screen')},'end_control':len(p.truth)})
        if approach.get('executed') and approach['stop_reason']=='endpoint' and approach['endpoint_error_m']<=.012:
            for _ in range(15):public_control(p,[0.,0.,0.,0.,0.,0.,1.])
            phases.append({'name':'close','end_control':len(p.truth),'opening_m':measured_robot(p)['gripper_opening_m']})
            robot=measured_robot(p);liftpoint=np.asarray(robot['eef_xyz_m'])+[0,0,.10]
            lift=SmoothMotion(p,p.screen(contact=True)).run([{'xyz_m':liftpoint.tolist(),'quat_xyzw':robot['eef_quat_xyzw']}],gripper=1.)
            phases.append({'name':'lift','result':{k:v for k,v in lift.items() if k not in ('trace','screen')},'end_control':len(p.truth)})
            if lift.get('executed') and lift['stop_reason']=='endpoint' and lift['endpoint_error_m']<=.012:
                robot=measured_robot(p);basket=next(a for a in row['request']['anchors'] if a['id']=='e98');source=next(a for a in row['request']['anchors'] if a['id']=='e99');direction=np.asarray(basket['xyz_m'])-source['xyz_m'];direction[2]=0.;direction=direction/np.linalg.norm(direction)*.20
                carrypoint=np.asarray(robot['eef_xyz_m'])+direction
                carry=SmoothMotion(p,p.screen(contact=False)).run([{'xyz_m':carrypoint.tolist(),'quat_xyzw':robot['eef_quat_xyzw']}],gripper=1.)
                phases.append({'name':'fixed_20cm_transport','result':{k:v for k,v in carry.items() if k not in ('trace','screen')},'end_control':len(p.truth)})
                for _ in range(20):public_control(p,[0.,0.,0.,0.,0.,0.,1.])
                phases.append({'name':'fixed_1s_hold','end_control':len(p.truth)})
        tail=p.truth[-20:]
        record={'candidate':candidate_id,'quality':candidate['antipodal_quality'],'flat_state_restore_error':flat_error,'initial_eef_record_error_m':float(np.linalg.norm(np.asarray(start['eef_xyz_m'])-row['request']['robot']['eef_xyz_m'])),'phases':phases,'controls':len(p.truth),'tail_samples':len(tail),'tail_dual_contact_count':sum(t['dual_finger_contact'] for t in tail),'tail_other_support_count':sum(bool(t['all_non_gripper_contact_geoms']) for t in tail),'tail_relative_com_range_m':np.ptp(np.array([t['relative_com_tcp'] for t in tail]),axis=0).tolist() if tail else None,'private_samples':p.truth}
        results.append(record);print(json.dumps({k:v for k,v in record.items() if k not in ('private_samples','phases')}),flush=True)
    finally:env.close()
report={'scope':'CPU same-snapshot public-planned opposition diagnostic; fixed approach/close/lift/20cm transport/1s hold, not full task or confirmation score','training_allowed':False,'gpu_used':False,'renderer_used':False,'private_labels_used_for_control':False,'source_base':'cee33e8','snapshot':saved_ref,'choices_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'execution_rules_unchanged':True,'results':results}
output=root/'coordination/bounded_skills_20261016/reports/box8071_opposition_physics_private_CPU_20261018.json';output.write_text(json.dumps(report,indent=2)+'\n')
