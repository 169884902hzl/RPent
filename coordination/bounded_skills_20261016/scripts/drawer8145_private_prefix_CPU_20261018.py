"""Inspect saved drawer contacts/joints; no control or model-visible labels."""
# ruff: noqa: E402 -- CPU and immutable source before simulator imports
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root=Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0,str(root/'source_bounded_bc160ff_20261018'))
import mujoco
import numpy as np
from libero.libero.envs.bddl_utils import robosuite_parse_problem
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

base=root/'results/bounded_skills/feasibility_20261017'
p=next((base/'job8145_100').glob('*oracle*/choices.jsonl'))
captured=p.read_bytes()
rows=[json.loads(line) for line in captured.splitlines()]
plan=json.loads((base/'preparation/original20_manifest_bc160ff_held_nudge.json').read_text())
case=next(c for c in plan['cases'] if c['name']+'_oracle_k4'==p.parent.name)
goals=robosuite_parse_problem(case['bddl']['path'])['goal_state']
env=ControlEnv(bddl_file_name=case['bddl']['path'],use_camera_obs=False,
    has_renderer=False,has_offscreen_renderer=False,camera_names=[],ignore_done=True,horizon=10015)
attach_reset_seed(env)
env.seed(0)
env.reset()
results=[]
try:
    for row in rows:
        if 'private_pre_execution_snapshot' not in row:
            continue
        ref=row['private_pre_execution_snapshot'];raw=Path(ref['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==ref['sha256']
        saved=pickle.loads(raw)
        env.set_init_state(saved['sim_state'])
        restore_actuators(env,saved['actuator_state'])
        sim=env.env.sim
        residual=float(np.max(np.abs(sim.get_state().flatten()-saved['sim_state'])))
        assert residual<1e-8
        model=sim.model._model
        contacts=[]
        for i,c in enumerate(sim.data.contact[:sim.data.ncon]):
            names=[mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,int(g)) for g in (c.geom1,c.geom2)]
            if any(n and ('finger' in n or 'hand' in n) for n in names):
                force=np.zeros(6);mujoco.mj_contactForce(model,sim.data._data,i,force)
                contacts.append({'geoms':names,
                    'bodies':[sim.model.body_id2name(int(sim.model.geom_bodyid[g])) for g in (c.geom1,c.geom2)],
                    'force_contact_frame':force.tolist(),'distance_m':float(c.dist)})
        joints={name:{'qpos':float(sim.data.qpos[sim.model.jnt_qposadr[i]]),
            'range':np.asarray(sim.model.jnt_range[i]).tolist()}
            for i,name in enumerate(sim.model.joint_names) if name and any(token in name for token in ('drawer','cabinet'))}
        selected=[c for c in row['request']['candidates'] if c['id'] in row['decision']['candidate_ids']]
        results.append({'row':row['index'],'snapshot':ref,'restore_residual':residual,
            'private_joints':joints,'private_contacts':contacts,
            'private_goals':[{'goal':g,'satisfied':bool(env.env._eval_predicate(g))} for g in goals],
            'public_robot':row['request']['robot'],
            'chosen':[{'skill':c['skill'],'parameters':c['parameters']} for c in selected],
            'receipts':[{k:r[k] for k in ('skill','outcome','stop_reason','steps_used')} for r in row['receipts']]})
finally:
    env.close()
output=root/'coordination/bounded_skills_20261016/reports/drawer8145_private_prefix_CPU_20261018.json'
output.write_text(json.dumps({'scope':'saved original-scene private prefix diagnosis;zero controls',
    'gpu_used':False,'training':False,'model_visible':False,'used_for_control':False,
    'choices_prefix_sha256':hashlib.sha256(captured).hexdigest(),'choices_captured_bytes':len(captured),
    'case':case,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'rows':results},indent=2)+'\n')
for r in results:
    print(json.dumps({k:v for k,v in r.items() if k not in ('snapshot','public_robot')},separators=(',',':')),flush=True)
