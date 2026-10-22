"""Locate sustained grasp before/after saved handoffs without policy or renderer."""
import copy
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys
from types import SimpleNamespace

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE=ROOT/'source_option_factor_6c1de614_20261022'
BASE=ROOT/'results/bounded_skills/execution_repairs_20261022'
OUT=BASE/'option_ceiling_20261022/CPU_handoff_private_r3'

def actions(value):
    if not isinstance(value,dict):return []
    trace=value.get('trace')
    if isinstance(trace,list) and trace and all('action' in r for r in trace):
        return [r['action'] for r in trace]
    result=[]
    for name in ('attempts','segments','motion','result'):
        children=value.get(name,[])
        if isinstance(children,dict):children=[children]
        if isinstance(children,list):
            for child in children:result+=actions(child)
    return result

def main():
    sys.path.insert(0,str(SOURCE))
    os.environ.update(CUDA_VISIBLE_DEVICES='',LIBERO_TYPE='pro',MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',
        LIBERO_CONFIG_PATH=str(ROOT/'runtime_config'),LIBERO_GRASP_DIAGNOSTIC_MODELS=str(OUT/'private_models'),
        PYTHONPATH=str(SOURCE),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    import robots.libero.env_server
    import rlinf.envs.libero.libero_env
    import numpy as np
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero.v5_branch_state import restore_actuators
    from robots.libero.v5_grasp_truth import contact_sample,measure_hold,_tcp_pose
    old=BASE/'D2_option_fallback_a3c7cf43/CPU_closed120_selected_paths/explanations/rows.json'
    gaps=json.loads(old.read_bytes())['rows'];rows=[]
    replay_checks=json.loads((BASE/'option_ceiling_20261022/CPU_handoff_endpoint_replay_r2.json').read_bytes())
    OUT.mkdir(exist_ok=False)
    for gap_index,gap in enumerate(gaps):
        if gap['classification']!='handoff_completion_not_retained':continue
        source=Path(gap['replay_summary']['path']);summary=json.loads(source.read_bytes())
        # The raw independent replay branch is still in the original summary.
        replay=summary['full_replay']
        target=next(i for i,r in enumerate(replay) if r['success'] is False)
        branch=replay[target]
        start_ref=(replay[target-1]['endpoint'] if target else
            {'path':str(source.parent/'episode/private_initial.pkl')})
        start=pickle.loads(Path(start_ref['path']).read_bytes())['physics']
        commands=[];chosen=None
        for line in Path(branch['choices']['path']).open():
            record=json.loads(line)
            for detail in record.get('execution_details',[]):
                e=detail.get('execution',{})
                if 'skill_stop_reason' not in e:continue
                commands+=actions(e.get('preparation',{}))
                commands+=actions(e)
                if e.get('stop_reason')=='completion_lost_during_handoff':
                    chosen=e;break
                commands+=actions(e.get('handoff',{}))
                commands+=actions(e.get('verification_motion',{}))
            if chosen is not None:break
        if chosen is None:
            rows.append({'case':gap['case'],'budget':gap['recovery_budget'],'status':'no_saved_completion_lost_execution','source':str(source)});continue
        env=ControlEnv(bddl_file_name=summary['case']['bddl']['path'],use_camera_obs=False,
            has_renderer=False,has_offscreen_renderer=False,camera_names=[],ignore_done=True,horizon=10015)
        def restore():
            env.set_init_state(start['sim_state']);state=copy.deepcopy(start['actuator_state']);state.pop('observation_state',None);restore_actuators(env,state)
        try:
            env.reset();restore();reference=contact_sample(env.env,branch['subtask']['source_symbol'])
            observation=None
            for a in commands:observation=env.step(np.asarray(a))[0]
            expected=chosen['trace'][-1]['after']['eef_xyz_m']
            # Compare the same public observation phase. Native site_xpos
            # can be a different mj_step phase than the returned sensor cache.
            measured=np.asarray(observation['robot0_eef_pos'])
            residual=float(np.max(np.abs(measured-expected)))
            verification=next(r for r in replay_checks if r['case']==gap['case'] and r['budget']==gap['recovery_budget'])
            if not (verification['endpoint_byte_identical'] and verification['native_data_byte_identical']
                    and verification['expected_controls']==verification['reconstructed_controls']):
                raise ValueError('full recorded physics replay did not match exactly')
            pre=measure_hold(env,branch['subtask']['source_symbol'],reference)
            restore()
            for a in commands:env.step(np.asarray(a))
            handoff=actions(chosen.get('handoff',{}))
            for a in handoff:env.step(np.asarray(a))
            post=measure_hold(env,branch['subtask']['source_symbol'],reference)
            result={'case':gap['case'],'budget':gap['recovery_budget'],'status':'physical_CPU_private_diagnostic',
                'cached_sensor_phase_residual_m':residual,'complete_replay_endpoint_and_native_data_byte_identical':True,
                'prefix_controls':len(commands),'handoff_controls':len(handoff),
                'before_handoff_truth_v3':pre['truth_v3'],'after_handoff_truth_v3':post['truth_v3'],
                'before_dual_contact_samples':sum(s['dual_finger_contact'] for s in pre['samples']),
                'after_dual_contact_samples':sum(s['dual_finger_contact'] for s in post['samples']),
                'scope':'camera/observation buffers omitted only in renderer-free private replay; no public policy input, threshold change or historical rescore'}
            (OUT/f'{gap_index:02d}_private.json').write_text(json.dumps({'before':pre,'after':post},indent=2)+'\n');rows.append(result)
        finally:env.close()
    (OUT/'summary.json').write_text(json.dumps({'rows':rows,'GPU_used':False,'model_calls':0,'training':False,'historical_rescore':False},indent=2)+'\n')
    print(json.dumps(rows))

if __name__=='__main__':main()
