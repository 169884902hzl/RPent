"""Measure frozen model choices under their original execution/outcome binding."""
import copy
import hashlib
import json
from pathlib import Path
import pickle
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def checked(ref):
    path = Path(ref['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
        raise ValueError('registered evaluation artifact changed: '+str(path))
    return path


def frozen_choice_request(query, saved):
    """Use the full captured request; verify the service view's selected ID."""
    if query['training_admission'] or not query['evaluation_only']:
        raise ValueError('this interface only measures registered evaluation queries')
    if query['prefix']:
        raise ValueError('the registered on-policy pool contains only empty prefixes')
    if (query['binding']['prefix'] != query['prefix']
            or query['binding']['snapshot_sha256'] != query['snapshot']['sha256']):
        raise ValueError('frozen prefix/snapshot binding changed')
    request = saved['request']
    if digest(request) != query['binding']['request_sha256']:
        raise ValueError('captured request differs from the frozen outcome binding')
    if digest(query['outcome_contract']) != query['binding']['outcome_contract_sha256']:
        raise ValueError('registered outcome contract changed')
    original = next(c for c in request['candidates'] if c['id'] == query['candidate_id'])
    for key in ('id', 'skill', 'parameters'):
        if original[key] != query['candidate'][key]:
            raise ValueError('selected candidate differs from captured option: '+key)
    return copy.deepcopy(request), copy.deepcopy(original)


def evaluate_candidate_at_saved_state(query, probe, facade, adapter, policy, output, seed):
    """Force exactly the selected option; only self actions get oracle continuation.

    ``probe`` and the live adapter must come from the query's original source.
    The caller owns simulator/services and restores this same checkpoint for
    every repeat. No replacement context or private progress is model input.
    """
    from robots.libero.bounded_oracle import NoPublicOption
    from rpent.skill_package.contract import legal_after
    from rpent.skill_package.vla import VLABudget

    source = Path(probe.__file__).resolve().parents[1]
    revision = json.loads((source/'SOURCE_REVISION.json').read_bytes())['commit']
    if revision != query['binding']['source_revision']:
        raise ValueError('frozen labels require their original execution source')
    checked(query['outcome_contract']['truth_code'])
    saved = pickle.loads(checked(query['snapshot']).read_bytes())
    request, candidate = frozen_choice_request(query, saved)
    probe.restore_checkpoint(facade, adapter, policy, saved)
    initial = probe.snapshot_digest(facade.snapshot())
    if initial != probe.snapshot_digest(saved['physics']):
        raise ValueError('complete saved state did not restore exactly')
    if digest(adapter.latest_request) != digest(request):
        raise ValueError('restored public execution cache differs from captured request')
    adapter.latest_request = request
    if candidate['id'] not in legal_after(request, []):
        raise ValueError('frozen choice is not legal in its captured public request')
    output.mkdir()
    adapter.vla_budget = VLABudget(**query['outcome_contract']['vla_budget'])
    spec = query['outcome_contract']['subtask']
    reference = facade.grasp_reference(spec['source_symbol']) if spec['mode'] == 'pick' else None
    original_rpc, original_model = policy.rpc, adapter.p.model
    policy.rpc = probe.SubtaskRPC(facade, spec)
    seeded = probe.SeededPolicy(original_model, seed, input_ledger=output/'vla_inputs.jsonl')
    adapter.p.model = seeded
    started = time.perf_counter()
    before = adapter.p.env.execution_budget()['used_sim_steps']
    reason, receipts = 'decision_limit', []
    try:
        with (output/'choices.jsonl').open('x') as ledger:
            for index in range(160):
                if adapter.p.env.terminated or adapter.p.env.truncated:
                    reason = 'native_stop'
                    break
                if index == 0:
                    decision = {k: request[k] for k in ('schema_version', 'observation_id', 'revision')}
                    decision.update(kind='decision', candidate_ids=[candidate['id']])
                else:
                    request = adapter.request(k=4)
                    try:
                        decision = policy.choose(request)
                    except NoPublicOption:
                        reason = 'no_public_option'
                        break
                details = len(adapter.details)
                receipts = adapter.execute(request, decision)
                ledger.write(json.dumps({'index': index, 'request': request, 'decision': decision,
                    'receipts': receipts, 'execution_details': adapter.details[details:]}, default=str)+'\n')
                ledger.flush()
                if candidate['skill'] == 'call_vla':
                    reason = receipts[-1]['stop_reason'] if receipts else 'empty_receipt'
                    break
                status = facade.goal_status()
                source_entity, _ = probe.bind_subtask(policy, adapter, spec)
                completed = (source_entity is not None and adapter.held == source_entity.id
                    if spec['mode'] == 'pick' else status['satisfied'][spec['goal_index']])
                if completed:
                    reason = 'subtask_completed'
                    break
                if any(r['skill'] == 'finish' or r['skill'] == 'ask_help'
                        and r['outcome'] == 'rejected' for r in receipts):
                    reason = receipts[-1]['stop_reason']
                    break
        endpoint, endpoint_ref = probe.save_checkpoint(facade, adapter, policy, output/'private_endpoint.pkl')
        status = facade.goal_status()
        steps = adapter.p.env.execution_budget()['used_sim_steps']-before
        metrology_started = time.perf_counter()
        if candidate['parameters'].get('mode') == 'task':
            success, truth = bool(status['done']), status
        elif reference is not None:
            truth = facade.measure_grasp_hold(spec['source_symbol'], reference)
            success = truth['truth_v3']['success']
        else:
            success, truth = bool(status['satisfied'][spec['goal_index']]), status
        metrology_s = time.perf_counter()-metrology_started
    finally:
        policy.rpc, adapter.p.model = original_rpc, original_model
    result = {'query_id': query['query_id'], 'candidate_id': candidate['id'],
        'candidate_parameters': candidate['parameters'], 'seed': seed, 'status': 'closed',
        'success': success, 'reason': reason, 'sim_steps': steps,
        'wall_s': time.perf_counter()-started-metrology_s, 'private_metrology_s': metrology_s,
        'initial_physics_sha256': initial, 'binding': query['binding'],
        'endpoint': endpoint_ref, 'private_truth': truth, 'source_revision': revision,
        'vla_inputs': seeded.inputs, 'vla_predictions': seeded.predictions,
        'training_admission': False, 'model_choices_added': 0}
    probe.write(output/'summary.json', result)
    return result
