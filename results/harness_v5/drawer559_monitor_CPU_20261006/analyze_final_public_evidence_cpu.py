"""Classify exact4254 saved public evidence without replay or relabeling."""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent
FINAL = BASE / 'final_20261006T164608.567363Z'
OUT = FINAL / 'public_evidence_analysis_v2'
OUT.mkdir(exist_ok=False)
report_path = FINAL / 'statistic/report.json'
report = json.loads(report_path.read_text())
diagnostics_path = FINAL / 'statistic/case_diagnostics.jsonl'
diagnostics = {row['case']: row for row in map(json.loads, diagnostics_path.read_text().splitlines())}
assert report['complete'] and report['overall']['recorded'] == 200
counts, task_counts, public_counts = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
private_before_counts, public_before_geometry_counts = defaultdict(Counter), defaultdict(Counter)
items, inputs, fp_items = [], [], []


def ref(path):
    path = Path(path)
    return {'path': str(path), 'exists': path.is_file(),
            **({'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} if path.is_file() else {})}


def null_category(metrology, receipt):
    if not metrology:
        return 'metrology_not_run_' + str(receipt.get('failure_reason', 'reason_not_recorded'))
    before, after = metrology.get('before') or {}, metrology.get('after') or {}
    if not before.get('frame') or not after.get('frame'):
        return 'missing_fixed_frame'
    if not before.get('moving') or not after.get('moving'):
        return 'missing_moving_part'
    reason = metrology.get('reason', 'reason_not_recorded')
    return 'measured_components_' + str(reason)


def selected_entities(public, metrology, selected):
    ids = {metrology.get('anchor_parent'), metrology.get('anchor_part'), metrology.get('current_part'), selected}
    return [entity for entity in (public or {}).get('entities', []) if entity.get('id') in ids]


for source_ref in report['original_explicit_inputs']:
    if source_ref['role'] != 'ledger' or not source_ref.get('exists'):
        continue
    snapshot = Path(source_ref['snapshot'])
    inputs.append(ref(snapshot))
    for line_number, line in enumerate(snapshot.read_text().splitlines(), 1):
        row = json.loads(line)
        case, first = row['case'], row['first_attempt']
        receipt = first['receipt']
        metrology = (first.get('verification_measurements') or {}).get('articulation')
        public = receipt.get('articulate_verified')
        private_before = (first.get('private_before') or {}).get('satisfied')
        private_after = (first.get('private_after') or {}).get('satisfied')
        typ, task = case['type'], case['episode']['task']
        label = 'null' if public is None else ('positive' if public is True else 'negative')
        public_counts[typ][label] += 1
        private_before_counts[typ][str(private_before)] += 1
        before_metrology = (metrology or {}).get('before') or {}
        after_metrology = (metrology or {}).get('after') or {}
        public_before_geometry_counts[typ][f"frame={bool(before_metrology.get('frame'))},moving={bool(before_metrology.get('moving'))}"] += 1
        fp = public is True and private_after is False
        if public is None:
            category = null_category(metrology, receipt)
            counts[typ][category] += 1
            task_counts[(typ, task)][category] += 1
            task_counts[(typ, task)]['private_after_' + str(private_after)] += 1
        elif fp:
            category = 'false_positive_saved_public_verdict'
        else:
            continue
        output = Path(row['output_dir'])
        rgbd = []
        for phase, raw in [('before', before_metrology), ('after', after_metrology)]:
            step = raw.get('source_step')
            step_source = 'original_public_metrology'
            if step is None:
                steps = [entity.get('source_step') for entity in (first.get('public_' + phase) or {}).get('entities', [])
                         if entity.get('source_step') is not None]
                if steps:
                    step, step_source = max(steps), 'original_public_entity_snapshot'
            if step is not None:
                for camera in ('agentview', 'wrist'):
                    rgbd.append({'phase': phase, 'camera': camera, 'source_step': step,
                                 'source_step_source': step_source,
                                 **ref(output / f'{camera}_world_high.npz' / f'{step:02d}.npz')})
        item = {'case': case['name'], 'type': typ, 'episode': case['episode'],
                'state_sha256': case['state_sha256'], 'original_ledger': source_ref['path'],
                'captured_ledger': str(snapshot), 'line': line_number,
                'category': category, 'saved_public_verdict': public,
                'private_labels_for_stratification_only': {'before_satisfied': private_before, 'after_satisfied': private_after},
                'diagnostic_root_cause_preserved': diagnostics[case['name']]['root_cause_category'],
                'original_receipt': receipt, 'original_public_metrology': metrology,
                'point_counts_before': before_metrology.get('point_counts'),
                'point_counts_after': after_metrology.get('point_counts'),
                'view_point_counts_before': before_metrology.get('point_counts_by_camera'),
                'view_point_counts_after': after_metrology.get('point_counts_by_camera'),
                'public_entities_before': selected_entities(first.get('public_before'), before_metrology, receipt.get('object')),
                'public_entities_after': selected_entities(first.get('public_after'), after_metrology, receipt.get('object')),
                'front_axis_serialized_before': 'front_axis' in before_metrology,
                'front_axis_serialized_after': 'front_axis' in after_metrology,
                'choices': {'path': str(output / 'choices.jsonl'), 'sha256': row['choices_sha256']},
                'public_RGBD_refs': rgbd,
                'private_joint_or_predicate_used_for_control': row.get('server_chunk_execution', {}).get('private_joint_or_predicate_used_for_control'),
                'physical_replay': False, 'saved_labels_changed': False}
        items.append(item)
        if fp:
            fp_items.append({'case': case['name'], 'episode': case['episode'],
                             'measured_extension_cm': (metrology or {}).get('measured_extension_cm'),
                             'choices': item['choices'], 'public_RGBD_refs': rgbd})

records = OUT / 'null_and_false_positive_public_evidence.jsonl'
records.write_text(''.join(json.dumps(row) + '\n' for row in items))
analysis = {'scope': 'Saved SOURCE558/job4254 public evidence classification only; private satisfied labels only for strata',
            'formal_report': ref(report_path), 'case_diagnostics': ref(diagnostics_path),
            'captured_ledger_refs': inputs, 'registered_cases': 200,
            'public_verdict_counts': {k: dict(v) for k, v in public_counts.items()},
            'private_before_strata': {k: dict(v) for k, v in private_before_counts.items()},
            'public_before_geometry_counts': {k: dict(v) for k, v in public_before_geometry_counts.items()},
            'null_categories_by_type': {k: dict(v) for k, v in counts.items()},
            'null_categories_by_task': [{'type': key[0], 'task': key[1], 'counts': dict(value)}
                                        for key, value in sorted(task_counts.items())],
            'false_positive_public_refs': fp_items, 'evidence_records': ref(records),
            'front_axis_policy': 'No serialized front_axis field; original normals and public bounds retained, no invented axis',
            'classification_policy': 'Missing fixed frame precedes missing moving part; absent metrology uses original receipt failure_reason',
            'view_ambiguity_policy': 'Only original reason is used; absent component is never asserted to be plane ambiguity',
            'private_qpos_exported': False, 'private_labels_used_to_repair_public_verdict': False,
            'new_model_calls': 0, 'new_physics': 0, 'saved_labels_changed': False,
            'producer': ref(__file__)}
path = OUT / 'public_evidence_analysis.json'
path.write_text(json.dumps(analysis, indent=2) + '\n')
print(json.dumps({'report': ref(path), 'records': ref(records),
                  'null_categories_by_type': analysis['null_categories_by_type'],
                  'null_categories_by_task': analysis['null_categories_by_task'],
                  'false_positive_public_refs': [{k: row[k] for k in ('case', 'episode', 'measured_extension_cm')}
                                                for row in fp_items],
                  'private_before_strata': analysis['private_before_strata']}))
