"""Selection-only endpoint distance calibration; original200 labels remain frozen."""

from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

import numpy as np


OUT = Path(__file__).resolve().parent / 'final_20261006T164608.567363Z'
FORMAL = OUT / 'statistic/report.json'
formal = json.loads(FORMAL.read_text())
items, source_ledgers = [], []


@lru_cache(maxsize=None)
def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def distribution(values):
    if not values:
        return {'n': 0}
    values = np.asarray(values, dtype=float)
    return {'n': len(values), **dict(zip(('min', 'q05', 'median', 'q95', 'max'),
                                        np.quantile(values, [0, .05, .5, .95, 1]).tolist()))}


def metrics(rows, feature, cutoff, mode):
    matched = [row for row in rows if row['original_public_verdict'] is not None and row.get(feature) is not None]
    counts = Counter()
    for row in matched:
        positive = row[feature] >= cutoff if mode == 'open' else row[feature] <= cutoff
        counts['tp' if positive and row['private_after_satisfied'] else
               'fp' if positive else 'fn' if row['private_after_satisfied'] else 'tn'] += 1
    tp, tn, fp, fn = [counts[key] for key in ('tp', 'tn', 'fp', 'fn')]
    null = [row for row in rows if row not in matched]
    return {'feature': feature, 'cutoff_m': cutoff, 'comparison': '>=' if mode == 'open' else '<=',
            'planned': len(rows), 'original_public_measured_pairs_used': len(matched),
            'unmeasured_not_relabelled': len(null),
            'truth_positive_left_unmeasured': sum(row['private_after_satisfied'] is True for row in null),
            'truth_negative_left_unmeasured': sum(row['private_after_satisfied'] is False for row in null),
            'confusion_on_measured': {'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn},
            'precision_on_measured': tp / (tp + fp) if tp + fp else None,
            'recall_on_measured_truth_positives': tp / (tp + fn) if tp + fn else None,
            'agreement_on_measured': (tp + tn) / len(matched) if matched else None,
            'coverage_over_registered': len(matched) / len(rows),
            'agreement_count_bounds_over_registered': [(tp + tn) / len(rows), (tp + tn + len(null)) / len(rows)],
            'public_prediction_scope': 'Hypothetical selection calibration only; original public nulls and verdicts untouched'}


for ledger in formal['original_explicit_inputs']:
    if ledger['role'] != 'ledger' or not ledger.get('exists'):
        continue
    snapshot = Path(ledger['snapshot'])
    source_ledgers.append(ref(snapshot))
    for line_number, line in enumerate(snapshot.read_text().splitlines(), 1):
        row = json.loads(line)
        case, first = row['case'], row['first_attempt']
        metrology = (first.get('verification_measurements') or {}).get('articulation') or {}
        public = first['receipt'].get('articulate_verified')
        item = {'case': case['name'], 'episode': case['episode'], 'type': case['type'], 'mode': case['mode'],
                'original_public_verdict': public,
                'private_before_satisfied': (first.get('private_before') or {}).get('satisfied'),
                'private_after_satisfied': (first.get('private_after') or {}).get('satisfied'),
                'private_before_scoring_qpos': (first.get('private_before') or {}).get('joint_qpos'),
                'private_after_scoring_qpos': (first.get('private_after') or {}).get('joint_qpos'),
                'original_rounded_extension_cm': metrology.get('measured_extension_cm'),
                'original_metrology_reason': metrology.get('reason'),
                'front_axis_was_serialized': any('front_axis' in (metrology.get(phase) or {}) for phase in ('before', 'after')),
                'geometry': {}, 'original_ledger': ledger['path'], 'captured_ledger': {**ref(snapshot), 'line': line_number},
                'choices': {'path': str(Path(row['output_dir']) / 'choices.jsonl'), 'sha256': row['choices_sha256']},
                'original_verdict_changed': False}
        outward = None
        for phase in ('before', 'after'):
            sample = metrology.get(phase) or {}
            frame, face = sample.get('frame'), sample.get('moving')
            item['geometry'][phase] = {'frame': frame, 'moving': face, 'source_step': sample.get('source_step'),
                                       'point_counts': sample.get('point_counts')}
            if frame is None or face is None:
                continue
            normal = np.asarray(frame['normal_xy'], dtype=float)
            delta = np.asarray(face['centre'][:2]) - frame['centre'][:2]
            raw = float(delta @ normal)
            item[phase + '_raw_signed_normal_m'] = raw
            item[phase + '_exact_abs_m'] = abs(raw)
            if phase == 'before':
                eef = (first.get('public_before') or {}).get('robot', {}).get('eef_xyz')
                if eef is not None:
                    side = float((np.asarray(eef[:2]) - frame['centre'][:2]) @ normal)
                    item['orientation_public_eef_side_distance_m'] = side
                    item['orientation_initial_public_eef_xyz'] = eef
                    if abs(side) > .01:
                        outward = normal if side > 0 else -normal
                        item['inferred_outward_axis_before_xy'] = outward.tolist()
            if outward is not None:
                aligned = normal if float(normal @ outward) > 0 else -normal
                item[phase + '_inferred_outward_signed_m'] = float(delta @ aligned)
                item['geometry'][phase]['inferred_outward_normal_xy'] = aligned.tolist()
            if phase == 'after' and public is not None:
                expected = abs(raw) >= .025 if case['mode'] == 'open' else abs(raw) <= .015
                if expected is not public:
                    raise ValueError('Saved original verdict differs from SOURCE558 distance rule: ' + case['name'])
        if item.get('after_inferred_outward_signed_m') is not None:
            qpos = item['private_after_scoring_qpos'][0][0]
            item['signed_public_minus_scoring_neg_qpos_mm'] = (item['after_inferred_outward_signed_m'] + qpos) * 1000
        items.append(item)

assert len(items) == 200
groups = {}
for typ, mode in [('drawer_open', 'open'), ('drawer_close', 'close')]:
    rows = [row for row in items if row['type'] == typ]
    assert len(rows) == 100
    eligible = [row for row in rows if row['original_public_verdict'] is not None]
    analyses = {}
    for feature in ('after_exact_abs_m', 'after_inferred_outward_signed_m'):
        values = sorted({row[feature] for row in eligible if row.get(feature) is not None})
        candidates = sorted(set([values[0] - 1e-9, values[-1] + 1e-9, *values,
                                  *[(a + b) / 2 for a, b in zip(values, values[1:])]]))
        scores = [metrics(rows, feature, cutoff, mode) for cutoff in candidates]
        guideline = .14 if mode == 'open' else 0.
        best = max(scores, key=lambda value: (value['agreement_on_measured'],
            -value['confusion_on_measured']['fp'], value['confusion_on_measured']['tp'],
            -abs(value['cutoff_m'] - guideline)))
        best_agreement = max(value['agreement_on_measured'] for value in scores)
        optima = [value['cutoff_m'] for value in scores if value['agreement_on_measured'] == best_agreement]
        analyses[feature] = {'current_cutoff_hypothetical': metrics(rows, feature, .025 if mode == 'open' else .015, mode),
            'original_joint_endpoint_numeric_cutoff_hypothetical': metrics(rows, feature, guideline, mode),
            'best_on_same_selection_data': best,
            'best_agreement_candidate_threshold_span_m': [min(optima), max(optima)],
            'threshold_candidates': len(candidates),
            'positive_truth_value_distribution_m': distribution([row[feature] for row in eligible
                if row.get(feature) is not None and row['private_after_satisfied'] is True]),
            'negative_truth_value_distribution_m': distribution([row[feature] for row in eligible
                if row.get(feature) is not None and row['private_after_satisfied'] is False])}
    groups[typ] = {'registered': 100, 'measured': len(eligible), 'null_preserved': 100 - len(eligible),
                  'private_truth_successes': sum(row['private_after_satisfied'] is True for row in rows),
                  'threshold_analysis': analyses,
                  'signed_distance_by_truth_and_side': dict(Counter(
                      str(row['private_after_satisfied']) + '/' + ('negative' if row.get('after_inferred_outward_signed_m', 0) < 0 else 'zero_or_positive')
                      for row in eligible if row.get('after_inferred_outward_signed_m') is not None)),
                  'signed_public_minus_scoring_neg_qpos_distribution_mm': distribution([
                      row['signed_public_minus_scoring_neg_qpos_mm'] for row in eligible
                      if row.get('signed_public_minus_scoring_neg_qpos_mm') is not None])}

data_path = OUT / 'endpoint_selection200_geometry.jsonl'
data_path.write_text(''.join(json.dumps(row) + '\n' for row in items))
output = {'scope': 'Original200 reused selection states only; saved public geometry plus scoring truth, no qualification or independent calibration',
    'formal_report': ref(FORMAL), 'captured_ledger_refs': source_ledgers, 'geometry_records': ref(data_path),
    'source_original_rule': {'after_distance': 'abs((moving.centre_xy-frame.centre_xy) dot frame.normal_xy)',
        'open_cutoff_m': .025, 'close_cutoff_m': .015,
        'source': ref(Path(formal['source']['snapshot']) / 'robots/libero/v5_verification.py')},
    'signed_direction_method': 'Orient before frame normal toward initial public-before EEF side; align after normal to this public direction. No private qpos, symbol or truth enters orientation',
    'direction_limit': 'The original front_axis was not serialized. This inferred public outward normal is an explicit calibration feature, not a recovered original runtime axis',
    'close_abs_information_loss': 'Absolute value discards which side of the fixed face plane the selected moving face lies on; exact signed geometry is preserved separately',
    'by_type': groups,
    'threshold_scope': 'Optima fit the same selected200 data and report conditional measured-pair performance. Original nulls remain null; 31percent close coverage cannot establish95percent full-cohort agreement',
    'official_qpos_scope': 'Private qpos is only a scoring comparison.14cm/zero numeric cutoffs are diagnostics, not runtime calibration or newly accepted endpoint criteria',
    'labels_thresholds_runtime_or_physics_changed': False, 'new_model_calls': 0, 'new_physics': 0,
    'new_training_rows': 0, 'producer': ref(Path(__file__).resolve())}
path = OUT / 'endpoint_threshold_selection_report.json'
path.write_text(json.dumps(output, indent=2) + '\n')
compact = {typ: {'measured': group['measured'], 'null': group['null_preserved'],
    'signed_sides': group['signed_distance_by_truth_and_side'],
    'thresholds': {feature: {key: analysis[key] for key in
        ('current_cutoff_hypothetical', 'original_joint_endpoint_numeric_cutoff_hypothetical', 'best_on_same_selection_data',
         'positive_truth_value_distribution_m', 'negative_truth_value_distribution_m')}
        for feature, analysis in group['threshold_analysis'].items()}} for typ, group in groups.items()}
print(json.dumps({'report': ref(path), 'geometry': ref(data_path), 'groups': compact}))
