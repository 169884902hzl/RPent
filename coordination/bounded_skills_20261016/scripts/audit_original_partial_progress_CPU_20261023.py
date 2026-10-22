"""Check failed original-task endpoints for already completed registered goals."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
BASE=ROOT/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'


def ref(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.source))
    os.environ.update(CUDA_VISIBLE_DEVICES='',LIBERO_TYPE='standard',MUJOCO_GL='egl',
        PYOPENGL_PLATFORM='egl',LIBERO_CONFIG_PATH=str(ROOT/'runtime_config_original_20261023'),
        OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    import robots.libero.env_server
    import rlinf.envs.libero.libero_env
    from libero.libero.envs.env_wrapper import ControlEnv
    from libero.libero.envs.bddl_utils import robosuite_parse_problem
    from robots.libero.v5_branch_state import restore_actuators,native_data_state

    paths=[]
    for shard in range(2):
        paths.extend((BASE/f'original_selfcheck/shard{shard}').glob('closed_*.json'))
        paths.extend((BASE/f'regression155_f6987f0d/shard{shard}').glob('closed_*.json'))
    pending=[]
    for pointer in paths:
        raw=Path(json.loads(pointer.read_bytes())['summary']);summary=json.loads(raw.read_bytes())
        case=summary['case']
        if case['episode']['suite'] not in {'libero_spatial','libero_object','libero_goal','libero_10','libero_90'}:
            continue
        if 'own_layout' in case.get('diagnostic',{}):continue
        goals=robosuite_parse_problem(case['bddl']['path'])['goal_state']
        if len(goals)<2:continue
        for trial in summary.get('trials',[]):
            task=trial.get('vla_variant',{}).get('parameters',{}).get('mode')=='task'
            if (trial['success'] is False and trial.get('native_task_success') is not True
                    and (task or trial['subtask']['mode']=='pick')):
                pending.append((case,trial,raw,goals))
    a.output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for case,trial,raw,goals in pending:
        endpoint=Path(trial['endpoint']['path'])
        assert ref(endpoint)['sha256']==trial['endpoint']['sha256']
        saved=pickle.loads(endpoint.read_bytes());physics=saved['physics'];del saved
        env=ControlEnv(bddl_file_name=case['bddl']['path'],use_camera_obs=False,
            has_renderer=False,has_offscreen_renderer=False,camera_names=[],ignore_done=True,horizon=10015)
        try:
            env.reset();env.set_init_state(physics['sim_state'])
            state=copy.deepcopy(physics['actuator_state']);state.pop('observation_state',None)
            restore_actuators(env,state)
            expected=physics['actuator_state']['native_data']['sha256']
            assert native_data_state(env)['sha256']==expected
            values=[bool(env.env._eval_predicate(goal)) for goal in goals]
            assert native_data_state(env)['sha256']==expected
            index=trial['subtask']['goal_index']
            row={'case':case['name'],'episode':case['episode'],'method':trial['method'],
                'variant':trial.get('vla_variant'),'seed':trial['trial_seed'],
                'registered_goal_index':index,'goals':goals,'satisfied':values,
                'requested_goal_satisfied':values[index],'native_complete':all(values),
                'recorded_local_success':trial['success'],'recorded_reason':trial['reason'],
                'truth_source':trial.get('truth_source'),'endpoint':trial['endpoint'],
                'parent_summary':ref(raw),'native_data_byte_identical':True,
                'physics_controls_after_restore':0}
            rows.append(row)
            with (a.output/'rows.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
            print(json.dumps({k:row[k] for k in ('case','variant','seed','requested_goal_satisfied','native_complete')}),flush=True)
        finally:env.close()
        del physics,state
    result={'original_failed_endpoints':len(rows),
        'registered_goal_complete_local_false':sum(r['requested_goal_satisfied'] for r in rows),
        'partial_registered_goal_complete':sum(r['requested_goal_satisfied'] and not r['native_complete'] for r in rows),
        'rows':ref(a.output/'rows.jsonl') if rows else None,'PRO':False,'D2':False,
        'confirmation':False,'training':False,'old_scores_changed':False,
        'scope':'CPU predicate replay of original endpoints; no controls after exact native-state restore'}
    (a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
