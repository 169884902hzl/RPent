"""Same-state, one-factor A1 comparisons. Evaluation only, never labels."""
from contextlib import contextmanager
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import pickle
import time

from rpent.skill_package.vla import VLABudget
from scripts import probe_bounded_hybrid_d2 as probe


class PromptOverride:
    """Change only the policy's language field and record the actual wire input."""
    def __init__(self, client, prompt):
        self.client, self.prompt = client, prompt

    def observation(self, obs):
        return {**obs, 'task_descriptions': self.prompt}

    def encode_obs(self, obs):
        return self.client.encode_obs(self.observation(obs))

    def predict(self, obs, options=None):
        return self.client.predict(self.observation(obs), options=options)


def factor_budget(factor, baseline, a1_parameters):
    """The primitive contrast shares the exact budget-only arm's limits."""
    if factor in {'a1_budget_only', 'a1_primitive'}:
        return VLABudget(**{**baseline, 'blocks': a1_parameters['max_chunks'],
            'no_progress_blocks': None, 'max_controls': None})
    return VLABudget(**baseline)


def execution_prompt(trial):
    for line in Path(trial['choices']['path']).open():
        for detail in json.loads(line).get('execution_details', []):
            template=detail.get('execution', {}).get('template')
            if template is not None:
                return template['prompt']
    return None


def private_score(facade, spec, reference):
    native=facade.goal_status()
    if reference is not None:
        truth=facade.measure_grasp_hold(spec['source_symbol'], reference)
        success=truth['truth_v3']['success']
    else:
        truth=native
        success=native['satisfied'][spec['goal_index']]
    return {'private_subtask_success': success, 'native_task_success':bool(native['done']),
        'private_evidence':truth, 'model_visible':False}


def raw_primitive(facade, adapter, policy, spec, parameters, prompt, seed, budget, output):
    """Run the existing RPent primitive, with the budget-only arm's prompt/seed.

    Its contact/stop logic is the changed factor. No A1 Cartesian waypoint or
    task-specific coordinate is injected; those require a separate bundle test.
    """
    output.mkdir()
    primitive=adapter.p
    before=primitive.env.execution_budget()['used_sim_steps']
    client, original_chunk=primitive.model, primitive._vlm_chunk
    seeded=probe.SeededPolicy(client, seed, input_ledger=output/'vla_inputs.jsonl')
    primitive.model=seeded
    trace=[]
    def chunk(instruction):
        return original_chunk(instruction, trace_callback=trace.append)
    primitive._vlm_chunk=chunk
    started=time.perf_counter()
    tool=parameters['tool']
    arguments={k:v for k,v in parameters['parameters'].items() if k!='prompt'}
    arguments['max_chunks']=budget.blocks
    try:
        result=getattr(primitive,tool)(prompt,**arguments)
        endpoint, endpoint_ref=probe.save_checkpoint(facade,adapter,policy,output/'private_endpoint.pkl')
    finally:
        primitive.model, primitive._vlm_chunk=client, original_chunk
    steps=int(endpoint['physics']['counters']['_elapsed_steps'])-before
    probe.write(output/'primitive.json',{'tool':tool,'parameters':{'prompt':prompt,**arguments},
        'result':result,'trace':trace,'seed':seed,'budget':asdict(budget)})
    return {'method':'rpent_primitive','success':None,'sim_steps':steps,
        'vla_inference_calls':seeded.calls,'vla_inputs':seeded.inputs,
        'wall_s':time.perf_counter()-started,'reason':'native_success' if primitive.env.terminated
            else 'environment_budget' if primitive.env.truncated else 'primitive_return',
        'primitive_result':result,'endpoint':endpoint_ref},endpoint


def checked(reference):
    path=Path(reference['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest()!=reference['sha256']:
        raise ValueError('registered diagnostic input changed: '+str(path))
    return path


def run_case(row, plan, endpoints, output, *, startup=False):
    if not plan['evaluation_only'] or plan['training'] or plan['confirmation']:
        raise ValueError('option-ceiling diagnostic is evaluation only')
    output.mkdir()
    saved=pickle.loads(checked(row['branchpoint']).read_bytes())
    if saved['physics']['actuator_state'].get('integration') is None:
        raise ValueError('factor comparison requires complete integration state')
    spec=row['subtask']
    expected=probe.snapshot_digest(saved['physics'])
    trials=[]
    with probe.runtime(row['case'],endpoints,output,domain='d2') as (facade,adapter,policy,timings):
        for factor in (['baseline'] if startup else
                ['baseline','a1_prompt_only','a1_budget_only','a1_primitive']):
            for repeat in ([0] if startup else range(3)):
                probe.restore_checkpoint(facade,adapter,policy,saved)
                actual=probe.snapshot_digest(facade.snapshot())
                if actual!=expected:
                    raise ValueError('factor arm did not restore the same complete initial state')
                request=copy.deepcopy(saved['request'])
                budget=factor_budget(factor,row['budget'],row['a1_pi']['parameters'])
                adapter.vla_budget=budget
                adapter.hybrid_recovery_budget=0
                reference=(facade.grasp_reference(spec['source_symbol']) if spec['mode']=='pick' else None)
                seed=row['trial_seed_base']+repeat*1000
                directory=output/f'{factor}_{repeat}'
                original_model=adapter.p.model
                if factor=='a1_prompt_only':
                    adapter.p.model=PromptOverride(original_model,row['a1_pi']['parameters']['prompt'])
                try:
                    if factor=='a1_primitive':
                        result,endpoint=raw_primitive(facade,adapter,policy,spec,row['a1_pi'],
                            row['baseline_prompt'],seed,budget,directory)
                    else:
                        result,endpoint=probe.trial(facade,adapter,policy,timings,spec,'call_vla',seed,
                            directory,request,vla_parameters={'preparation':'in_place'},
                            decision_limit=1)
                    # trial's diagnostic hold window steps physics. Score the
                    # saved endpoint again, never its post-metrology successor.
                    probe.restore_checkpoint(facade,adapter,policy,endpoint)
                    score=private_score(facade,spec,reference)
                finally:
                    adapter.p.model=original_model
                result.update(factor=factor,repeat=repeat,trial_seed=seed,
                    complete_initial_sha256=actual,budget=asdict(budget),**score)
                probe.write(directory/'factor_result.json',result)
                trials.append(result)
        result={'case':row['case'],'status':'startup_physical' if startup else 'physical_result',
            'evaluation':'A1_one_factor_option_ceiling','source_commit':plan['source_commit'],
            'subtask':spec,'trials':trials,'initial_physics_sha256':expected,
            'all_complete_initial_hashes_match':all(t['complete_initial_sha256']==expected for t in trials),
            'contrasts':{'a1_prompt_only':'baseline, language only',
                'a1_budget_only':'baseline, A1 per-call block budget and no early progress abort',
                'a1_primitive':'a1_budget_only, existing RPent primitive contact/stop logic only'},
            'baseline_prompt':row['baseline_prompt'],'A1_pi_call':row['a1_pi'],
            'A1_complete_initial_certified':False,'training':False,'confirmation':False,
            'wall_time_breakdown':timings.summary(time.perf_counter()-timings.started)}
        if startup and not any(t['sim_steps'] and t['vla_inference_calls'] for t in trials):
            raise RuntimeError('factor startup did not execute a real policy control')
        probe.write(output/'summary.json',result)
        return result
