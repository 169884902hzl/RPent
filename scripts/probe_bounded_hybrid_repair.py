"""Registered same-state handoff/stop diagnostics, separate from D2 whole cases."""
from __future__ import annotations

import copy
import json
import pickle
import time
from pathlib import Path

from rpent.skill_package.vla import VLABudget
from scripts import probe_bounded_hybrid_d2 as probe
from scripts.probe_bounded_motion import write


def migrate_replay_header(adapter, request):
    """Admit an unchanged historical catalog for a registered replay.

    V4 extends the mode enum and V5 adds an explicitly scoped endpoint screen.
    Neither changes the meaning of existing full-route consequences.
    This explicitly changes the version header, never poses/options/screens.
    """
    from rpent.skill_package import VERSION

    if (request['schema_version'], VERSION) not in {
            ('bounded-skills/3', 'bounded-skills/4'),
            ('bounded-skills/3', 'bounded-skills/5'),
            ('bounded-skills/4', 'bounded-skills/5')}:
        raise ValueError('unsupported historical replay header migration')
    request = copy.deepcopy(request)
    cached = copy.deepcopy(adapter.latest_request)
    if request != cached:
        raise ValueError('saved request differs from its restored cache')
    request['schema_version'] = cached['schema_version'] = VERSION
    adapter.latest_request = cached
    return request


def rebuild_schema6_replay(adapter, request, defaults):
    """Re-measure a historical checkpoint for the changed schema6 catalog.

    Schema6 merges move options, so a version-header rewrite cannot preserve
    their meaning. Keep the restored physics and retry history, initialize
    only the new runtime fields, and generate a current measured request.
    """
    from rpent.skill_package import VERSION

    if VERSION != 'bounded-skills/6' or request['schema_version'] not in {
            'bounded-skills/3', 'bounded-skills/4', 'bounded-skills/5'}:
        raise ValueError('unsupported schema6 checkpoint reconstruction')
    if request != adapter.latest_request:
        raise ValueError('saved request differs from its restored cache')
    vars(adapter).update(copy.deepcopy(defaults))
    adapter.refresh()
    return adapter.request(k=4)


SCHEMA6_REPLAY_FIELDS = (
    'schema6_v1', 'lazy_planning_v1', 'public_progress', '_incremental_touched',
    '_incremental_route', '_failed_move_anchors', '_move_approach_by_anchor',
    '_grasp_geometry_cache', 'vla_options_v2',
)


def constructed_original_start(case, plan):
    """Use the existing train-layout provenance checks for measured forks."""
    diagnostic = case['diagnostic']
    if 'own_layout' not in diagnostic:
        return None
    if diagnostic['domain'] != 'original' or diagnostic['kind'] != 'original_fork':
        raise ValueError('own layouts require an original train fork')
    from coordination.bounded_skills_20261016.scripts.run_own_layout_pi_pilot_20261022 import validate_job

    row = {'kind': 'layout_pilot', 'case': case,
        **{key: diagnostic['own_layout'][key] for key in
            ('generated_state', 'construction_report', 'frozen_parent_index')}}
    generated, _ = validate_job(row, plan)
    return generated


def validate_plan(plan):
    from robots.libero.bounded_hybrid_diagnostic import validate_d2_episode
    if (plan.get('evaluation') != 'hybrid_repair' or plan['training'] or plan['confirmation']
            or not plan['cases']):
        raise ValueError('expected an isolated development repair plan')
    for case in plan['cases']:
        probe.load_public_gripper_calibration(case['grasp_measurement_calibration'])
        diagnostic = case['diagnostic']
        repeats = diagnostic.get('self_repeats', 1)
        if type(repeats) is not int or repeats < 1:
            raise ValueError('self_repeats must be a positive integer')
        vla_repeats = diagnostic.get('vla_repeats', 3)
        if type(vla_repeats) is not int or vla_repeats < 1:
            raise ValueError('vla_repeats must be a positive integer')
        if diagnostic['domain'] == 'd2':
            validate_d2_episode(case['episode'])
        elif diagnostic['domain'] == 'original':
            ep = case['episode']
            suites = {'libero_spatial': 10, 'libero_object': 10, 'libero_goal': 10,
                'libero_10': 10, 'libero_90': 90}
            if ep['suite'] not in suites or not 0 <= ep['task'] < suites[ep['suite']]:
                raise ValueError('original fork requires an original40/90 task')
        else:
            raise ValueError('unregistered diagnostic domain')
        if 'own_layout' in diagnostic:
            constructed_original_start(case, plan)
        VLABudget(**diagnostic['budget'])
        for key in ('old_summary', 'branchpoint'):
            if key in diagnostic and probe.reference(diagnostic[key]['path']) != diagnostic[key]:
                raise ValueError('registered replay input changed')
        if 'original_subtask_start' in diagnostic:
            if diagnostic['domain'] != 'original' or diagnostic['kind'] != 'original_fork':
                raise ValueError('original saved starts cannot be used for D2')
            for key in ('physics', 'annotation'):
                ref = diagnostic['original_subtask_start'][key]
                if probe.reference(ref['path'])['sha256'] != ref['sha256']:
                    raise ValueError('registered original subtask start changed')


def restore_original_subtask(facade, adapter, policy, reference):
    """Restore logged physics, then create one fresh public state for both arms.

    Old measured anchors associate IDs only. Unobserved old anchors are dropped;
    no simulator object location or old numerical planning screen is imported.
    Recovery history starts fresh equally in both arms, rather than pretending
    that the limited old annotation contains the complete live runtime.
    """
    from robots.libero.bounded_motion import measured_robot
    from robots.libero.bounded_offline_labels import load_annotation_state

    physics = pickle.loads(Path(reference['physics']['path']).read_bytes())
    captured = load_annotation_state(reference['annotation']['path'], reference['annotation']['sha256'])
    observed = facade.restore(physics)
    adapter.p.env.last_obs = observed
    adapter.p.env.terminated = adapter.p.env.truncated = False
    adapter.p.set_obs(observed)
    actual = facade.snapshot()
    legacy = 'observation_state' not in physics['actuator_state']
    complete_integration = physics['actuator_state'].get('integration') is not None
    if not complete_integration:
        from robots.libero.v5_branch_state import captured_projection
        actual = captured_projection(actual,physics)
    if probe.snapshot_digest(actual) != probe.snapshot_digest(physics):
        raise ValueError('original subtask start physics did not restore exactly')
    old_adapter = captured['adapter']
    adapter.scene.entities = copy.deepcopy(old_adapter.scene.entities)
    adapter.scene._ids = [key for key in adapter.scene._ids if key not in adapter.scene.entities]
    for name in ('_bounded_motion_samples', '_bounded_control_index', '_bounded_rest_reference'):
        if hasattr(old_adapter.p, name):
            setattr(adapter.p, name, copy.deepcopy(getattr(old_adapter.p, name)))
    adapter.gripper_command = -1. if measured_robot(adapter.p)['gripper_opening_m'] >= .075 else 1.
    adapter.refresh()
    step = adapter.ex.toolkit._state.latest_step
    adapter.scene.entities = {key: entity for key, entity in adapter.scene.entities.items()
        if entity.visible and entity.source_step == step}
    old_held = old_adapter.held
    if old_held in adapter.scene.entities and adapter.holding_aperture(
            measured_robot(adapter.p)['gripper_opening_m'])[0]:
        payload = (copy.deepcopy(old_adapter.payload_reference)
            if getattr(old_adapter, 'payload_reference', None) is not None
            else adapter._capture_payload_reference(old_held))
        adapter.held = adapter.active = old_held
        adapter.payload_reference = payload
        adapter._instance_cache.clear()
        adapter._screen_cache.clear()
    return {'physics': reference['physics'], 'annotation': reference['annotation'],
        'same_captured_physics': True, 'historical_observation_phase_available': not legacy,
        'historical_complete_integration_available':complete_integration,
        'public_reconstruction': 'fresh_dual_view_rgbd; old_public_anchor_ids_associated_then_unmeasured_dropped',
        'recovery_history': 'fresh_and_identical_in_both_arms', 'held_id_after_measurement': adapter.held,
        'simulation_object_coordinates_imported_to_public_state': False}


def first_self_chunk(facade, adapter, policy, spec, output):
    """Actually continue with bounded skills after the VLA/control handoff."""
    from robots.libero.bounded_oracle import NoPublicOption
    from rpent.skill_package.contract import legal_after
    started = time.perf_counter()
    before = adapter.p.env.execution_budget()['used_sim_steps']
    request = adapter.request(k=4)
    write(output / 'first_self_request.json', request)
    original = policy.rpc
    policy.rpc = probe.SubtaskRPC(facade, spec)
    try:
        try:
            decision = policy.choose(request)
        except NoPublicOption as exc:
            return {'request_generated': True, 'legal_n': len(legal_after(request, [])),
                'status': 'no_public_option', 'message': str(exc), 'wall_s': time.perf_counter()-started}
        if any(next(c for c in request['candidates'] if c['id'] == cid)['skill'] == 'call_vla'
               for cid in decision['candidate_ids']):
            raise ValueError('self continuation must use bounded skills')
        receipts = adapter.execute(request, decision)
        result = {'request_generated': True, 'legal_n': len(legal_after(request, [])),
            'status': 'executed', 'decision': decision, 'receipts': receipts,
            'sim_steps': adapter.p.env.execution_budget()['used_sim_steps']-before,
            'wall_s': time.perf_counter()-started}
        write(output / 'first_self_chunk.json', result)
        return result
    finally:
        policy.rpc = original


def run_trial(facade, adapter, policy, timings, spec, method, seed, output, request, *,
              decision_limit=160, vla_parameters=None):
    start_event, started = len(timings.events), time.perf_counter()
    result, endpoint = probe.trial(facade, adapter, policy, timings, spec, method,
        seed, output, request, decision_limit=decision_limit,
        **({'vla_parameters': vla_parameters} if vla_parameters is not None else {}))
    result['wall_time_breakdown'] = timings.summary(time.perf_counter()-started, start_event=start_event)
    write(output / 'summary.json', result)
    return result, endpoint


def vla_execution(result):
    for line in Path(result['choices']['path']).open():
        for detail in json.loads(line)['execution_details']:
            execution = detail.get('execution', {})
            if 'skill_stop_reason' in execution:
                return execution
    return None


def evaluate_case(case, endpoints, output, plan, *, startup=False):
    output.mkdir()
    diagnostic = case['diagnostic']
    budget = VLABudget(**diagnostic['budget'])
    constructed = constructed_original_start(case, plan)
    world = {'constructed_start': constructed} if constructed is not None else {}
    with probe.runtime(case, endpoints, output, domain=diagnostic['domain'], **world) as (facade, adapter, policy, timings):
        probe.configure_development_catalog(adapter, plan)
        if diagnostic['kind'] == 'replay':
            old = json.loads(Path(diagnostic['old_summary']['path']).read_bytes())
            saved = pickle.loads(Path(diagnostic['branchpoint']['path']).read_bytes())
            rebuild_public = bool(plan.get('schema6_source'))
            defaults = ({name: copy.deepcopy(getattr(adapter, name))
                         for name in SCHEMA6_REPLAY_FIELDS} if rebuild_public else None)
            probe.restore_checkpoint(facade, adapter, policy, saved)
            adapter.vla_budget = budget
            adapter.targeted_vla_measurement_v1 = diagnostic.get('targeted_vla_measurement_v1', False)
            spec, request = old['subtask'], saved['request']
            if rebuild_public:
                request = rebuild_schema6_replay(adapter, request, defaults)
            elif diagnostic.get('migrate_v3_header_to_v4', False):
                request = migrate_replay_header(adapter, request)
            result, endpoint = run_trial(facade, adapter, policy, timings, spec, 'call_vla',
                old['trial_seed'], output / 'replay', request)
            old_execution, new_execution = vla_execution(old), vla_execution(result)
            old_trace = old_execution['trace'] if old_execution else []
            new_trace = new_execution['trace'] if new_execution else []
            common = min(len(old_trace), len(new_trace))
            result['paired_replay'] = {'old_summary': diagnostic['old_summary'],
                'same_initial_physics': result['initial_physics_sha256'] == old['initial_physics_sha256'],
                'same_legacy_captured_physics': result['initial_legacy_captured_physics_sha256'] == old['initial_physics_sha256'],
                'historical_observation_phase_available': 'observation_state' in saved['physics']['actuator_state'],
                'same_initial_request': result['request_sha256'] == old['request_sha256'],
                'same_request_except_schema': {k:v for k,v in request.items() if k != 'schema_version'}
                    == {k:v for k,v in saved['request'].items() if k != 'schema_version'},
                'public_request_schema_migration': diagnostic.get('migrate_v3_header_to_v4', False) and not rebuild_public,
                'schema6_public_request_rebuilt': rebuild_public,
                'old_controls':len(old_trace), 'new_controls':len(new_trace),
                'common_controls':common,
                'first_action_mismatch':next((i for i in range(common)
                    if old_trace[i]['action'] != new_trace[i]['action']), None)}
            write(output / 'replay/summary.json', result)
            probe.restore_checkpoint(facade, adapter, policy, endpoint)
            subtask_plan, _ = probe.split_subtasks(facade.goal_status()['goals'], adapter.ex.instruction)
            next_spec = spec
            if result['success'] is True:
                position = next(i for i, value in enumerate(subtask_plan) if value['id'] == spec['id'])
                if position+1 < len(subtask_plan):
                    next_spec = subtask_plan[position+1]
            continuation = (first_self_chunk(facade, adapter, policy, next_spec, output)
                if not (adapter.p.env.terminated or adapter.p.env.truncated) else {'status':'native_stop'})
            trials = [result]
        elif diagnostic['kind'] == 'original_fork':
            restored_start = (restore_original_subtask(facade, adapter, policy,
                diagnostic['original_subtask_start']) if 'original_subtask_start' in diagnostic else None)
            subtask_plan, unsupported = probe.split_subtasks(facade.goal_status()['goals'], adapter.ex.instruction)
            matches = [s for s in subtask_plan if s['mode'] == diagnostic['subtask_mode']
                and s['goal_index'] == diagnostic.get('goal_index', 0)]
            if not matches:
                report = {'case':case, 'status':'oracle_rule_uncovered', 'unsupported':unsupported,
                    'reason':'requested_original_subtask_not_in_existing_progress_rules', 'training':False}
                write(output / 'summary.json', report)
                return report
            spec = matches[0]
            adapter.vla_budget = budget
            adapter.targeted_vla_measurement_v1 = diagnostic.get('targeted_vla_measurement_v1', False)
            prefix = []
            prefix_decisions = 0
            position = subtask_plan.index(spec)
            prerequisites = [] if restored_start is not None else subtask_plan[:position]
            for index, prerequisite in enumerate(prerequisites):
                if facade.goal_status()['satisfied'][prerequisite['goal_index']]:
                    continue
                request = adapter.request(k=4)
                row, endpoint = run_trial(facade, adapter, policy, timings, prerequisite, 'self',
                    diagnostic['trial_seed_base']+500000000+1000*index,
                    output/f'prefix_{index:02d}_{prerequisite["mode"]}', request,
                    decision_limit=max(0, 160-prefix_decisions))
                prefix.append(row)
                prefix_decisions += row['decisions']
                probe.restore_checkpoint(facade, adapter, policy, endpoint)
                if row['success'] is not True:
                    report = {'case': case, 'status': 'prefix_not_reached', 'prefix': prefix,
                        'requested_subtask': spec, 'trials': [], 'training': False,
                        'confirmation': False, 'source_commit': plan['source_commit'],
                        'reason': 'bounded_prefix_failed_before_registered_fork'}
                    write(output/'summary.json', report)
                    return report
            request = adapter.request(k=4)
            saved, _ = probe.save_checkpoint(facade, adapter, policy, output / 'private_branchpoint.pkl', request)
            trials = []
            # Trial identities/seeds are fixed independently of scheduling.
            # Diagnose fallback contact before a slow bounded-self branch.
            variants = diagnostic.get('vla_variants')
            if variants is not None:
                if not plan.get('vla_options_v2'):
                    raise ValueError('explicit VLA variants require the registered B2 catalog')
                methods = [(j, 'call_vla', variant) for variant in variants
                    for j in range(1, diagnostic.get('vla_repeats', 3) + 1)]
                if startup:
                    methods = methods[:1]
            else:
                methods = [(j, 'call_vla', None) for j in
                    ((1,) if startup else range(1, diagnostic.get('vla_repeats', 3) + 1))]
            if not startup and diagnostic.get('include_self', True):
                methods.extend((j, 'self', None) for j in range(diagnostic.get('self_repeats', 1)))
            for index, method, variant in methods:
                probe.restore_checkpoint(facade, adapter, policy, saved)
                adapter.vla_budget = budget
                adapter.targeted_vla_measurement_v1 = diagnostic.get('targeted_vla_measurement_v1', False)
                name = f'{method}_{index}' if variant is None else f'call_vla_{variant["name"]}_{index}'
                parameters = variant['parameters'] if variant is not None else None
                row, _ = run_trial(facade, adapter, policy, timings, spec, method,
                    diagnostic['trial_seed_base']+index*1000, output / name, request,
                    decision_limit=max(0, 160-prefix_decisions), vla_parameters=parameters)
                if variant is not None:
                    row['vla_variant'] = variant
                    write(output / name / 'summary.json', row)
                trials.append(row)
            continuation = None
        else:
            raise ValueError('unsupported repair diagnostic')
        report = {'case':case, 'status':'physical_result', 'evaluation':'hybrid_repair',
            'scope':'subtask diagnostic; not a D2 whole-episode score', 'trials':trials,
            'continuation':continuation, 'source_commit':plan['source_commit'],
            'training':False, 'confirmation':False, 'actual_full_replay_success':None}
        if diagnostic['kind'] == 'original_fork':
            report['prefix'] = prefix
            report['restored_original_subtask_start'] = restored_start
        write(output / 'summary.json', report)
        return report
