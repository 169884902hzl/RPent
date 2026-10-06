"""Read saved drawer stages and original LIBERO semantics; CPU, no replay."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import numpy as np


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PHASES = ('after_actual_chunk', 'after_public_stop_before_recovery',
          'after_fixture_release', 'after_measured_contact_clearance',
          'after_view_retreat_attempt')


def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def compact_label(label):
    return {key: label.get(key) for key in ('source', 'predicate', 'satisfied',
            'joint_names', 'joint_qpos', 'sim_time')} if label else None


def score_record(sample):
    return {key: sample.get(key) for key in ('phase', 'chunk', 'source', 'used_for_control',
            'status', 'error')} | {'label': compact_label(sample.get('label'))}


def plane(geometry):
    return {key: geometry.get(key) for key in ('centre', 'normal_xy', 'points',
            'residual_p90_m', 'path', 'sha256', 'source_cameras')} if geometry else None


def geometry_record(sample):
    measurement = sample['measurement']
    views = measurement.get('views') or {}
    crossview = {}
    for component in ('frame', 'moving'):
        a, b = [(views.get(view) or {}).get(component) for view in ('agentview', 'wrist')]
        if a and b:
            normal = np.asarray(a['normal_xy'])
            crossview[component] = {
                'both_camera_planes_available': True,
                'normal_depth_difference_m': float(abs((np.asarray(b['centre'][:2]) - a['centre'][:2]) @ normal)),
                'normal_cosine_abs': float(abs(normal @ np.asarray(b['normal_xy'])))}
        else:
            crossview[component] = {'both_camera_planes_available': False,
                                    'available_cameras': [view for view in ('agentview', 'wrist')
                                        if (views.get(view) or {}).get(component)]}
    return {'chunk': sample['chunk'], 'verified': sample['verified'],
            'signed_extension_m': sample['evidence'].get('measured_signed_extension_m'),
            'thresholds_m': sample['evidence'].get('endpoint_thresholds_m'),
            'reason': sample['evidence'].get('reason'),
            'measurement': {key: measurement.get(key) for key in ('source_step', 'source',
                'basis', 'anchor_parent', 'anchor_part', 'anchor_source_step', 'current_part',
                'current_part_source_step', 'current_part_bounds', 'binding_margin_m',
                'depth_search_m', 'outward_axis_xy', 'point_counts_by_camera')},
            'frame': plane(measurement.get('frame')), 'moving': plane(measurement.get('moving')),
            'camera_planes': {view: {component: plane((data or {}).get(component))
                             for component in ('frame', 'moving')} for view, data in views.items()},
            'saved_camera_plane_comparison': crossview}


def compact_contacts(diagnostic, fixture):
    if not diagnostic:
        return None
    relevant = [contact for contact in diagnostic.get('contacts', [])
                if any(fixture in str(contact.get(key, '')) for key in ('geom1', 'geom2'))
                and any(any(token in str(contact.get(key, '')) for token in ('gripper', 'robot', 'panda'))
                        for key in ('geom1', 'geom2'))]
    return {'source': diagnostic.get('source'), 'requested_fixture_robot_contacts': relevant,
            'contact_position_recorded': any(any(key in contact for key in ('position', 'pos', 'point'))
                                             for contact in relevant),
            'scope': 'Saved simulation contacts are diagnostic only; absence in a limited snapshot is not proof of no contact'}


def motion_record(motion, fixture):
    data = {key: motion.get(key) for key in ('name', 'steps_used', 'actions_used', 'max_steps',
            'start_gripper_opening', 'peak_gripper_opening', 'final_gripper_opening',
            'gripper_command', 'start_eef_pos', 'target_xyz', 'final_eef_pos', 'final_dist_m',
            'waypoint_reached', 'failure_reason', 'terminated', 'truncated') if key in motion}
    trajectory = motion.get('trajectory') or []
    if trajectory:
        data['first_saved_pose'] = {key: trajectory[0].get(key) for key in ('step', 'eef_pos', 'dist_to_target_m')}
        data['last_saved_pose'] = {key: trajectory[-1].get(key) for key in ('step', 'eef_pos', 'dist_to_target_m')}
        data['requested_fixture_contact_samples'] = [
            {'step': sample.get('step'), 'eef_pos': sample.get('eef_pos'),
             'contacts': compact_contacts(sample.get('contact_and_joints'), fixture)}
            for sample in trajectory
            if (compact_contacts(sample.get('contact_and_joints'), fixture) or {}).get('requested_fixture_robot_contacts')]
    data['final_private_contacts'] = compact_contacts(motion.get('final_contact_and_joints'), fixture)
    return data


def null_reason(first):
    evidence = (first.get('verification_measurements') or {}).get('articulation') or {}
    if not evidence:
        return 'metrology_not_run_' + str(first['receipt'].get('failure_reason', 'unrecorded'))
    missing = [phase + '_' + part for phase in ('before', 'after') for part in ('frame', 'moving')
               if not (evidence.get(phase) or {}).get(part)]
    return 'missing_' + '+'.join(missing) if missing else 'measured_' + str(evidence.get('reason', 'endpoint_result'))


def original_task(case):
    # Read the installed original LIBERO task, never the PRO task file.
    path = Path(case['bddl']['path'].replace('/liberopro/liberopro/', '/libero/libero/'))
    assert '/libero/libero/' in str(path) and '/liberopro/' not in str(path)
    text = path.read_text()
    language = re.search(r'\(:language\s+([^\)]+)\)', text).group(1).strip()
    goal_block = text[text.index('(:goal'):]
    goals = [(mode.lower(), symbol) for mode, symbol in re.findall(
        r'\((open|close)\s+([^\s\)]+)\)', goal_block, flags=re.IGNORECASE)]
    return {'bddl': ref(path), 'language': language, 'articulation_goals': goals,
            'registered_prompt_matches_original_language': case['subtask_prompt'] == language,
            'requested_endpoint_in_original_goals': [case['mode'], case['object_symbol']] in [list(x) for x in goals]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--final-dir', type=Path, required=True)
    parser.add_argument('--source-snapshot', type=Path, required=True)
    parser.add_argument('--job-id', type=int, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_snapshot))
    from robots.libero.v5_verification import measured_fixture_endpoint

    formal_path = args.final_dir / 'statistic/report.json'
    formal = json.loads(formal_path.read_text())
    assert formal['complete'] and formal['overall']['recorded'] == 20
    original_libero = ROOT / '.venv/lib/python3.10/site-packages/libero/libero'
    semantic_path = original_libero / 'envs/objects/articulated_objects.py'
    semantic_text = semantic_path.read_text()
    white = semantic_text.split('class WhiteCabinet', 1)[1].split('@register_object', 1)[0]
    assert 'default_close_ranges"] = [0.0, 0.005]' in white
    assert 'qpos > min(self.object_properties["articulation"]["default_close_ranges"])' in white
    semantics = {'source': ref(semantic_path), 'predicate_source': ref(original_libero / 'envs/predicates/base_predicates.py'),
                 'original_WhiteCabinet_close_ranges': [0., .005], 'strict_close_condition': 'qpos > 0.0',
                 'original_WhiteCabinet_open_ranges': [-.16, -.14], 'strict_open_condition': 'qpos < -0.14',
                 'public_close_condition': 'measured_signed_extension_m <= 0.0005',
                 'meaning': 'A public close within 0.5mm does not imply the strict original positive-qpos endpoint'}
    groups, phases, nulls = defaultdict(Counter), defaultdict(lambda: defaultdict(Counter)), defaultdict(Counter)
    records, anomalies = [], []
    for source_ref in formal['original_explicit_inputs']:
        if source_ref['role'] != 'ledger' or not source_ref.get('exists'):
            continue
        ledger = Path(source_ref['snapshot'])
        for line_index, line in enumerate(ledger.read_text().splitlines(), 1):
            row = json.loads(line)
            case, first = row['case'], row['first_attempt']
            receipt = first['receipt']
            motions = first.get('motion_evidence') or []
            chunk_locations = [i for i, motion in enumerate(motions) if motion['name'] == 'vla_act_chunk']
            chunks = [motions[i] for i in chunk_locations]
            samples = first.get('contact_evidence', {}).get('private_fixture_scores', [])
            scored = {phase: [score_record(sample) for sample in samples if sample['phase'] == phase] for phase in PHASES}
            complete5 = all(chunk.get('requested_action_count') == chunk.get('executed_action_count') == 5 for chunk in chunks)
            trace_complete = [s['chunk'] for s in scored['after_actual_chunk']] == list(range(len(chunks)))
            all_diagnostic = all(s.get('used_for_control') is False and s.get('source') == 'simulation_diagnostic_only' for s in samples)
            stop_scores = scored['after_public_stop_before_recovery']
            stop = receipt.get('stop') == 'measured_fixture_endpoint'
            public_samples = (first.get('verification_measurements') or {}).get('drawer_public_stop', [])
            proof = {'available': False}
            if len(public_samples) >= 2 and all(s['measurement'].get('moving') for s in public_samples[-2:]):
                a, b = [s['measurement'] for s in public_samples[-2:]]
                stable, evidence = measured_fixture_endpoint(a, b, case['mode'], drawer=True, signed_drawer_v6=True)
                normal = np.asarray(b['frame']['normal_xy'])
                motion = float((np.asarray(b['moving']['centre'][:2]) - a['moving']['centre'][:2]) @ b['outward_axis_xy'])
                frame_drift = float(abs((np.asarray(b['frame']['centre'][:2]) - a['frame']['centre'][:2]) @ normal))
                frame_angle = math.degrees(math.acos(float(np.clip(abs(normal @ np.asarray(a['frame']['normal_xy'])), 0, 1))))
                proof = {'available': True, 'two_saved_verdicts_true': all(s['verified'] is True for s in public_samples[-2:]),
                         'fresh_source_steps': a['source_step'] != b['source_step'],
                         'source_step_pair': [a['source_step'], b['source_step']], 'stable_public_endpoint': stable,
                         'stability_reason': evidence.get('reason'), 'frame_normal_drift_m': frame_drift,
                         'frame_normal_angle_deg': frame_angle, 'outward_panel_motion_m': motion,
                         'passes_5mm_motion_gate': abs(motion) <= .005,
                         'after_complete_contact_chunk': public_samples[-1]['chunk'] == len(chunks) and complete5}
            selected_id = re.search(r'articulate\(([^,]+),', first['selected']).group(1)
            entities = {entity['id']: entity for entity in first['public_before']['entities']}
            selected = entities[selected_id]
            parent = entities.get(selected.get('part_of'))
            ordinal = next((name for name in ('bottom', 'middle', 'top') if name in selected['name']), None)
            ordinal_match = ordinal is not None and f'_{ordinal}_' in case['object_symbol']
            stop_binding_ids = [{key: sample['measurement'].get(key) for key in ('anchor_parent', 'anchor_part', 'current_part')}
                                for sample in public_samples[-2:]] if stop else []
            ids_match = all(ids['anchor_part'] == ids['current_part'] == selected_id
                            and ids['anchor_parent'] == selected.get('part_of') for ids in stop_binding_ids)
            task = original_task(case)
            fixture = case['object_symbol'].split('_bottom')[0].split('_middle')[0].split('_top')[0]
            clearance = receipt.get('fixture_contact_clearance') or {}
            clearance_compact = {key: clearance.get(key) for key in ('version', 'opening_before_m', 'opening_after_m',
                'outward_axis_xy', 'clearance_target_xyz', 'basis', 'view_restored', 'reason', 'error') if key in clearance}
            if clearance.get('release'):
                clearance_compact['release'] = motion_record(clearance['release'], fixture)
            if clearance.get('clearance_move'):
                clearance_compact['clearance_move'] = motion_record(clearance['clearance_move'], fixture)
            recovery = [motion_record(m, fixture) for m in motions[chunk_locations[-1]+1:]] if chunks else []
            after_contact = scored['after_actual_chunk'][-1]['label'] if trace_complete and chunks else None
            stop_label = stop_scores[-1]['label'] if stop_scores else None
            final_label = compact_label(first.get('private_after'))
            loss_phase = None
            preceding_label = stop_label if stop else after_contact
            losses = []
            for phase in PHASES[2:]:
                for sample in scored[phase]:
                    current = sample['label']
                    if preceding_label and current and preceding_label['satisfied'] is True and current['satisfied'] is False:
                        losses.append({'first_false_phase': phase, 'preceding': preceding_label, 'current': current})
                        loss_phase = loss_phase or phase
                    if current:
                        preceding_label = current
            if preceding_label and final_label and preceding_label['satisfied'] is True and final_label['satisfied'] is False:
                losses.append({'first_false_phase': 'between_last_saved_recovery_and_final', 'preceding': preceding_label, 'current': final_label})
                loss_phase = loss_phase or 'between_last_saved_recovery_and_final'
            metrology = (first.get('verification_measurements') or {}).get('articulation') or {}
            item = {'case': case['name'], 'episode': case['episode'], 'type': case['type'], 'state_sha256': case['state_sha256'],
                    'locator': {'original_ledger': source_ref['path'], 'captured_ledger': ref(ledger), 'line': line_index},
                    'actual_vla_chunks': len(chunks), 'actual_requested_controls': sum(m['requested_action_count'] for m in chunks),
                    'actual_executed_controls': sum(m['executed_action_count'] for m in chunks), 'every_chunk_complete5': complete5,
                    'server_chunk_execution': row.get('server_chunk_execution'), 'complete_after_chunk_private_trace': trace_complete,
                    'private_scoring_used_for_control': not all_diagnostic, 'private_stage_scores': scored,
                    'public_contact_stop': stop, 'private_at_stop': stop_label, 'private_after_contact': after_contact,
                    'public_stop_proof': proof, 'public_stop_last_two_saved_geometry': [geometry_record(s) for s in public_samples[-2:]],
                    'private_before': compact_label(first.get('private_before')), 'private_final': final_label,
                    'public_final': receipt.get('articulate_verified'), 'public_final_signed_extension_m': metrology.get('measured_signed_extension_m'),
                    'public_final_null_reason': null_reason(first), 'stop_already_strict_endpoint_false': bool(stop and stop_label and stop_label['satisfied'] is False),
                    'recovery_first_endpoint_loss_phase': loss_phase, 'saved_recovery_endpoint_losses': losses,
                    'fixture_contact_clearance': clearance_compact, 'post_contact_motion_evidence': recovery,
                    'last_contact_public_eef_pos': chunks[-1].get('final_eef_pos') if chunks else None,
                    'last_contact_public_gripper_opening': chunks[-1].get('gripper_opening') if chunks else None,
                    'post_contact_recovery': receipt.get('post_contact_recovery'),
                    'receipt_status': {key: receipt.get(key) for key in ('stop', 'executed', 'failure_reason', 'verification')},
                    'requested_binding': {'selected': first['selected'], 'selected_part': selected, 'parent': parent,
                        'ordinal': ordinal, 'requested_symbol': case['object_symbol'], 'requested_mode': case['mode'],
                        'requested_ordinal_matches_selected': ordinal_match,
                        'registered_subtask': case['subtask_prompt'], 'recorded_chunk_prompts': sorted({m['instruction'] for m in chunks}),
                        'public_callback_measured_phrase_reconstructed_from_frozen_runtime': selected['name'],
                        'callback_phrase_separately_serialized': False, 'stop_measurement_binding_ids': stop_binding_ids,
                        'selected_and_stop_measurement_IDs_match': ids_match, 'original_task': task,
                        'scope': 'Names, requested ordinal and persistent selected/current IDs match; this does not certify the physical identity of every fitted point-cloud plane'},
                    'original_labels_preserved': True}
            records.append(item)
            group = groups[case['type']]
            group['cases'] += 1; group['vla_chunks'] += len(chunks); group['executed_controls'] += item['actual_executed_controls']
            group['all_chunks_complete5'] += complete5; group['complete_chunk_private_trace'] += trace_complete
            group['public_stops'] += stop; group['stop_already_strict_endpoint_false'] += item['stop_already_strict_endpoint_false']
            group['recovery_endpoint_loss_cases'] += bool(losses)
            group['final_strict_endpoint_true'] += bool(final_label and final_label['satisfied'] is True)
            group['clearance_waypoint_failed'] += clearance.get('reason') == 'fixture_clearance_not_reached'
            group['view_restored'] += clearance.get('view_restored') is True
            for phase, scores in scored.items():
                for score in scores:
                    counts = phases[case['type']][phase]; counts['samples'] += 1
                    counts['true'] += bool(score['label'] and score['label']['satisfied'] is True)
                    counts['false'] += bool(score['label'] and score['label']['satisfied'] is False)
                    counts['unknown_or_scoring_error'] += score['label'] is None
            if item['public_final'] is None: nulls[case['type']][item['public_final_null_reason']] += 1
            valid_stop_proof = (not stop or (proof.get('stable_public_endpoint') is True
                and all(proof.get(key) is True for key in ('two_saved_verdicts_true', 'fresh_source_steps',
                    'passes_5mm_motion_gate', 'after_complete_contact_chunk'))))
            if not complete5 or not trace_complete or not all_diagnostic or stop != bool(stop_scores) or not task['registered_prompt_matches_original_language'] or not task['requested_endpoint_in_original_goals'] or not ids_match or not ordinal_match or not valid_stop_proof:
                anomalies.append({'case': case['name'], 'complete5': complete5, 'trace_complete': trace_complete,
                                  'all_diagnostic': all_diagnostic, 'stop_score_matches_receipt': stop == bool(stop_scores),
                                  'binding_ids_match': ids_match, 'ordinal_match': ordinal_match,
                                  'valid_stop_proof': valid_stop_proof, 'original_task': task})
    records_path = args.final_dir / 'fixture_stage_scoring_evidence.jsonl'
    records_path.write_text(''.join(json.dumps(record) + '\n' for record in records))
    table_path = args.final_dir / 'fixture_stage_scoring.tsv'
    columns = ['case', 'type', 'actual_vla_chunks', 'actual_executed_controls', 'every_chunk_complete5',
               'public_contact_stop', 'stop_already_strict_endpoint_false', 'recovery_first_endpoint_loss_phase',
               'private_stop', 'private_release', 'private_clearance', 'private_retreat', 'private_final', 'public_final']
    with table_path.open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter='\t'); writer.writeheader()
        for item in records:
            values = {key: item.get(key) for key in columns}
            values['private_final'] = item['private_final']['satisfied'] if item['private_final'] else None
            for short, phase in [('stop', PHASES[1]), ('release', PHASES[2]), ('clearance', PHASES[3]), ('retreat', PHASES[4])]:
                scores = item['private_stage_scores'][phase]
                values['private_'+short] = scores[-1]['label']['satisfied'] if scores and scores[-1]['label'] else None
            writer.writerow(values)
    report = {'scope': f'Exact {args.job_id} same20 development selection, saved actual contact and recovery stage labels; CPU only',
              'job_id': args.job_id, 'formal': ref(formal_path), 'producer': ref(__file__),
              'frozen_verifier': ref(args.source_snapshot / 'robots/libero/v5_verification.py'),
              'frozen_stage_scoring_hook': ref(args.source_snapshot / 'scripts/probe_v5_skill501_original.py'),
              'frozen_public_runtime': ref(args.source_snapshot / 'robots/libero/v5_runtime.py'),
              'registered_cases': 20, 'by_type': {key: dict(value) for key, value in groups.items()},
              'private_stage_sample_counts': {typ: {phase: dict(counts) for phase, counts in parts.items()} for typ, parts in phases.items()},
              'original_LIBERO_endpoint_semantics': semantics, 'null_categories': {key: dict(value) for key, value in nulls.items()},
              'anomalies': anomalies, 'stop_already_strict_endpoint_false_cases': [item['case'] for item in records if item['stop_already_strict_endpoint_false']],
              'recovery_endpoint_loss_cases': [item['case'] for item in records if item['saved_recovery_endpoint_losses']],
              'records': ref(records_path), 'table': ref(table_path), 'private_used_for_runtime_control': False,
              'causality_limit': 'Stage samples localize the first saved strict endpoint transition, not a per-control contact cause. Contact-point positions and release EEF trajectories are not saved; do not infer them',
              'source_or_saved_labels_changed': False, 'new_model_calls': 0, 'new_physics': 0, 'qualification_authorized': False}
    report_path = args.final_dir / 'fixture_stage_scoring_report.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'report': ref(report_path), 'records': ref(records_path), 'table': ref(table_path),
                      'by_type': report['by_type'], 'anomaly_count': len(anomalies),
                      'stop_already_false': report['stop_already_strict_endpoint_false_cases'],
                      'recovery_losses': report['recovery_endpoint_loss_cases']}))


if __name__ == '__main__':
    main()
