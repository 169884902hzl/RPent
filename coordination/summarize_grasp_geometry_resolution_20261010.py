"""Consolidate closed, same-state selection methods under the locked v3 rule."""

import argparse
from collections import Counter, defaultdict
import datetime
import hashlib
import json
from pathlib import Path

from coordination.summarize_registered_grasp_v3r9 import confusion, metric
from coordination.classify_grasp_contact_phases_20261010 import diagnose


LOCKED_V3 = 'd8ea8a435e20e00326d34be3e0be53a1ab7983fe411e114cd11e5234dfcdf81f'


def pin(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def transition(before, after):
    if before is None or after is None:
        return 'unknown_in_pair'
    if before == after:
        return 'both_success' if before else 'both_failure'
    return 'improved' if after else 'regressed'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--report', type=Path, action='append', required=True)
    parser.add_argument('--event-root', type=Path)
    parser.add_argument('--diagnose', action='store_true', help='read preserved private traces for failure analysis only')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reference = list(map(json.loads, (args.before / 'rows.jsonl').open()))
    indexed = {(r['type'], r['state_sha256']): r for r in reference}
    if len(indexed) != len(reference):
        raise ValueError('duplicate baseline state')
    reports = list(args.report)
    if args.event_root:
        reports.extend(p.parent for p in sorted(args.event_root.glob('*/publication.json')))
    groups, records, inputs, source_hashes = {}, [], [], {}
    for report in dict.fromkeys(reports):
        manifest_path, rows_path = report / 'manifest.json', report / 'rows.jsonl'
        document = json.loads(manifest_path.read_text())
        rows = list(map(json.loads, rows_path.open()))
        plans = {}
        for item in document['plans']:
            path = Path(item['path'])
            if pin(path)['sha256'] != item['sha256']:
                raise ValueError('selection plan changed')
            plan = json.loads(path.read_text())
            if plan['confirmation'] or plan['training_allowed'] or plan['PRO_files_read']:
                raise ValueError('selection evidence only')
            source = Path(plan['source_path'])
            if pin(source / 'robots/libero/v5_grasp_truth.py')['sha256'] != LOCKED_V3:
                raise ValueError('method does not use locked v3')
            for file in plan['source_snapshot']['files']:
                path_in_snapshot = source / file['relative_path']
                if path_in_snapshot not in source_hashes:
                    source_hashes[path_in_snapshot] = pin(path_in_snapshot)['sha256']
                if source_hashes[path_in_snapshot] != file['sha256']:
                    raise ValueError('registered snapshot file changed: ' + str(path_in_snapshot))
            group = path.parent.parent.parent.name + '/' + path.parent.parent.name
            condition = next(iter(plan['conditions'].values()))
            plans[group] = {'plan': pin(path), 'source_identity': pin(source / 'source_identity_v3r9.json'),
                            'source_files': plan['source_snapshot']['files'],
                            'contact_execution_kind': 'analytic_contact' if
                                condition.get('overrides', {}).get('analytic_grasp_v1') else 'pi05_contact'}
        inputs.append({'manifest': pin(manifest_path), 'rows': pin(rows_path)})
        for group, value in document['groups'].items():
            if group in groups:
                raise ValueError('duplicate method report')
            selected = [r for r in rows if r['group'] == group]
            n = value['registered_n']
            if value['pending_n'] != 0 or len(selected) != n or n < 100:
                raise ValueError('method is not a closed >=100-state selection')
            if len({r['state_sha256'] for r in selected}) != n:
                raise ValueError('duplicate state within method')
            types = {r['type'] for r in selected}
            if len(types) != 1:
                raise ValueError('one object category per method expected')
            paired = []
            for row in selected:
                before = indexed[(row['type'], row['state_sha256'])]
                paired.append({**row, 'before_v3': before['registered_v3'],
                    'transition': transition(before['registered_v3'], row['registered_v3']),
                    'before_failure_reason': before['failure_reason']})
            physical = metric(sum(r['registered_v3'] is True for r in paired), n)
            public = confusion(paired, 'registered_v3')
            exceeds_values = physical['rate'] >= .90 and public['agreement_all_registered']['rate'] >= .95
            groups[group] = {**plans[group], 'type': next(iter(types)), 'registered_n': n,
                'v3_success': physical, 'v3_unknown': sum(r['registered_v3'] is None for r in paired),
                'public_verifier': public, 'paired_to_servo_only_v3': dict(Counter(r['transition'] for r in paired)),
                'failure_reasons': dict(Counter(r['failure_reason'] for r in paired)),
                'descend_before': sum(r['before_failure_reason'] == 'analytic_descend_not_reached' for r in paired),
                'descend_after': sum(r['failure_reason'] == 'analytic_descend_not_reached' for r in paired),
                'formerly_descend_failure_outcomes': dict(Counter(
                    'v3_success' if r['registered_v3'] is True else
                    'v3_unknown' if r['registered_v3'] is None else
                    r['failure_reason'] or 'closed_but_v3_hold_failed'
                    for r in paired if r['before_failure_reason'] == 'analytic_descend_not_reached')),
                'old_exclusive_v2_secondary': dict(Counter(str(r['exclusive_v2']) for r in paired)),
                'selection_meets_threshold_values_descriptive_only': exceeds_values,
                'confirmation_passed': False}
            records.extend(paired)
    diagnostic_rows, diagnostic_inputs, cached = [], {}, {}
    if args.diagnose:
        for row in records:
            path = Path(row['input'])
            if path not in cached:
                cached.clear()
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != row['input_sha256']:
                    raise ValueError('closed physical ledger changed')
                cached[path] = data.splitlines()
                diagnostic_inputs[str(path)] = pin(path)
            raw = json.loads(cached[path][row['line'] - 1])
            if raw['case']['name'] != row['case']:
                raise ValueError('diagnostic case mismatch')
            outcome = 'success' if row['registered_v3'] is True else 'failure' if row['registered_v3'] is False else 'unknown'
            item = {'case': row['case'], 'category': row['type'], 'state_sha256': row['state_sha256'],
                    'method': groups[row['group']]['contact_execution_kind'],
                    'physical_outcome': outcome}
            result = diagnose(raw, item)
            if result['contact_failure_class'] == 'historical_end_success_retained':
                result['contact_failure_class'] = 'locked_v3_success'
            result.update(group=row['group'], v3_outcome=outcome, input=diagnostic_inputs[str(path)], line=row['line'])
            result.pop('historical_physical_outcome', None)
            diagnostic_rows.append(result)
        for group, value in groups.items():
            selected = [r for r in diagnostic_rows if r['group'] == group]
            value['contact_phase_diagnosis_all_registered'] = dict(Counter(r['contact_failure_class'] for r in selected))
            value['contact_phase_diagnosis_v3_failure'] = dict(Counter(r['contact_failure_class'] for r in selected
                                                                      if r['v3_outcome'] == 'failure'))
            value['trace_missing_n'] = sum(r['saved_phase_samples'] == 0 for r in selected)
    by_type = defaultdict(list)
    for group, result in groups.items():
        by_type[result['type']].append((group, result))
    candidates = {}
    for category, methods in by_type.items():
        group, value = max(methods, key=lambda x: (x[1]['v3_success']['k'],
            x[1]['public_verifier']['agreement_all_registered']['k']))
        candidates[category] = {'best_observed_selection_method': group, 'success': value['v3_success'],
            'public_agreement': value['public_verifier']['agreement_all_registered'],
            'selection_methods_exceeding_threshold_values_descriptive_only':
                [g for g, v in methods if v['selection_meets_threshold_values_descriptive_only']],
            'confirmation_passed': False}
    args.output.mkdir(parents=True, exist_ok=False)
    producer_copy = args.output / Path(__file__).name
    producer_copy.write_bytes(Path(__file__).read_bytes())
    output_rows = args.output / 'rows.jsonl'
    output_rows.write_text(''.join(json.dumps(row) + '\n' for row in records))
    diagnostic_path = args.output / 'private_contact_diagnosis.jsonl'
    if args.diagnose:
        diagnostic_path.write_text(''.join(json.dumps(row) + '\n' for row in diagnostic_rows))
    manifest = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'before': pin(args.before / 'rows.jsonl'), 'inputs': inputs, 'producer': pin(producer_copy),
        'records': pin(output_rows), 'groups': groups, 'class_selection': candidates,
        'locked_v3_sha256': LOCKED_V3, 'internal_thresholds': {'overall': .95, 'class': .90, 'agreement': .95},
        'confirmation_performed_by_this_report': False, 'training_allowed': False,
        'selection_threshold_is_not_an_admission_gate': True,
        'private_diagnostics': {'enabled': args.diagnose, 'records': pin(diagnostic_path) if args.diagnose else None,
            'dependency': pin(Path(diagnose.__code__.co_filename)), 'inputs': list(diagnostic_inputs.values()),
            'runtime_or_training_use': False},
        'limits': ['All rates retain unknown truth and missing public measurements in registered denominators.',
                  'Best observed selection performance is not an independent confirmation result.',
                  'Cross-method rows share states and must not be pooled as independent trials.',
                  'Private labels are measurement-only; no private object poses enter control.']}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    lines = ['# 扰动抓取同状态选择批汇总', '', '固定 v3；以下全部为选择批，尚非确认或冻结证据。', '',
        '| 类别 / 方法 | 成功 / 注册数 | Wilson 95% | 公开一致 | FP / FN / 公开缺测 / 真值unknown | 改善 / 退步 | 下降未到位：前→后 |',
        '|---|---:|---|---:|---|---|---|']
    for group, value in sorted(groups.items(), key=lambda item: (item[1]['type'], item[0])):
        m, c, t = value['v3_success'], value['public_verifier'], value['paired_to_servo_only_v3']
        lo, hi = m['wilson95']
        lines.append(f"| {value['type']} / {group} | {m['k']}/{m['n']} | {lo:.1%}–{hi:.1%} | "
            f"{c['agreement_all_registered']['k']}/{m['n']} | {c['fp']} / {c['fn']} / "
            f"{c['public_null_on_known_truth']} / {value['v3_unknown']} | {t.get('improved', 0)} / "
            f"{t.get('regressed', 0)} | {value['descend_before']}→{value['descend_after']} |")
    lines.extend(['', '方法间共享选择状态，不能把各方法试次相加当作独立总体。所有源码、计划、逐次记录 SHA 在 manifest.json。',
                  '内部门槛保持总体≥95%、各类≥90%、验证器一致率≥95%；本报告不宣称准入或冻结。'])
    (args.output / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'methods': len(groups), 'records': len(records), 'class_selection': candidates}))


if __name__ == '__main__':
    main()
