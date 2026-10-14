"""Compare registered contact methods, keeping physical and verifier axes separate."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from scripts.summarize_v5_grasp449_20261005 import wilson


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def diagnose(row):
    stage = row.get('first_attempt') or {}
    receipt = stage.get('receipt') or {}
    truth = stage.get('private_hold_truth_v2', {}).get('success')
    public = receipt.get('grasp_verified')
    reason = receipt.get('failure_reason')
    plan = receipt.get('analytic_grasp_plan') or {}
    baseline = next((e for e in (stage.get('public_before') or {}).get('entities', [])
                     if e.get('id') == receipt.get('object')), None)
    prior_xy_distance = None
    if baseline and plan.get('xyz'):
        prior_xy_distance = math.sqrt(sum(max(baseline['lower'][i] - plan['xyz'][i],
            plan['xyz'][i] - baseline['upper'][i], 0.) ** 2 for i in (0, 1)))
    phase = row.get('private_grasp_phase', {}).get('all_supports_v2') or {}
    samples = phase.get('samples') or []
    observed_lift = phase.get('true_sustained_grasp_during_skill')
    if not observed_lift and samples and phase.get('reference'):
        reference = phase['reference']
        observed_lift = any(s.get('finger_contact') and
            s.get('lower_extent_m', reference['lower_extent_m']) - reference['lower_extent_m'] >= .03
            and s.get('all_non_gripper_contact_geoms') == [] for s in samples)
    if truth is True:
        physical = 'success'
    elif not stage:
        physical = 'public_binding_or_precondition_failure'
    elif reason and ('not_reached' in reason or reason == 'waypoint_not_reached'):
        physical = 'not_reached'
    elif reason in ('measured_width_exceeds_gripper', 'pan_handle_not_measured',
                    'rim_not_measured', 'rim_patch_not_measured', 'height_not_measured',
                    'current_cloud_missing', 'analytic_refinement_missing'):
        physical = 'public_geometry_precondition_failure'
    elif truth is False and observed_lift is True:
        end_checks = stage.get('private_hold_truth_v2', {}).get('checks') or []
        if end_checks and all(s.get('finger_contact') is True for s in end_checks):
            physical = ('lifted_then_non_gripper_contact' if any(
                s.get('all_non_gripper_contact_geoms') for s in end_checks)
                else 'lifted_end_clearance_or_hold_window_failed')
        elif end_checks and all(s.get('finger_contact') is False for s in end_checks):
            physical = 'lifted_then_dropped'
        else:
            physical = 'lifted_end_hold_unstable_or_unmeasured'
    elif truth is False and phase.get('true_sustained_grasp_during_skill') is False:
        physical = 'not_gripped'
    elif truth is False:
        physical = 'no_hold_contact_phase_unknown'
    else:
        physical = 'private_truth_unknown'
    error = ('false_positive' if public is True and truth is False else
             'false_negative' if public is False and truth is True else
             'public_unmeasured' if public is None else 'agreement' if public == truth else
             'private_truth_unknown')
    return {'case': row['case']['name'], 'category': row['case']['type'],
        'method': row['case']['condition'], 'layout': row['case']['registered_layout_state'],
        'state_sha256': row['case']['state_sha256'], 'status': row['status'],
        'private_success': truth, 'public_verified': public, 'physical_outcome': physical,
        'verifier_outcome': error, 'failure_reason': reason or row.get('binding_error'),
        'sim_steps': receipt.get('sim_steps_used'), 'output_dir': row['output_dir'],
        'precontact_plan_outside_original_measured_xy_m': prior_xy_distance,
        'public_precontact_identity_jump': prior_xy_distance > .02 if prior_xy_distance is not None else None,
        'control_phase_trace_available': bool(phase), 'training_allowed': False}


def summarize(records, planned):
    matrix = Counter()
    positives = negatives = known = successes = 0
    for row in records:
        truth, public = row['private_success'], row['public_verified']
        if not isinstance(truth, bool):
            matrix['private_truth_unknown'] += 1
            continue
        known += 1
        successes += int(truth)
        positives += int(truth)
        negatives += int(not truth)
        if isinstance(public, bool):
            matrix['tp' if truth and public else 'fn' if truth else 'fp' if public else 'tn'] += 1
        else:
            matrix['unmeasured_positive' if truth else 'unmeasured_negative'] += 1
    observed = len(records)
    agreement = matrix['tp'] + matrix['tn']
    return {'registered': planned, 'recorded': observed, 'pending': planned - observed,
        'true_successes': successes, 'known_private_truth': known,
        'success_rate_over_recorded': successes / observed if observed else None,
        'success_wilson_95CI_over_recorded': wilson(successes, observed),
        'known_truth_success_rate': successes / known if known else None,
        'confusion': dict(matrix), 'agreement_count': agreement,
        'agreement_denominator': known, 'agreement_rate': agreement / known if known else None,
        'agreement_wilson_95CI': wilson(agreement, known),
        'false_positive': {'count': matrix['fp'], 'known_negatives': negatives,
            'rate_over_known_negatives': matrix['fp'] / negatives if negatives else None},
        'false_negative': {'count': matrix['fn'], 'known_positives': positives,
            'rate_over_known_positives': matrix['fn'] / positives if positives else None},
        'physical_outcomes': dict(Counter(r['physical_outcome'] for r in records)),
        'failure_reasons': dict(Counter(r['failure_reason'] for r in records if r['failure_reason'])),
        'mean_sim_steps': sum(r['sim_steps'] or 0 for r in records) / observed if observed else None,
        'phase_trace_coverage': sum(r['control_phase_trace_available'] for r in records),
        'public_precontact_identity_jump_count': sum(r['public_precontact_identity_jump'] is True for r in records),
        'identity_jump_interpretation': 'diagnostic flag: refined contact point outside prior selected bounds by >2cm; not itself a private wrong-object label',
        'interpretation': 'selection only; unknown/absent verdicts never filled from truth; abstentions stay in known-truth agreement denominator'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, action='append', required=True)
    parser.add_argument('--exclude-cell', action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    observed_start = datetime.now(timezone.utc).isoformat()
    args.output.mkdir(parents=True, exist_ok=False)
    closed = args.output / 'closed_ledgers'
    closed.mkdir()
    planned, records, groups, refs, faults, tails = {}, {}, Counter(), [], [], []
    for root in args.root:
        for manifest in sorted(root.glob('*/preparation/selection.json')):
            cell = manifest.parent.parent
            if cell.name in args.exclude_cell:
                continue
            plan = json.loads(manifest.read_text())
            if plan['confirmation'] or plan['training_allowed'] or plan['PRO_files_read']:
                raise ValueError('only original-layout method selections are accepted')
            refs.append(ref(manifest))
            for case in plan['cases']:
                if case['name'] in planned:
                    raise ValueError('duplicate registered case')
                planned[case['name']] = case
                groups[(case['type'], case['condition'])] += 1
            for ledger in sorted(cell.glob('job*/part*/probe/episodes.jsonl')):
                raw = ledger.read_bytes()
                boundary = raw.rfind(b'\n') + 1
                name = hashlib.sha256(str(ledger).encode()).hexdigest()[:20] + '.jsonl'
                snapshot = closed / name
                snapshot.write_bytes(raw[:boundary])
                refs.append({'source': str(ledger), 'closed_snapshot': ref(snapshot),
                    'trailing_unclosed_bytes': len(raw) - boundary})
                if len(raw) > boundary:
                    tails.append({'path': str(ledger), 'bytes': len(raw) - boundary})
                for line in raw[:boundary].splitlines():
                    row = json.loads(line)
                    case = row['case']
                    if case != planned.get(case['name']):
                        raise ValueError('case differs from registered method/layout')
                    if row.get('infrastructure_failure') or row.get('status') == 'infrastructure_error':
                        faults.append({'case': case['name'], 'source': ref(snapshot), 'status': row['status']})
                        continue
                    if case['name'] in records:
                        raise ValueError('duplicate physical outcome')
                    records[case['name']] = diagnose(row)
    by_group = defaultdict(list)
    for record in records.values():
        by_group[(record['category'], record['method'])].append(record)
    output_rows = args.output / 'attempts.jsonl'
    output_rows.write_text(''.join(json.dumps(row) + '\n' for row in records.values()))
    report = {'observed_start_utc': observed_start,
        'observed_end_utc': datetime.now(timezone.utc).isoformat(),
        'registered': len(planned), 'recorded': len(records),
        'groups': {'/'.join(group): summarize(by_group[group], count) for group, count in groups.items()},
        'infrastructure_attempts': faults, 'unclosed_tails': tails, 'inputs': refs,
        'records': ref(output_rows), 'source': ref(Path(__file__)),
        'truth': 'post-execution sustained exclusive gripper hold, all-current-supports/2; diagnostic only',
        'limits': ['Without control-phase trace, no-hold outcomes do not distinguish missed closure from lift-and-drop.',
                   'Live completed prefixes are selection data, never confirmation or freeze evidence.'],
        'confirmation': False, 'training_allowed': False}
    manifest = args.output / 'manifest.json'
    manifest.write_text(json.dumps(report, indent=2) + '\n')
    lines = [
        'Contact-method selection; every outcome is retained. Not confirmation or freeze evidence.',
        '',
        '| category / method | recorded / registered | truth success | Wilson 95% CI | public agreement / known truth | FP / negatives | FN / positives | public null |',
        '|---|---:|---:|---|---:|---:|---:|---:|',
    ]
    for name, group in report['groups'].items():
        interval = group['success_wilson_95CI_over_recorded']
        ci = ', '.join(f'{value:.4f}' for value in interval) if interval else 'pending'
        fp, fn, matrix = group['false_positive'], group['false_negative'], group['confusion']
        lines.append(f"| {name} | {group['recorded']}/{group['registered']} | "
            f"{group['true_successes']}/{group['recorded']} | [{ci}] | "
            f"{group['agreement_count']}/{group['agreement_denominator']} | "
            f"{fp['count']}/{fp['known_negatives']} | {fn['count']}/{fn['known_positives']} | "
            f"{matrix.get('unmeasured_positive', 0) + matrix.get('unmeasured_negative', 0)} |")
    lines.extend(['',
        'Success rates include every recorded registered attempt; no binding abstention is replaced by success.',
        'Public null is excluded from FP/FN but retained as disagreement in the known-truth agreement denominator.',
        'Unknown contact phases stay unknown; they are not assigned to missed closure or lift-and-drop.',
        '', '| category / method | physical outcome | count |', '|---|---|---:|'])
    for name, group in report['groups'].items():
        for outcome, count in group['physical_outcomes'].items():
            lines.append(f'| {name} | {outcome} | {count} |')
    (args.output / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'manifest': ref(manifest), 'registered': len(planned), 'recorded': len(records),
        'groups': {key: {k: v[k] for k in ('recorded', 'true_successes', 'success_wilson_95CI_over_recorded',
            'agreement_count', 'agreement_denominator', 'false_positive', 'false_negative', 'physical_outcomes')}
            for key, v in report['groups'].items()}}))


if __name__ == '__main__':
    main()
