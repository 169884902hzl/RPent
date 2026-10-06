"""Account for saved public stops, recovery and final scoring; CPU only."""

from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_v5_drawer566_20261006'
FINAL = Path(__file__).resolve().parent / 'final_20261006T173457.788149Z'
FORMAL = FINAL / 'statistic/report.json'
PREVIOUS = ROOT / 'results/harness_v5/drawer565_monitor_CPU_20261006/final_20261006T172531.587332Z/statistic/report.json'
sys.path.insert(0, str(SOURCE))
from robots.libero.v5_verification import measured_fixture_endpoint


def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def rows(report):
    result = []
    for item in report['original_explicit_inputs']:
        if item['role'] == 'ledger' and item.get('exists'):
            path = Path(item['snapshot'])
            for index, line in enumerate(path.read_text().splitlines(), 1):
                result.append((json.loads(line), {'captured_ledger': ref(path), 'line': index, 'original_ledger': item['path']}))
    return result


def sample_record(sample):
    measure, evidence = sample['measurement'], sample['evidence']
    return {'chunk': sample['chunk'], 'verified': sample['verified'], 'source': sample['source'],
            'source_step': measure.get('source_step'), 'outward_axis_xy': measure.get('outward_axis_xy'),
            'signed_extension_m': evidence.get('measured_signed_extension_m'),
            'reason': evidence.get('reason'), 'verification_scope': evidence.get('verification_scope'),
            'endpoint_thresholds_m': evidence.get('endpoint_thresholds_m'),
            'frame': measure.get('frame'), 'moving': measure.get('moving'),
            'current_part': measure.get('current_part'), 'current_part_source_step': measure.get('current_part_source_step'),
            'current_part_bounds': measure.get('current_part_bounds'), 'point_counts': measure.get('point_counts'),
            'point_counts_by_camera': measure.get('point_counts_by_camera'),
            'depth_search_m': measure.get('depth_search_m')}


def null_category(first):
    metro = (first.get('verification_measurements') or {}).get('articulation') or {}
    if not metro:
        return 'metrology_not_run_' + str(first['receipt'].get('failure_reason', 'unrecorded'))
    missing = [phase + '_' + component for phase in ('before', 'after') for component in ('frame', 'moving')
               if not (metro.get(phase) or {}).get(component)]
    return 'missing_' + '+'.join(missing) if missing else 'measured_' + str(metro.get('reason', 'endpoint_result'))


formal, previous = json.loads(FORMAL.read_text()), json.loads(PREVIOUS.read_text())
new_rows = rows(formal)
old_lookup = {(row['case']['type'], row['case']['state_sha256']): row for row, _ in rows(previous)}
assert formal['complete'] and len(new_rows) == 20
items, anomalies = [], []
groups, nulls = defaultdict(Counter), defaultdict(Counter)
for row, locator in new_rows:
    case, first = row['case'], row['first_attempt']
    receipt = first['receipt']
    verification = first.get('verification_measurements') or {}
    samples = verification.get('drawer_public_stop', [])
    receipt_contact_stop = receipt.get('stop') == 'measured_fixture_endpoint'
    motions = first.get('motion_evidence', [])
    chunk_indices = [index for index, motion in enumerate(motions) if motion['name'] == 'vla_act_chunk']
    chunks = [motions[index] for index in chunk_indices]
    completed5 = all(chunk.get('executed_action_count') == chunk.get('requested_action_count') == 5 for chunk in chunks)
    after_contact = motions[chunk_indices[-1] + 1:] if chunk_indices else []
    post_motions = [{key: motion.get(key) for key in ('name', 'steps_used', 'actions_used', 'requested_action_count',
                    'executed_action_count', 'target_xyz', 'final_eef_pos', 'final_dist_m', 'waypoint_reached',
                    'failure_reason', 'terminated', 'truncated') if key in motion} for motion in after_contact]
    proof = {'available': False}
    if len(samples) >= 2 and all(sample['measurement'].get('moving') is not None for sample in samples[-2:]):
        last, preceding = samples[-1], samples[-2]
        a, b = preceding['measurement'], last['measurement']
        stable, evidence = measured_fixture_endpoint(a, b, case['mode'], drawer=True, signed_drawer_v6=True)
        delta = np.asarray(b['moving']['centre']) - a['moving']['centre']
        displacement = float(delta[:2] @ b['outward_axis_xy'])
        proof = {'available': True, 'contact_stop_chunk': last['chunk'],
                 'two_saved_verdicts_true': preceding['verified'] is True and last['verified'] is True,
                 'fresh_steps': a['source_step'] != b['source_step'],
                 'source_step_pair': [a['source_step'], b['source_step']],
                 'stable_public_endpoint': stable, 'stability_reason': evidence.get('reason'),
                 'outward_motion_between_last_two_m': displacement,
                 'passes_original_5mm_motion_gate': abs(displacement) <= .005,
                 'happened_after_complete_control_chunk': last['chunk'] == len(chunks) and completed5}
    reconstructed_callback_ready = (proof.get('available') and proof.get('stable_public_endpoint') is True
        and all(proof.get(key) is True for key in ('two_saved_verdicts_true', 'fresh_steps',
                 'passes_original_5mm_motion_gate', 'happened_after_complete_control_chunk')))
    callback_stop_with_lost_receipt = bool(not receipt_contact_stop and reconstructed_callback_ready
        and len(chunks) < 160 and chunks[-1].get('terminated') is False
        and chunks[-1].get('truncated') is False and receipt.get('failure_reason') == 'waypoint_not_reached')
    contact_stop = receipt_contact_stop or callback_stop_with_lost_receipt
    truth = (first.get('private_after') or {}).get('satisfied')
    public = receipt.get('articulate_verified')
    old = old_lookup[(case['type'], case['state_sha256'])]
    metro = verification.get('articulation') or {}
    old_first = old['first_attempt']
    item = {'case': case['name'], 'type': case['type'], 'episode': case['episode'], 'state_sha256': case['state_sha256'],
            'locator': locator, 'choices': {'path': str(Path(row['output_dir']) / 'choices.jsonl'), 'sha256': row['choices_sha256']},
            'actual_vla_chunks': len(chunks), 'actual_requested_controls': sum(chunk.get('requested_action_count', 0) for chunk in chunks),
            'actual_executed_controls': sum(chunk.get('executed_action_count', 0) for chunk in chunks),
            'every_chunk_complete5': completed5, 'server_chunk_execution': row.get('server_chunk_execution'),
            'receipt': receipt, 'public_contact_stop_triggered': contact_stop,
            'public_stop_explicit_in_receipt': receipt_contact_stop,
            'public_stop_inferred_from_frozen_callback_and_control_flow': callback_stop_with_lost_receipt,
            'stop_record_scope': 'Frozen callback readiness plus completed contact controls prove the early public break; post-contact waypoint exception occurs before receipt.update(**result)' if callback_stop_with_lost_receipt else 'Original receipt stop field',
            'public_stop_stage': 'after_completed_contact_chunk_before_post_contact_recovery' if contact_stop else None,
            'stop_sample_signed_extension_m': samples[-1]['evidence'].get('measured_signed_extension_m') if contact_stop else None,
            'stop_previous_signed_extension_m': samples[-2]['evidence'].get('measured_signed_extension_m') if contact_stop else None,
            'public_stop_samples': [sample_record(sample) for sample in samples], 'public_stop_proof': proof,
            'post_contact_motion_evidence': post_motions, 'post_contact_recovery': receipt.get('post_contact_recovery'),
            'post_recovery_public_verdict': public, 'post_recovery_geometry_category': null_category(first),
            'post_recovery_signed_extension_m': metro.get('measured_signed_extension_m'),
            'post_recovery_endpoint_evidence': metro,
            'private_final_endpoint_scoring': first.get('private_after'),
            'native_original_success_latched_diagnostic_only': row.get('native_original_success_latched'),
            'private_endpoint_at_public_stop_recorded': False,
            'public_stop_but_final_requested_endpoint_false': contact_stop and truth is False,
            'public_endpoint_at_stop_but_post_recovery_public_not_true': contact_stop and public is not True,
            'physical_endpoint_loss_during_recovery_confirmed': None,
            'recovery_causality_limit': 'No private requested-endpoint sample is saved at the public stop. A public stop followed by final false may be public measurement error or later endpoint loss; original native success latch is not a stop-time requested endpoint label',
            'same_state_SOURCE565': {'case': old['case']['name'], 'private_final': (old_first.get('private_after') or {}).get('satisfied'),
                                    'public_final': old_first['receipt'].get('articulate_verified'),
                                    'vla_chunks': sum(motion['name'] == 'vla_act_chunk' for motion in old_first.get('motion_evidence', []))},
            'original_labels_preserved': True}
    group = groups[case['type']]
    group['cases'] += 1
    group['public_stop'] += contact_stop
    group['public_stop_explicit_in_receipt'] += receipt_contact_stop
    group['public_stop_inferred_after_receipt_lost_to_recovery_exception'] += callback_stop_with_lost_receipt
    group['final_private_true'] += truth is True
    group['final_private_false'] += truth is False
    group['public_stop_and_final_private_true'] += contact_stop and truth is True
    group['public_stop_and_final_private_false'] += contact_stop and truth is False
    group['public_stop_and_post_recovery_public_true'] += contact_stop and public is True
    group['public_stop_and_post_recovery_public_false'] += contact_stop and public is False
    group['public_stop_and_post_recovery_public_null'] += contact_stop and public is None
    group['all_chunks_complete5'] += completed5
    group['actual_vla_chunks'] += len(chunks)
    group['actual_vla_controls'] += item['actual_executed_controls']
    group['old565_final_private_true'] += item['same_state_SOURCE565']['private_final'] is True
    group['old565_actual_vla_chunks'] += item['same_state_SOURCE565']['vla_chunks']
    if public is None:
        nulls[case['type']][item['post_recovery_geometry_category']] += 1
    if not completed5 or (contact_stop and (not proof.get('available') or not all(proof.get(key) is True for key in
            ('two_saved_verdicts_true', 'fresh_steps', 'passes_original_5mm_motion_gate', 'happened_after_complete_control_chunk'))
            or proof.get('stable_public_endpoint') is not True)):
        anomalies.append({'case': case['name'], 'chunks_complete5': completed5, 'proof': proof})
    items.append(item)

records = FINAL / 'public_stop_runtime_evidence.jsonl'
records.write_text(''.join(json.dumps(item) + '\n' for item in items))
table = FINAL / 'public_stop_runtime.tsv'
with table.open('w') as handle:
    writer = csv.DictWriter(handle, fieldnames=['case', 'type', 'actual_vla_chunks', 'actual_executed_controls',
        'public_contact_stop_triggered', 'public_stop_explicit_in_receipt',
        'public_stop_inferred_from_frozen_callback_and_control_flow', 'stop_previous_signed_extension_m',
        'stop_sample_signed_extension_m', 'post_recovery_public_verdict', 'private_final',
        'post_recovery_geometry_category', 'post_recovery_signed_extension_m', 'public_stop_but_final_requested_endpoint_false'], delimiter='\t')
    writer.writeheader()
    for item in items:
        writer.writerow({key: item['private_final_endpoint_scoring'].get('satisfied') if key == 'private_final' else item[key]
                         for key in writer.fieldnames})
report = {'scope': 'Exact4295 same20 development selection; actual complete5 controls and public contact stops with late private endpoint scoring',
          'formal': ref(FORMAL), 'previous_same20_full160': ref(PREVIOUS), 'producer': ref(__file__),
          'frozen_verifier': ref(SOURCE / 'robots/libero/v5_verification.py'),
          'registered_cases': 20, 'by_type': {key: dict(value) for key, value in groups.items()},
          'null_categories': {key: dict(value) for key, value in nulls.items()},
          'stop_count_scope': 'Explicit receipt stops and frozen-callback/control-flow stops are counted separately. Two recovery waypoint exceptions omit the earlier contact result because receipt.update(**result) was not reached',
          'public_stop_control_or_proof_anomalies': anomalies,
          'public_stop_then_final_endpoint_false_cases': [{'case': item['case'], 'episode': item['episode'],
             'chunks': item['actual_vla_chunks'], 'proof': item['public_stop_proof'],
             'post_recovery_public': item['post_recovery_public_verdict'],
             'post_recovery_signed_extension_m': item['post_recovery_signed_extension_m'],
             'private_final_endpoint_scoring': item['private_final_endpoint_scoring'],
             'post_contact_motion_evidence': item['post_contact_motion_evidence']}
             for item in items if item['public_stop_but_final_requested_endpoint_false']],
          'causality_limit': 'Stop-time private requested endpoint is not recorded. Public-positive-to-late-negative transitions alone cannot establish physical endpoint loss or attribute it to retreat',
          'same20_comparison_limit': 'Both runs preserve original first labels; changing public measurement frequency and contact stopping changes physics, so this is a controller development comparison',
          'records': ref(records), 'table': ref(table), 'private_used_for_runtime_control': False,
          'source_or_saved_labels_changed': False, 'new_model_calls': 0, 'new_physics': 0, 'qualification_authorized': False}
path = FINAL / 'public_stop_runtime_report.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'report': ref(path), 'records': ref(records), 'table': ref(table),
                  'by_type': report['by_type'], 'null_categories': report['null_categories'],
                  'anomalies': anomalies, 'public_stop_then_final_endpoint_false_cases': report['public_stop_then_final_endpoint_false_cases']}))
