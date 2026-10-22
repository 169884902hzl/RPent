"""Evaluate pi0.5 on pinned own-layout original train worlds; no training."""
import hashlib
import json
from pathlib import Path
import pickle
import time


def checked(reference):
    path = Path(reference['path'])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise ValueError('registered own-layout input changed: '+str(path))
    return raw


def validate_job(row, plan):
    from robots.libero.bounded_train_layouts import ORIGINAL_SUITES
    if (row['kind'] != 'layout_pilot' or plan['training'] or plan['confirmation']
            or row['case']['episode']['suite'] not in ORIGINAL_SUITES):
        raise ValueError('own-layout pilot requires original development inputs')
    report = json.loads(checked(row['construction_report']))
    raw = checked(row['generated_state'])
    generated = pickle.loads(raw)
    if (hashlib.sha256(raw).hexdigest() != report['state_sha256']
            or not report['CPU_only'] or report['GPU_rollouts'] != 0
            or report['layout'] != generated['layout']):
        raise ValueError('CPU construction report and state disagree')
    parent = generated['layout']['parent']
    if any(parent[key] != row['case']['episode'][key] for key in ('suite', 'task', 'seed')):
        raise ValueError('constructed world and original runtime parent differ')
    checked(row['case']['bddl'])
    if row['case']['bddl'] != report['original_bddl']:
        raise ValueError('task wording or original BDDL identity changed')
    parents = json.loads(checked(row['frozen_parent_index']))['parents']
    if parents[report['parent_id']]['split'] != 'train':
        raise ValueError('constructed world parent is not original train')
    witness = generated['layout']['predicate_witness']
    if not all(witness.get(key) is True for key in ('native_predicates_satisfied',
            'nonintersecting', 'instruction_identity_consistent')):
        raise ValueError('constructed world lacks the registered CPU checks')
    return generated, report


def run_case(row, plan, endpoints, output, *, startup=False):
    from scripts import probe_bounded_hybrid_d2 as probe
    from robots.libero.bounded_offline_labels import capture_annotation_state, save_annotation_state
    from rpent.skill_package.vla import VLABudget

    generated, construction = validate_job(row, plan)
    output.mkdir()
    with probe.runtime(row['case'], endpoints, output, domain='original',
            constructed_start=generated) as (facade, adapter, policy, timings):
        probe.configure_development_catalog(adapter, {'vla_options_v2': True})
        adapter.vla_budget = VLABudget(**row['vla_budget'])
        adapter.hybrid_recovery_budget = 0
        with timings.measure('planning.request'):
            request = adapter.request(k=4)
        _, branch = probe.save_checkpoint(facade, adapter, policy,
            output/'private_canonical_branchpoint.pkl', request)
        annotation = save_annotation_state(output/'private_annotation.pkl',
            capture_annotation_state(policy, request))
        # The forced public task candidate is scored only by native full-task
        # completion; no private subgoal becomes a policy option or prompt.
        goals = facade.goal_status()['goals']
        spec = {'mode': 'task', 'source_symbol': goals[0][1],
            'target_symbol': None, 'goal_index': 0}
        trial, _ = probe.trial(facade, adapter, policy, timings, spec, 'call_vla',
            row['trial_seed'], output/'full_task', request,
            vla_parameters={'mode': 'task', 'preparation': 'in_place', 'prompt_style': 'full_task'})
        result = {'case': row['case'], 'source_commit': plan['source_commit'],
            'status': 'startup_physical' if startup else 'physical_result',
            'evaluation': 'own_original_train_layout_pi05_full_task',
            'success': trial['success'], 'actual_full_replay_success': trial['success'],
            'sim_steps': trial['sim_steps'], 'trials': [trial],
            'canonical_branchpoint': branch, 'private_annotation': annotation,
            'construction_report': row['construction_report'], 'generated_state': row['generated_state'],
            'layout_seed': construction['layout']['layout_seed'],
            'requested_task_text': adapter.ex.instruction,
            'wall_time_breakdown': timings.summary(time.perf_counter()-timings.started),
            'training': False, 'confirmation': False, 'training_admission': False,
            'scope': 'twenty-state development pilot; not a confirmation result or training admission'}
        if startup and (not trial['sim_steps'] or not trial['vla_inference_calls']):
            raise RuntimeError('layout pilot startup did not execute a real VLA control')
        probe.write(output/'summary.json', result)
        return result
