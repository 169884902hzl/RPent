"""Separate missed closure, slipping and lift loss using saved private traces only."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def pad_contacts(sample):
    geoms = sample.get('finger_geoms')
    if geoms is None:
        return None
    return (any('finger1_pad_collision' in g for g in geoms)
            and any('finger2_pad_collision' in g for g in geoms))


def diagnose(raw, item):
    first = raw.get('first_attempt') or {}
    receipt = first.get('receipt') or {}
    phase = raw.get('private_grasp_phase') or first.get('private_grasp_phase') or {}
    samples = phase.get('samples') or []
    diagnostic_controls=(first.get('private_setup_hold') or {}).get('diagnostic_actions',0)
    recorded_controls=len(samples)
    if diagnostic_controls and phase.get('trace_version')=='every-executed-skill-control/1-dev':
        # The existing private hold is recorded too, but cannot masquerade
        # as a contact/close/lift action selected by the public skill.
        samples=samples[:-diagnostic_controls]
    reference = phase.get('reference') or {}
    output = {'case': item['case'], 'category': item['category'], 'method': item['method'],
              'state_sha256': item['state_sha256'], 'failure_reason': receipt.get('failure_reason'),
              'historical_physical_outcome': item['physical_outcome'],
              'saved_phase_samples': len(samples), 'private_diagnostic_only': True,
              'recorded_controls_including_private_hold':recorded_controls,
              'private_hold_controls_excluded_from_contact_stage':diagnostic_controls,
              'training_allowed': False, 'v3_score_not_inferred_from_lower_extent_proxy': True}
    final_truth = (first.get('private_hold_truth_v3') or
                   (first.get('private_setup_hold') or {}).get('truth_v3') or {})
    final_failures = Counter()
    for check in final_truth.get('checks', []):
        if check.get('unknown_reason'):
            final_failures['unknown:' + check['unknown_reason']] += 1
        if check.get('clearance_m') is not None and check['clearance_m'] < final_truth['required_clearance_m']:
            final_failures['whole_object_not_clear_of_original_support'] += 1
        if check.get('dual_finger_contact') is False:
            final_failures['dual_finger_contact_missing'] += 1
        if (check.get('relative_com_displacement_m') is not None
                and check['relative_com_displacement_m'] > final_truth['required_relative_displacement_m']):
            final_failures['object_moves_relative_to_gripper'] += 1
        if check.get('counterfactual_load_bearing_support') is True:
            final_failures['supported_by_non_gripper_geometry'] += 1
    output['registered_final_window_failure_samples'] = dict(final_failures)
    output['registered_final_window_status'] = final_truth.get('status')
    # A geometry/servo rejection before closure is not a missed physical grasp.
    if item['method'].startswith('analytic') and not receipt.get('analytic_close'):
        output['contact_failure_class'] = 'closure_not_executed; binding_geometry_or_servo_rejection'
        return output
    if not samples or not reference:
        output['contact_failure_class'] = ('no_physical_control_executed' if reference
            and phase.get('control_steps_sampled') == 0 and not first.get('physically_executed')
            else 'whole_skill_trace_not_saved')
        return output
    pads = [pad_contacts(s) for s in samples]
    two = [i for i, contact in enumerate(pads) if contact is True]
    base = reference.get('original_support_plane_z_m')
    plane_measured = base is not None
    if base is None:
        base = reference.get('lower_extent_m')
    rises = [s.get('lower_extent_m', base) - base if base is not None else None for s in samples]
    lifts = [i for i in two if rises[i] is not None and rises[i] >= .03]
    slip = []
    for a, b in zip(two, two[1:]):
        if b != a + 1:
            continue
        left, right = samples[a].get('relative_com_tcp'), samples[b].get('relative_com_tcp')
        if left is not None and right is not None:
            slip.append(float(np.linalg.norm(np.asarray(right) - left)))
    maximum_slide = None
    if two:
        origin = samples[two[0]].get('relative_com_tcp')
        relatives = [s['relative_com_tcp'] for s in samples[two[0]:]
                     if s.get('relative_com_tcp') is not None]
        if origin is not None and relatives:
            maximum_slide = max(float(np.linalg.norm(np.asarray(r) - origin)) for r in relatives)
    output.update(two_pad_contact_frames=len(two), lifted_with_two_pad_contact_frames=len(lifts),
                  lift_basis='original_measured_support_plane' if plane_measured else
                             'initial_collision_lower_extent_displacement_proxy_diagnostic_only',
                  maximum_observed_rise_m=max((r for r in rises if r is not None), default=None),
                  maximum_consecutive_pad_relative_step_m=max(slip, default=None),
                  relative_motion_evidence_saved=bool(slip),
                  maximum_relative_motion_since_first_two_pad_contact_m=maximum_slide)
    if item['physical_outcome'] == 'success':
        label = 'historical_end_success_retained'
    elif not two:
        label = 'never_two_registered_pad_contacts'
    elif lifts and any(p is False for p in pads[lifts[0]:]):
        label = 'two_pad_lift_then_contact_lost'
    elif not lifts and maximum_slide is not None and maximum_slide > .01:
        label = 'two_pad_contact_slips_before_3cm_lift'
    elif not lifts and any(p is False for p in pads[two[0]:]):
        label = 'two_pad_contact_lost_before_3cm_lift; sliding_evidence_missing'
    elif not lifts:
        label = 'two_pad_contact_without_3cm_lift; depth_or_support_unresolved'
    else:
        measured_failures = [name for name in (
            'whole_object_not_clear_of_original_support', 'dual_finger_contact_missing',
            'object_moves_relative_to_gripper', 'supported_by_non_gripper_geometry')
            if final_failures[name]]
        label = ('lift_then_final_window_failed:' + '+'.join(measured_failures)
                 if measured_failures else 'lift_observed_but_end_failure_reason_unresolved')
    output['contact_failure_class'] = label
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('attempts', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records, inputs = [], []
    for line in args.attempts.open():
        item = json.loads(line)
        path = Path(item['output_dir']) / 'private_skill_diagnostic.json'
        if not path.exists():
            records.append({**item, 'contact_failure_class': 'original_private_diagnostic_not_saved'})
            continue
        inputs.append(pin(path))
        raw = json.loads(path.read_text())
        if raw['case']['name'] != item['case']:
            raise ValueError('case identity mismatch')
        records.append(diagnose(raw, item))
    groups = defaultdict(list)
    for row in records:
        groups[row['category'] + '/' + row['method']].append(row)
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / 'records.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in records))
    report = {'attempts': pin(args.attempts), 'records': pin(path), 'inputs': inputs,
              'producer': pin(Path(__file__)), 'registered_attempts': len(records),
              'groups': {g: {'n': len(rows), 'contact_failure_classes': dict(Counter(
                  r['contact_failure_class'] for r in rows)), 'failed_only': dict(Counter(
                  r['contact_failure_class'] for r in rows if
                  r.get('historical_physical_outcome', r.get('physical_outcome')) != 'success'))}
                  for g, rows in groups.items()},
              'adjustment_directions': {
                  'never_two_registered_pad_contacts': 'Recenter and deepen the measured opposing pad patch; verify closure reaches both flanks.',
                  'two_pad_contact_slips_before_3cm_lift': 'Use a deeper opposing patch; inspect measured aperture and pinned actuator force before changing force.',
                  'two_pad_lift_then_contact_lost': 'Hold closure and compare a slower lift on the same selection states.'},
              'limitations': ['No force change is inferred from contact loss alone.',
                             'Initial lower-extent displacement is not a registered v3 support-plane label.',
                             'Missing control-phase samples remain unresolved.'],
              'training_allowed': False, 'qualification_allowed': False}
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'inputs'}, indent=2))


if __name__ == '__main__':
    main()
