"""Describe all39 preserved4254 endpoint failures using saved scoring labels."""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


OUT = Path(__file__).resolve().parent / 'final_20261006T164608.567363Z'
formal_path = OUT / 'statistic/report.json'
formal = json.loads(formal_path.read_text())
semantics_path = OUT / 'false_positive_semantics_report.json'
semantics = json.loads(semantics_path.read_text())['semantics']
diagnostics_path = OUT / 'statistic/case_diagnostics.jsonl'
diagnostics = {row['case']: row for row in map(json.loads, diagnostics_path.read_text().splitlines())}
counts, task_counts, records = defaultdict(Counter), defaultdict(Counter), []


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


for ledger in formal['original_explicit_inputs']:
    if ledger['role'] != 'ledger' or not ledger.get('exists'):
        continue
    snapshot = Path(ledger['snapshot'])
    for line_number, line in enumerate(snapshot.read_text().splitlines(), 1):
        row = json.loads(line)
        case, first = row['case'], row['first_attempt']
        before, after = first.get('private_before') or {}, first.get('private_after') or {}
        if after.get('satisfied') is not False:
            continue
        typ, mode, task = case['type'], case['mode'], case['episode']['task']
        assert before['satisfied'] is False
        qb, qa = before['joint_qpos'][0][0], after['joint_qpos'][0][0]
        cabinet = 'WoodenCabinet' if case['object_symbol'].startswith('wooden_cabinet_') else 'WhiteCabinet'
        cutoff = semantics[cabinet]['open_qpos_strictly_less_than_m'] if mode == 'open' else semantics[cabinet]['close_qpos_strictly_greater_than_m']
        gap = qa - cutoff if mode == 'open' else cutoff - qa
        receipt = first['receipt']
        motions = first.get('motion_evidence') or []
        chunks = [motion for motion in motions if motion.get('name') == 'vla_act_chunk']
        server = row.get('server_chunk_execution') or {}
        native = row.get('native_original_success_latched') is True
        raw_native = server.get('raw_native_success_controls', 0)
        assert native == (raw_native > 0)
        pattern = 'original_native_success_signal_observed_final_endpoint_false' if native else 'original_native_success_signal_not_observed_final_endpoint_false'
        state_pattern = ('final_opening_under25mm' if qa >= -.025 else 'final_partial_opening25to140mm') if mode == 'open' else (
            'final_close_gap_under15mm' if qa >= -.015 else 'final_still_fully_open_at_least140mm' if qa <= -.14 else 'final_partial_close_gap15to140mm')
        counter = counts[typ]
        counter['physical_endpoint_failures'] += 1
        counter[pattern] += 1
        counter[state_pattern] += 1
        counter['recovery_waypoint_not_reached'] += receipt.get('failure_reason') == 'waypoint_not_reached'
        counter['public_positive'] += receipt.get('articulate_verified') is True
        counter['public_negative'] += receipt.get('articulate_verified') is False
        counter['public_null'] += receipt.get('articulate_verified') is None
        counter['final_target_motion_opposes_request'] += (qb - qa if mode == 'open' else qa - qb) < 0
        full = len(chunks) == 160 and sum(m.get('executed_action_count', 0) for m in chunks) == 800
        counter['full160x5_controls'] += full
        task_counts[(typ, task)][pattern] += 1
        task_counts[(typ, task)][state_pattern] += 1
        metrology = (first.get('verification_measurements') or {}).get('articulation') or {}
        selected = receipt['object']
        public_entities = {phase: next((entity for entity in first['public_' + phase]['entities']
            if entity['id'] == selected), None) for phase in ('before', 'after')}
        records.append({'case': case['name'], 'episode': case['episode'], 'type': typ, 'mode': mode,
            'goal_symbol': case['object_symbol'], 'joint_names': after['joint_names'],
            'before_scoring_qpos_m': qb, 'after_scoring_qpos_m': qa,
            'before_private_satisfied_preserved': False, 'after_private_satisfied_preserved': False,
            'private_label_times': {'before': before['sim_time'], 'after': after['sim_time'],
                'later_after_first_attempt_snapshot': (row.get('after_first_attempt_snapshot') or {}).get('sim_state', [None])[0]},
            'official_endpoint_cutoff_m': cutoff, 'endpoint_gap_mm': gap * 1000,
            'scoring_target_motion_in_requested_direction_mm': (qb - qa if mode == 'open' else qa - qb) * 1000,
            'saved_native_original_task_success_latched': row.get('native_original_success_latched'),
            'native_original_success_control_flags_count': raw_native,
            'before_original_task_success_once': (row.get('before_first_attempt_snapshot') or {}).get('counters', {}).get('success_once'),
            'after_original_task_success_once': (row.get('after_first_attempt_snapshot') or {}).get('counters', {}).get('success_once'),
            'observed_signal_pattern': pattern, 'final_state_description': state_pattern,
            'original_public_verdict': receipt.get('articulate_verified'), 'original_receipt': receipt,
            'public_extension_cm': metrology.get('measured_extension_cm'), 'public_selected_entities': public_entities,
            'original_diagnostic_category': diagnostics[case['name']]['root_cause_category'],
            'full160x5_controls': full, 'server_chunk_execution': server,
            'post_contact_recovery_public_motion_summaries': [{key: motion.get(key) for key in
                ('name', 'target_xyz', 'final_eef_pos', 'final_dist_m', 'steps_used', 'max_steps')}
                for motion in motions if motion.get('name') != 'vla_act_chunk'],
            'original_ledger': ledger['path'], 'captured_ledger': {**ref(snapshot), 'line': line_number},
            'choices': {'path': str(Path(row['output_dir']) / 'choices.jsonl'), 'sha256': row['choices_sha256']},
            'label_or_control_changed': False})

assert len(records) == 39
assert counts['drawer_open']['physical_endpoint_failures'] == 19 and counts['drawer_close']['physical_endpoint_failures'] == 20
record_path = OUT / 'physical_failure39_evidence.jsonl'
record_path.write_text(''.join(json.dumps(row) + '\n' for row in records))
analysis = {'scope': 'Original SOURCE558/job4254 selection; all39 retained private-after endpoint failures, scoring diagnosis only',
    'formal_report': ref(formal_path), 'official_semantics': ref(semantics_path),
    'records': ref(record_path), 'by_type': {key: dict(value) for key, value in counts.items()},
    'by_task': [{'type': key[0], 'task': key[1], 'counts': dict(value)} for key, value in sorted(task_counts.items())],
    'primary_finding': '32of39 final endpoint failures follow an observed original-native-task success signal; fixed160chunks execute800controls fully and do not stop on native flags',
    'causal_limit': 'This is not a requested-endpoint measurement at each chunk. No per-control target-joint trace is saved; loss during later VLA controls versus post-contact recovery cannot be separated from these records',
    'control_relationship': 'All39 complete160x5, no external truncation, native-goal shortcut or private predicate in control. Nine also have recovery waypoint_not_reached; that does not replace the saved endpoint label',
    'private_qpos_scope': 'Before/after scoring diagnosis only; not a runtime feature, public replacement label or new stopping rule',
    'state_bins_scope': 'Final-state descriptions, not new success criteria; official original predicates and all original labels are preserved',
    'new_physics': 0, 'new_model_calls': 0, 'new_training_rows': 0,
    'labels_thresholds_or_control_changed': False, 'producer': ref(Path(__file__).resolve())}
path = OUT / 'physical_failure39_report.json'
path.write_text(json.dumps(analysis, indent=2) + '\n')
table = OUT / 'physical_failure39.tsv'
table.write_text('case\ttype\tbefore_qpos_m\tafter_qpos_m\tendpoint_gap_mm\tnative_success_latched\traw_native_success_control_flags\tfinal_state\tpublic_verdict\trecovery_failure\n' + ''.join(
    f"{r['case']}\t{r['type']}\t{r['before_scoring_qpos_m']:.9f}\t{r['after_scoring_qpos_m']:.9f}\t{r['endpoint_gap_mm']:.3f}\t{r['saved_native_original_task_success_latched']}\t{r['native_original_success_control_flags_count']}\t{r['final_state_description']}\t{r['original_public_verdict']}\t{r['original_receipt'].get('failure_reason')}\n"
    for r in records))
print(json.dumps({'report': ref(path), 'table': ref(table), 'records': ref(record_path), 'by_type': analysis['by_type'], 'by_task': analysis['by_task']}))
