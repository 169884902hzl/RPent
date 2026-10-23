"""Run the published HTTP model on registered evaluation-only identities."""
import hashlib
import json
import time
from collections import Counter
from contextlib import ExitStack
from urllib.error import HTTPError
from urllib.request import urlopen


def verified_health(service):
    """Require the registered adapter and public contract, not just HTTP 200."""
    with urlopen(service['health_url'], timeout=30) as response:
        health = json.load(response)
    if health['status'] != 'ok' or health['adapter_sha256'] != service['adapter_sha256']:
        raise ValueError('model service adapter differs from registration')
    version = service.get('schema_version')
    package = (health.get('bounded_supported_schemas', {}).get(version)
        if version is not None else health['skill_package'])
    if package is None:
        raise ValueError('model service does not support registered schema: '+str(version))
    for key in ('schema_sha256', 'contract_sha256'):
        if package[key] != service[key]:
            raise ValueError('model service contract differs from registration: '+key)
    return health


def restore_registered_physics(probe, facade, adapter, reference):
    """Restore a pinned full physical state, then rebuild public measurements."""
    import pickle
    from pathlib import Path
    from robots.libero.bounded_motion import measured_robot

    path = Path(reference['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != reference['sha256']:
        raise ValueError('registered initial snapshot changed')
    saved = pickle.loads(path.read_bytes())
    physics = saved['physics']
    observed = facade.restore(physics)
    facade._native_success_events = saved.get('private_native_success_events', [])
    adapter.p.env.last_obs = observed
    flags = saved.get('client_stop_flags', {})
    adapter.p.env.terminated = bool(flags.get('terminated', False))
    adapter.p.env.truncated = bool(flags.get('truncated', False))
    adapter.p.set_obs(observed)
    actual = probe.snapshot_digest(facade.snapshot())
    if actual != probe.snapshot_digest(physics):
        raise ValueError('registered complete physical state failed exact restoration')
    for name in ('_bounded_motion_samples', '_bounded_rest_reference'):
        if hasattr(adapter.p, name):
            delattr(adapter.p, name)
    adapter._proprio_sample = None
    adapter._incremental_previous_robot = None
    adapter.gripper_command = saved.get('gripper_command',
        -1. if measured_robot(adapter.p)['gripper_opening_m'] >= .075 else 1.)
    adapter.refresh()
    return {'reference': reference, 'initial_physics_sha256': actual,
        'complete_physics_matches': True, 'public_reconstruction': 'fresh_rgbd_and_proprioception',
        'private_object_coordinates_imported': False}


def run_episode(probe, case, endpoints, output, plan, k, *, startup=False, domain='original', split='init_holdout'):
    """Make every semantic choice through HTTP; oracle labels are never read."""
    from robots.libero.bounded_async import http_choice, public_model_request
    from scripts.probe_bounded_hybrid_d2 import SeededPolicy
    service = plan['model_service']
    health = verified_health(service)
    output.mkdir()
    def save_response(result):
        with (output/'model_responses.jsonl').open('a') as stream:
            stream.write(json.dumps(result)+'\n')
    choose = http_choice(service['endpoint'], on_response=save_response)
    (output/'service_health_before.json').write_text(json.dumps(health, indent=2)+'\n')
    with probe.runtime(case, endpoints, output, domain=domain) as (facade, adapter, policy, timings), ExitStack() as owned:
        policy_seed = plan.get('policy_seed_base', 50000000) + int(
            hashlib.sha256(case['name'].encode()).hexdigest()[:8], 16)
        original_vla = adapter.p.model
        seeded_vla = SeededPolicy(original_vla, policy_seed, input_ledger=output/'vla_inputs.jsonl')
        adapter.p.model = seeded_vla
        owned.callback(setattr, adapter.p, 'model', original_vla)
        adapter.allow_vla = True
        adapter.vla_options_v2 = True
        adapter.human_available = False
        registered_initial = plan.get('initial_snapshot_by_arm', {}).get(case['name']+'|'+str(k))
        restoration = (restore_registered_physics(probe, facade, adapter, registered_initial)
            if registered_initial is not None else None)
        _, initial = probe.save_checkpoint(facade, adapter, policy, output/'private_initial.pkl')
        started = time.perf_counter()
        records, skill_steps = [], Counter()
        recovery_used, recovery_events, stop_reason = 0, [], 'decision_limit'
        recovery_budget = plan['runtime_budget'].get('recovery_budget')
        with (output/'choices.jsonl').open('x') as ledger, (output/'requests.jsonl').open('x') as requests:
            for index in range(plan['runtime_budget']['decisions']):
                if adapter.p.env.terminated or adapter.p.env.truncated:
                    stop_reason = 'native_success' if adapter.p.env.terminated else 'native_truncated'
                    break
                begin = time.perf_counter()
                start_event = len(timings.events)
                with timings.measure('planning.request'):
                    request = adapter.request(k=k)
                if plan.get('require_human_capability') and request.get('human_available') is not False:
                    raise ValueError('new evaluation request must explicitly disable unavailable human assistance')
                request_sha = hashlib.sha256(json.dumps(request, sort_keys=True,
                    separators=(',', ':')).encode()).hexdigest()
                model_request = public_model_request(request)
                model_request_sha = hashlib.sha256(json.dumps(model_request, sort_keys=True,
                    separators=(',', ':')).encode()).hexdigest()
                requests.write(json.dumps({'index': index, 'request': request,
                    'request_sha256': request_sha, 'model_request': model_request,
                    'model_request_sha256': model_request_sha,
                    'model_view': 'omit_frozen_public_blockers/1'})+'\n')
                requests.flush()
                try:
                    with timings.measure('decision.model'):
                        decision = choose(request)
                except HTTPError as exc:
                    body = exc.read().decode('utf-8', errors='replace')
                    (output/'model_http_error.json').write_text(json.dumps({
                        'index': index, 'request_sha256': request_sha,
                        'model_request_sha256': model_request_sha,
                        'status': exc.code, 'body': body, 'endpoint': service['endpoint']}, indent=2)+'\n')
                    raise RuntimeError(f'model HTTP {exc.code}: {body}') from exc
                before = len(adapter.details)
                held_before = getattr(adapter, 'held', None)
                with timings.measure('execution.chunk'):
                    receipts = adapter.execute(request, decision)
                record = {'index': index, 'request': request, 'decision': decision,
                    'request_sha256': request_sha,
                    'model_request_sha256': model_request_sha,
                    'receipts': receipts, 'details': adapter.details[before:],
                    'wall_time_breakdown': timings.summary(time.perf_counter()-begin,
                        start_event=start_event)}
                ledger.write(json.dumps(record, default=str)+'\n')
                ledger.flush()
                records.append(record)
                for receipt in receipts:
                    skill_steps[receipt['skill']] += receipt['steps_used']
                if recovery_budget is not None:
                    failed = any(probe.consumes_recovery(r) for r in receipts)
                    if failed:
                        recovery_events.append({'decision': index, 'used_before': recovery_used,
                            'public_phase_held_anchor_id': held_before})
                        if recovery_used >= recovery_budget:
                            stop_reason = 'failed_chunk_recovery_budget'
                            break
                        recovery_used += 1
                    elif getattr(adapter, 'held', None) != held_before or any(
                            r.get('skill') == 'call_vla' and r.get('outcome') == 'success'
                            for r in receipts):
                        # Public contact/hold transition, never an oracle goal or label.
                        recovery_used = 0
                if startup and sum(skill_steps.values()) > 0:
                    stop_reason = 'startup_physical'
                    break
                if any(r['skill'] == 'finish' or r['skill'] == 'ask_help'
                        and r.get('outcome') == 'rejected' for r in receipts):
                    stop_reason = receipts[-1].get('stop_reason', receipts[-1]['skill'])
                    break
        after = verified_health(service)
        (output/'service_health_after.json').write_text(json.dumps(after, indent=2)+'\n')
        return {'case': case, 'status': 'startup_physical' if startup else 'physical_result',
            'success': bool(facade.goal_status()['done']), 'decisions': len(records),
            'sim_steps': sum(skill_steps.values()), 'skill_sim_steps': dict(skill_steps),
            'k': k, 'model_service': service, 'initial_snapshot': initial,
            'source_commit': plan['source_commit'], 'split': split, 'domain': domain,
            'recovery_budget': recovery_budget, 'recovery_used': recovery_used,
            'recovery_events': recovery_events, 'stop_reason': stop_reason,
            'vla_policy_seed': policy_seed, 'vla_inference_calls': seeded_vla.calls,
            'vla_inputs': seeded_vla.inputs, 'vla_predictions': seeded_vla.predictions,
            'recovery_scope': 'public hold transitions or successful call_vla; no private-subtask reset',
            'training': False, 'confirmation': False, 'oracle_choices_used': 0,
            'registered_initial_restoration': restoration, 'human_available': False,
            'wall_s': time.perf_counter()-started,
            'wall_time_breakdown': timings.summary(time.perf_counter()-timings.started),
            'selected_option_ids': [r['decision']['candidate_ids'] for r in records],
            'native_truncated': bool(adapter.p.env.truncated),
            'last_receipts': records[-1]['receipts'] if records else []}
