"""Capture original-train layout states along actual bounded oracle prefixes."""
import hashlib
import json
from pathlib import Path
import pickle
import time


def reference(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def run_case(row, plan, endpoints, output, *, startup=False):
    from scripts import probe_bounded_hybrid_d2 as probe
    from robots.libero.bounded_offline_labels import capture_annotation_state, save_annotation_state
    from robots.libero.bounded_oracle import NoPublicOption
    from coordination.bounded_skills_20261016.scripts.run_own_layout_pi_pilot_20261022 import validate_job

    generated, construction = validate_job({**row, 'kind': 'layout_pilot'}, plan)
    output.mkdir()
    points, trace, first_physical = [], [], None
    last_saved_steps = None
    reason = 'prefix_decision_limit'
    with probe.runtime(row['case'], endpoints, output, domain='original',
            constructed_start=generated) as (facade, adapter, policy, timings):
        probe.configure_development_catalog(adapter, {'vla_options_v2': True})
        adapter.hybrid_recovery_budget = row.get('recovery_budget', 0)
        for index in range(row.get('prefix_decisions', 12)):
            if adapter.p.env.terminated or adapter.p.env.truncated:
                reason = 'native_stop'
                break
            with timings.measure('planning.request'):
                request = adapter.request(k=1)
            status = facade.goal_status()
            if status['done']:
                reason = 'native_task_completed'
                break
            steps = adapter.p.env.execution_budget()['used_sim_steps']
            if last_saved_steps is None or steps > last_saved_steps:
                directory = output/f'point{len(points):03d}'
                directory.mkdir()
                specs, unsupported = probe.split_subtasks(status['goals'], adapter.ex.instruction)
                goal_index = next((i for i, done in enumerate(status['satisfied']) if not done), None)
                available = [spec for spec in specs if spec['goal_index'] == goal_index]
                held = None
                if available:
                    source, _ = probe.bind_subtask(policy, adapter, available[0])
                    held = source is not None and adapter.held == source.id
                spec = (next((s for s in available if s['mode'] != 'pick'), None)
                    if held else next(iter(available), None))
                saved, checkpoint = probe.save_checkpoint(facade, adapter, policy,
                    directory/'private_branchpoint.pkl', request)
                physics = directory/'private_physics.pkl'
                physics.write_bytes(pickle.dumps(saved['physics'], protocol=5))
                annotation = save_annotation_state(directory/'private_annotation.pkl',
                    capture_annotation_state(policy, request))
                point = {'index': len(points), 'prefix_decisions': index,
                    'public_sim_steps': steps, 'public_held': bool(held),
                    'phase': 'initial' if not points else 'public_held' if held else 'intermediate',
                    'holding_scope': 'public adapter state; private grasp truth is measured in the subsequent forks',
                    'label_eligible': spec is not None, 'subtask': spec, 'unsupported': unsupported,
                    'physics': reference(physics), 'annotation': annotation, 'checkpoint': checkpoint,
                    'layout_seed': construction['layout']['layout_seed'],
                    'construction_report': row['construction_report'],
                    'generated_state': row['generated_state'], 'frozen_parent_index': row['frozen_parent_index'],
                    'source_commit': plan['source_commit'], 'case': row['case'],
                    'training': False, 'confirmation': False}
                probe.write(directory/'point.json', point)
                points.append(point)
                last_saved_steps = steps
                if len(points) >= row.get('max_points', 5):
                    reason = 'registered_point_limit'
                    break
            try:
                with timings.measure('decision.oracle'):
                    decision = policy.choose(request)
            except NoPublicOption:
                reason = 'no_public_option'
                break
            by_id = {c['id']: c for c in request['candidates']}
            if len(decision['candidate_ids']) != 1 or any(
                    by_id[cid]['skill'] == 'call_vla' for cid in decision['candidate_ids']):
                raise ValueError('prefix collection requires one bounded oracle action, with VLA disabled')
            before_path = output/f'step{index:03d}_private_before.pkl'
            before_path.write_bytes(pickle.dumps(facade.snapshot(), protocol=5))
            details_before = len(adapter.details)
            with timings.measure('execution.adapter'):
                receipts = adapter.execute(request, decision)
            event = {'request': request, 'decision': decision, 'receipts': receipts,
                'execution_details': adapter.details[details_before:],
                'private_pre_execution_snapshot': reference(before_path)}
            trace.append(event)
            with (output/'prefix_choices.jsonl').open('a') as stream:
                stream.write(json.dumps(event, default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x))+'\n')
            if any(receipt['steps_used'] > 0 for receipt in receipts):
                first_physical = first_physical or event
                if startup:
                    reason = 'first_physical_prefix_request'
                    break
            if any(receipt['skill'] in {'finish', 'ask_help'} for receipt in receipts):
                reason = 'bounded_terminal_option'
                break
        result = {'case': row['case'], 'source_commit': plan['source_commit'],
            'status': 'startup_physical' if startup else 'physical_result', 'reason': reason,
            'points': points, 'first_physical': first_physical or {},
            'prefix_decisions': len(trace), 'sim_steps': adapter.p.env.execution_budget()['used_sim_steps'],
            'wall_time_breakdown': timings.summary(time.perf_counter()-timings.started),
            'training': False, 'confirmation': False, 'task_success_denominator': False,
            'scope': 'actual prefix-state acquisition; no measured method labels or model training yet'}
        probe.write(output/'summary.json', result)
        if startup and first_physical is None:
            raise RuntimeError('prefix collection startup made no physical request')
        return result
