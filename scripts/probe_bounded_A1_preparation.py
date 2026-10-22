"""Paired A1 staging or placement-tail diagnostics, never runtime candidates."""
import copy
import hashlib
from pathlib import Path
import pickle
import time

from rpent.skill_package.vla import VLABudget
from scripts import probe_bounded_hybrid_d2 as probe
from scripts.probe_bounded_option_ceiling import checked, private_score

MOTION_TOOLS=frozenset({'move_to','move_pose','set_gripper','release','rotate_pitch'})


def motion_commands(calls, *, tail=False):
    """Retain actual motion calls around the recorded first pick, not prose."""
    first=next(i for i,c in enumerate(calls) if c['tool'].startswith('pi0_'))
    selected=calls[first+1:] if tail else calls[:first]
    # Tail experiments use the recorded scripted primitives only. A later
    # VLA call is a separate intervention, never silently inserted here.
    return [{'tool':c['tool'],'parameters':copy.deepcopy(c['parameters'])}
        for c in selected if c['tool'] in MOTION_TOOLS]


def execute_motion(primitives, commands):
    """Use existing RPent implementations and keep every actual control."""
    from robots.libero.bounded_motion import measured_robot
    trace=[];original=primitives._step_env
    def step(action):
        before=measured_robot(primitives)
        original(action)
        trace.append({'action':list(map(float,action)),'before':before,
            'after':measured_robot(primitives)})
    primitives._step_env=step
    results=[]
    try:
        for command in commands:
            if command['tool'] not in MOTION_TOOLS:
                raise ValueError('diagnostic accepts existing motion primitives only')
            if primitives.env.terminated or primitives.env.truncated:break
            result=getattr(primitives,command['tool'])(**command['parameters'])
            results.append({'command':command,'result':result})
    finally:
        primitives._step_env=original
    return {'commands':results,'trace':trace,'steps_used':len(trace)}


def run_case(row, plan, endpoints, output, *, startup=False):
    if not plan['evaluation_only'] or plan['training'] or plan['confirmation']:
        raise ValueError('A1 staging is evaluation only, not a task-specific runtime rule')
    output.mkdir()
    saved=pickle.loads(checked(row['branchpoint']).read_bytes());expected=probe.snapshot_digest(saved['physics'])
    spec=row['subtask'];tail=spec['mode'] in {'on','in'}
    commands=motion_commands(row['a1_physical_commands'],tail=tail)
    if tail and not commands:
        result={'case':row['case'],'status':'not_applicable','trials':[],
            'reason':'A1_has_no_scripted_placement_tail; its VLA call spans the task',
            'training':False,'confirmation':False,'source_commit':plan['source_commit']}
        probe.write(output/'summary.json',result)
        return result
    rows=[]
    with probe.runtime(row['case'],endpoints,output,domain='d2') as (facade,adapter,policy,timings):
        for arm in (['baseline'] if startup else ['baseline','a1_motion']):
            for repeat in ([0] if startup else range(3)):
                probe.restore_checkpoint(facade,adapter,policy,saved)
                actual=probe.snapshot_digest(facade.snapshot())
                if actual!=expected:raise ValueError('complete staging initial state changed')
                reference=(facade.grasp_reference(spec['source_symbol']) if spec['mode']=='pick' else None)
                before=adapter.p.env.execution_budget()['used_sim_steps'];started=time.perf_counter()
                directory=output/f'{arm}_{repeat}';directory.mkdir()
                adapter.vla_budget=VLABudget(**row['budget']);adapter.hybrid_recovery_budget=0
                motion=execute_motion(adapter.p,commands) if arm=='a1_motion' else {'steps_used':0,'trace':[],'commands':[]}
                probe.write(directory/'motion.json',motion)
                if tail and arm=='a1_motion':
                    result={'method':'A1_scripted_placement_tail','success':None,'vla_inference_calls':0}
                    endpoint,endpoint_ref=probe.save_checkpoint(facade,adapter,policy,directory/'private_endpoint.pkl')
                    result['endpoint']=endpoint_ref
                else:
                    # Both arms make a fresh measurement. The changed arm
                    # differs only by the recorded staging motion before it.
                    adapter._incremental_touched.update(adapter.scene.entities)
                    adapter.refresh()
                    with timings.measure('planning.request'):request=adapter.request(k=4)
                    result,endpoint=probe.trial(facade,adapter,policy,timings,spec,
                        'self' if tail else 'call_vla',row['trial_seed_base']+repeat*1000,
                        directory/'continuation',request,
                        **({} if tail else {'vla_parameters':{'preparation':'in_place'},'decision_limit':1}))
                probe.restore_checkpoint(facade,adapter,policy,endpoint)
                used=int(endpoint['physics']['counters']['_elapsed_steps'])-before
                score=private_score(facade,spec,reference)
                result.update(**score,arm=arm,repeat=repeat,complete_initial_sha256=actual,
                    total_sim_steps=used,staging_steps=motion['steps_used'],
                    wall_s=time.perf_counter()-started)
                probe.write(directory/'result.json',result);rows.append(result)
        report={'case':row['case'],'status':'startup_physical' if startup else 'physical_result',
            'source_commit':plan['source_commit'],'evaluation':'A1_staging_or_scripted_tail_pair',
            'subtask':spec,'tail':tail,'trials':rows,'A1_commands':commands,
            'all_complete_initial_hashes_match':all(r['complete_initial_sha256']==expected for r in rows),
            'training':False,'confirmation':False,'runtime_candidates_changed':False,
            'interpretation':'A1 recorded public Cartesian commands are an evaluation intervention, not a general learned/runtime skill or D2 training label'}
        if startup and not any(r['total_sim_steps']>0 for r in rows):
            raise RuntimeError('staging startup did not execute physics')
        probe.write(output/'summary.json',report);return report
