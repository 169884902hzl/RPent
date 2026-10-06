"""Saved-only close endpoint observability and release-phase diagnostics."""

from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = Path(__file__).resolve().parent
OLD = ROOT / 'results/harness_v5/drawer559_monitor_CPU_20261006/final_20261006T164608.567363Z'
RUNS = [(569, 4319, '180710.101434'), (571, 4327, '181240.205782')]
CURRENT_CUTOFF = .0005


def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def load_rows(formal):
    rows = []
    for loc in formal['original_explicit_inputs']:
        if loc['role'] == 'ledger' and loc.get('exists'):
            captured = ref(loc['snapshot'])
            rows.extend((json.loads(line), {'ledger': loc['path'], 'captured': captured, 'line': i})
                        for i, line in enumerate(Path(loc['snapshot']).read_text().splitlines(), 1))
    return rows


def label_value(label):
    joints = (label or {}).get('joint_qpos')
    return float(joints[0][0]) if joints and joints[0] else None


def distribution(values):
    values = [x for x in values if x is not None]
    if not values:
        return {'n': 0}
    return {'n': len(values), 'min': min(values), 'q05': float(np.quantile(values, .05)),
            'median': float(np.median(values)), 'q95': float(np.quantile(values, .95)), 'max': max(values)}


def metrics(rows, cutoff):
    measured = [row for row in rows if row['eligible_original_metrology'] and row['private_truth'] is not None]
    unknown = [row for row in rows if not row['eligible_original_metrology']]
    counts = Counter()
    fp_cases, fn_cases = set(), set()
    for row in measured:
        predicted = row['signed_extension_m'] <= cutoff
        key = ('tp' if row['private_truth'] else 'fp') if predicted else ('fn' if row['private_truth'] else 'tn')
        counts[key] += 1
        if key == 'fp': fp_cases.add(row['case'])
        if key == 'fn': fn_cases.add(row['case'])
    return {'cutoff_m': cutoff, 'sample_denominator': len(rows), 'eligible_original_samples': len(measured),
            'preserved_null_samples': len(unknown), 'null_truth_true': sum(row['private_truth'] is True for row in unknown),
            'null_truth_false': sum(row['private_truth'] is False for row in unknown),
            'unique_case_denominator': len({row['case'] for row in rows}),
            'confusion': {key: counts[key] for key in ('tp', 'tn', 'fp', 'fn')},
            'fp_unique_cases': sorted(fp_cases), 'fn_unique_cases': sorted(fn_cases),
            'scope': 'Diagnostic saved-sample scan only; nulls are not relabelled and correlated frames are not independent trials'}


def scan(rows):
    values = sorted({row['signed_extension_m'] for row in rows if row['eligible_original_metrology']})
    cuts = sorted({-.015, -.01, -.005, -.002, -.001, -.0005, 0., .00024017693624991032, CURRENT_CUTOFF, .001,
                   .0015, .002, .005, .015, *values,
                   *((a+b)/2 for a, b in zip(values, values[1:])),
                   *( [values[0]-1e-9, values[-1]+1e-9] if values else [])})
    results = [metrics(rows, cutoff) for cutoff in cuts]
    best_error = min(result['confusion']['fp'] + result['confusion']['fn'] for result in results)
    best = [result for result in results if result['confusion']['fp'] + result['confusion']['fn'] == best_error]
    zero_fp = [result for result in results if result['confusion']['fp'] == 0]
    true_values = [row['signed_extension_m'] for row in rows if row['eligible_original_metrology'] and row['private_truth'] is True]
    false_values = [row['signed_extension_m'] for row in rows if row['eligible_original_metrology'] and row['private_truth'] is False]
    return results, {'current_unchanged_0p5mm': metrics(rows, CURRENT_CUTOFF), 'zero_numeric_cutoff': metrics(rows, 0.),
                     'historical_best_cutoff_0p2401769mm': metrics(rows, .00024017693624991032),
                     'signed_positive_truth_distribution_mm': distribution([x*1000 for x in true_values]),
                     'signed_negative_truth_distribution_mm': distribution([x*1000 for x in false_values]),
                     'public_minus_private_neg_qpos_bias_mm': distribution([row['bias_mm'] for row in rows if row['eligible_original_metrology']]),
                     'perfect_single_signed_threshold_on_measured_exists': best_error == 0,
                     'minimum_fp_plus_fn_on_same_samples': best_error,
                     'best_same_sample_scan_candidate_span_m': [best[0]['cutoff_m'], best[-1]['cutoff_m']],
                     'best_same_sample_scan_confusion': best[0]['confusion'],
                     'zero_fp_maximum_tp': max(result['confusion']['tp'] for result in zero_fp),
                     'null_denominator_unchanged_across_all_cutoffs': True,
                     'threshold_candidates': len(results), 'threshold_change_authorized': False}


def measurement_row(case, label, verdict, signed, phase, dataset, locator, sample=None):
    qpos = label_value(label)
    eligible = verdict is not None and signed is not None
    return {'dataset': dataset, 'case': case['name'], 'episode': case['episode'], 'state_sha256': case['state_sha256'],
            'phase': phase, 'chunk': sample.get('chunk') if sample else None,
            'source_step': (sample.get('measurement') or {}).get('source_step') if sample else None,
            'signed_extension_m': signed, 'eligible_original_metrology': eligible, 'original_public_verdict': verdict,
            'original_null_reason': ((sample.get('evidence') or {}).get('reason') if sample else None),
            'private_truth': (label or {}).get('satisfied'), 'private_qpos_m': qpos,
            'private_sim_time': (label or {}).get('sim_time'), 'private_used_for_control': False,
            'bias_mm': (signed + qpos)*1000 if signed is not None and qpos is not None else None,
            'locator': locator, 'original_label_changed': False}


def contacts(sample, fixture):
    diagnostic = (sample or {}).get('contact_and_joints') or {}
    return [contact for contact in diagnostic.get('contacts', [])
            if any(fixture in str(contact.get(key, '')) for key in ('geom1', 'geom2'))
            and any(any(token in str(contact.get(key, '')) for token in ('gripper', 'robot', 'panda'))
                    for key in ('geom1', 'geom2'))]


def main():
    BASE.mkdir(exist_ok=True)
    datasets, release_records, anomalies = {}, [], []
    old_geometry_path = OLD / 'endpoint_selection200_geometry.jsonl'
    old_geometry = {row['case']: row for row in map(json.loads, old_geometry_path.read_text().splitlines())}
    old_formal_path = OLD / 'statistic/report.json'
    old_formal = json.loads(old_formal_path.read_text())
    historical = []
    for row, locator in load_rows(old_formal):
        case, first = row['case'], row['first_attempt']
        if case['type'] != 'drawer_close': continue
        geometry = old_geometry[case['name']]
        item = measurement_row(case, first.get('private_after'), geometry['original_public_verdict'],
            geometry.get('after_inferred_outward_signed_m'), 'final', 'original559_final100_close', locator)
        item.update(original_null_reason=geometry['original_metrology_reason'],
                    signed_method='Before normal oriented using initial public EEF side, after normal aligned; original runtime axis not serialized')
        historical.append(item)
    assert len(historical) == 100
    datasets['original559_final100_close'] = historical
    input_refs = {'original_geometry': ref(old_geometry_path), 'original_formal': ref(old_formal_path)}
    same_keys = None
    for version, job, stamp in RUNS:
        final = ROOT / f'results/harness_v5/drawer{version}_monitor_CPU_20261006/final_20261006T{stamp}Z'
        formal_path = final / 'statistic/report.json'
        formal = json.loads(formal_path.read_text())
        input_refs[str(job)] = {'formal': ref(formal_path), 'stage_report': ref(final/'fixture_stage_scoring_report.json')}
        finals, callbacks, stop_pairs, case_keys = [], [], [], set()
        for row, locator in load_rows(formal):
            case, first = row['case'], row['first_attempt']
            if case['type'] != 'drawer_close': continue
            case_keys.add((case['type'], case['state_sha256']))
            evidence = first['verification_measurements']
            scores = first['contact_evidence']['private_fixture_scores']
            chunks = {s['chunk']: s['label'] for s in scores if s['phase'] == 'after_actual_chunk'}
            stop = [s for s in scores if s['phase'] == 'after_public_stop_before_recovery']
            for s in stop:
                if chunks[s['chunk']-1] != s['label']: anomalies.append({'case': case['name'], 'error': 'stop_label_changed_since_actual_chunk'})
            sample_rows = []
            for sample in evidence.get('drawer_public_stop', []):
                private = chunks[sample['chunk']-1]
                item = measurement_row(case, private, sample['verified'], sample['evidence'].get('measured_signed_extension_m'),
                    'after_complete_contact_chunk_public_callback', f'{job}_callback_close', locator, sample)
                item['pairing_scope'] = 'Private read after actual chunk, then read-only capture; stop-time duplicate labels match exactly. No per-control private signal enters measurement'
                item['signed_method'] = 'Serialized runtime public measured outward axis'
                sample_rows.append(item); callbacks.append(item)
            if stop: stop_pairs.extend(sample_rows[-2:])
            articulation = evidence.get('articulation') or {}
            final_sample = {'measurement': articulation.get('after') or {}, 'evidence': articulation}
            item = measurement_row(case, first.get('private_after'), first['receipt'].get('articulate_verified'),
                articulation.get('measured_signed_extension_m'), 'final', f'{job}_final10_close', locator, final_sample)
            item['signed_method'] = 'Serialized runtime public measured outward axis'; finals.append(item)
            last = chunks[max(chunks)]
            released = [s['label'] for s in scores if s['phase'] == 'after_fixture_release']
            clearance = first['receipt'].get('fixture_contact_clearance') or {}
            move = clearance.get('clearance_move') or {}
            motions = first['motion_evidence']
            actual_locations = [i for i,m in enumerate(motions) if m['name'] == 'vla_act_chunk']
            actual = [motions[i] for i in actual_locations]
            post_moves = [m for m in motions[actual_locations[-1]+1:] if m['name'] == 'move_to']
            eef_before = actual[-1].get('final_eef_pos')
            eef_after = post_moves[0].get('start_eef_pos') if post_moves else None
            delta = (np.asarray(eef_after)-eef_before).tolist() if eef_before and eef_after else None
            fixture = case['object_symbol'].split('_bottom')[0].split('_middle')[0].split('_top')[0]
            release = clearance.get('release') or {}
            label_after = released[-1] if released else None
            label_before = stop[-1]['label'] if stop else last
            release_records.append({'job': job, 'case': case['name'], 'episode': case['episode'], 'state_sha256': case['state_sha256'],
                'private_before_release': label_before, 'private_after_release': label_after,
                'strict_endpoint_true_to_false_during_release': bool(label_before and label_after and label_before['satisfied'] is True and label_after['satisfied'] is False),
                'qpos_delta_m': label_value(label_after)-label_value(label_before) if label_after and label_before else None,
                'sim_duration_s': label_after['sim_time']-label_before['sim_time'] if label_after and label_before else None,
                'release_steps': release.get('steps_used'), 'jaw_before_m': clearance.get('opening_before_m'),
                'jaw_after_m': clearance.get('opening_after_m'),
                'jaw_was_already_open_75mm_before_release': clearance.get('opening_before_m', 0) >= .075,
                'jaw_delta_m': clearance['opening_after_m']-clearance['opening_before_m'] if 'opening_after_m' in clearance else None,
                'public_eef_before_release': eef_before, 'public_eef_after_release_before_clearance': eef_after,
                'release_endpoint_eef_delta_m': delta, 'release_endpoint_eef_displacement_m': float(np.linalg.norm(delta)) if delta else None,
                'saved_requested_fixture_robot_contacts_after_release': contacts((move.get('trajectory') or [None])[0], fixture),
                'contact_points_or_forces_during_release_saved': False, 'release_EEF_trajectory_saved': False,
                'command_from_frozen_source': '40 controls: six EEF command dimensions zero, gripper command -1 (open)',
                'interpretation': 'Already open jaw and a fixed-pose 2s command support continued contact dynamics or relaxation as possibilities. They do not establish a closed-to-open grasp release or isolate the mechanical cause',
                'locator': locator, 'private_used_for_control': False})
        assert len(finals) == 10
        if same_keys is None: same_keys = case_keys
        else: assert same_keys == case_keys
        datasets[f'{job}_final10_close'] = finals
        datasets[f'{job}_callback_close'] = callbacks
        datasets[f'{job}_stop_last_two_close'] = stop_pairs
        # This stratum diagnoses observation overlap; it never changes full-run scoring or selects a runtime rule.
        datasets[f'{job}_private_boundary_absq_le3mm_callback'] = [row for row in callbacks
            if row['private_qpos_m'] is not None and abs(row['private_qpos_m']) <= .003]
    historical_same = [row for row in historical if ('drawer_close', row['state_sha256']) in same_keys]
    assert len(historical_same) == 10
    datasets['original559_same10_close'] = historical_same
    all_scans, summaries = [], {}
    for name, rows in datasets.items():
        thresholds, summary = scan(rows)
        summaries[name] = summary
        all_scans.extend({'dataset': name, **row} for row in thresholds)
    near = [row for key, rows in datasets.items() if key.endswith('private_boundary_absq_le3mm_callback') for row in rows
            if row['eligible_original_metrology']]
    mixed = defaultdict(lambda: defaultdict(list))
    for row in near: mixed[row['signed_extension_m']][row['private_truth']].append(row)
    aliases = [{'signed_extension_m': signed, 'true_examples': labels[True], 'false_examples': labels[False]}
               for signed, labels in sorted(mixed.items()) if labels[True] and labels[False]]
    nearest = sorted(({'signed_difference_m': abs(a['signed_extension_m']-b['signed_extension_m']),
                       'true': a, 'false': b} for a in near if a['private_truth'] is True
                      for b in near if b['private_truth'] is False), key=lambda row: row['signed_difference_m'])[:10]
    measurements = BASE/'saved_close_measurements.jsonl'
    measurements.write_text(''.join(json.dumps({'analysis_group': name, **row})+'\n'
        for name, rows in datasets.items() for row in rows))
    scan_path = BASE/'signed_threshold_scans.jsonl'
    scan_path.write_text(''.join(json.dumps(row)+'\n' for row in all_scans))
    scan_table = BASE/'signed_threshold_scans.tsv'
    with scan_table.open('w') as handle:
        writer = csv.DictWriter(handle, delimiter='\t', fieldnames=['dataset','cutoff_mm','samples','measured','null','tp','tn','fp','fn','fp_cases','fn_cases'])
        writer.writeheader()
        for row in all_scans:
            writer.writerow({'dataset': row['dataset'], 'cutoff_mm': row['cutoff_m']*1000, 'samples': row['sample_denominator'],
                'measured': row['eligible_original_samples'], 'null': row['preserved_null_samples'], **row['confusion'],
                'fp_cases': ','.join(row['fp_unique_cases']), 'fn_cases': ','.join(row['fn_unique_cases'])})
    release_path = BASE/'release_already_open_diagnostics.jsonl'
    release_path.write_text(''.join(json.dumps(row)+'\n' for row in release_records))
    overlap_path = BASE/'near_boundary_mixed_labels.json'
    overlap_path.write_text(json.dumps({'identical_signed_value_mixed_truth_groups': aliases,
        'nearest_true_false_public_signed_examples': nearest,
        'scope': 'Both full datasets retained. Private abs(q)<=3mm is a scoring diagnostic stratum, not a public filter or new evaluation set'}, indent=2)+'\n')
    tools = ROOT/'source_v5_drawer569_20261006/robots/libero/tools.py'
    report = {'scope': 'Original selection200 and same20 SOURCE569/571 saved close public/private evidence; no physics replay or rule change',
        'producer': ref(__file__), 'inputs': input_refs,
        'frozen_sources': {'569_release': ref(tools), '569_runtime': ref(ROOT/'source_v5_drawer569_20261006/robots/libero/v5_runtime.py'),
            '571_runtime': ref(ROOT/'source_v5_drawer571_20261006/robots/libero/v5_runtime.py')},
        'strict_original_close_truth': 'qpos > 0.0', 'unchanged_public_close_cutoff_m': CURRENT_CUTOFF,
        'dataset_summaries': summaries, 'original559_names_source_snapshot_558': True,
        'exact_mixed_truth_signed_value_groups': len(aliases), 'release_cases': len(release_records),
        'release_jaw_already_open_cases': sum(row['jaw_was_already_open_75mm_before_release'] for row in release_records),
        'release_strict_true_to_false_cases': [{key: row[key] for key in ('job','case','episode','private_before_release','private_after_release',
            'qpos_delta_m','jaw_before_m','jaw_after_m','jaw_delta_m','sim_duration_s','release_steps','release_endpoint_eef_displacement_m')}
            for row in release_records if row['strict_endpoint_true_to_false_during_release']],
        'limitations': ['Original100 close has only31 valid measured pairs;69 nulls are preserved and historical inferred axis is not the new serialized axis',
            'New75/121 contact callback samples come from10 reused states per run; they are correlated frames, not new independent episodes',
            'Private abs(q)<=3mm strata localize overlap and cannot be used as a public decision input or performance subset',
            'Same public signed values with opposite strict labels rule out perfect scalar separation on these observations; this does not prove all RGB-D information or future richer measurements cannot resolve the endpoint',
            'Threshold scans classify saved frames only. They cannot estimate changed closed-loop performance because new stopping rules alter physics and the recorded trajectories stop at the original callback horizon',
            'Release holds EEF commands zero for40 physical controls while the jaw is already open. No per-control release contact/force/velocity trace isolates relaxation, collision or grasp mechanics'],
        'measurements': ref(measurements), 'threshold_scans': ref(scan_path), 'threshold_table': ref(scan_table),
        'release_diagnostics': ref(release_path), 'overlap_evidence': ref(overlap_path), 'anomalies': anomalies,
        'original_nulls_and_failures_preserved': True, 'runtime_threshold_changed': False, 'private_used_for_control': False,
        'new_physics': 0, 'new_model_calls': 0, 'qualification_authorized': False}
    path=BASE/'close_observability_report.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'report':ref(path),'mixed_signed_truth_groups':len(aliases),
        'release_already_open':report['release_jaw_already_open_cases'], 'release_losses':report['release_strict_true_to_false_cases'],
        'at_unchanged_cutoff':{name:summary['current_unchanged_0p5mm'] for name,summary in summaries.items()},
        'anomaly_count':len(anomalies)}))


if __name__ == '__main__':
    main()
