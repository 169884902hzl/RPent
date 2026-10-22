"""Check physical endpoint identity before interpreting renderer-free metrology."""
import copy,json,os,pickle,sys
from pathlib import Path
ROOT=Path('/public/home/sunyihan/rpent_libero_eval');SOURCE=ROOT/'source_option_factor_6c1de614_20261022';sys.path.insert(0,str(SOURCE))
os.environ.update(LIBERO_TYPE='pro',MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',LIBERO_CONFIG_PATH=str(ROOT/'runtime_config'),OPENBLAS_NUM_THREADS='1')
import robots.libero.env_server
import rlinf.envs.libero.libero_env
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.v5_branch_state import restore_actuators, native_data_state
from replay_handoff_private_CPU_20261022 import actions
BASE=ROOT/'results/bounded_skills/execution_repairs_20261022/D2_option_fallback_a3c7cf43'
rows=[]
for gap in json.loads((BASE/'CPU_closed120_selected_paths/explanations/rows.json').read_bytes())['rows']:
 if gap['classification']!='handoff_completion_not_retained':continue
 summary=json.loads(Path(gap['replay_summary']['path']).read_bytes());rs=summary['full_replay'];i=next(i for i,t in enumerate(rs) if t['success'] is False);trial=rs[i]
 initial=pickle.loads(Path(rs[i-1]['endpoint']['path'] if i else str(Path(gap['replay_summary']['path']).parent/'episode/private_initial.pkl')).read_bytes())['physics']
 endpoint=pickle.loads(Path(trial['endpoint']['path']).read_bytes())['physics'];controls=[]
 for line in Path(trial['choices']['path']).open():
  for detail in json.loads(line)['execution_details']:
   e=detail.get('execution',{})
   if 'skill_stop_reason' not in e:continue
   controls+=actions(e.get('preparation',{}))+actions(e)+actions(e.get('handoff',{}))+actions(e.get('verification_motion',{}))
 env=ControlEnv(bddl_file_name=summary['case']['bddl']['path'],use_camera_obs=False,has_renderer=False,has_offscreen_renderer=False,camera_names=[],ignore_done=True,horizon=10015)
 try:
  env.reset();env.set_init_state(initial['sim_state']);state=copy.deepcopy(initial['actuator_state']);state.pop('observation_state',None);restore_actuators(env,state)
  for a in controls:env.step(np.asarray(a))
  actual=env.sim.get_state().flatten();expected=np.asarray(endpoint['sim_state'])
  rows.append({'case':gap['case'],'budget':gap['recovery_budget'],'expected_controls':trial['sim_steps'],'reconstructed_controls':len(controls),
   'endpoint_max_residual':float(np.max(np.abs(actual-expected))),'endpoint_byte_identical':actual.tobytes()==expected.tobytes(),
   'native_data_byte_identical':native_data_state(env)['sha256']==endpoint['actuator_state']['native_data']['sha256']})
 finally:env.close()
out=ROOT/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022/CPU_handoff_endpoint_replay_r2.json';out.write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows))
