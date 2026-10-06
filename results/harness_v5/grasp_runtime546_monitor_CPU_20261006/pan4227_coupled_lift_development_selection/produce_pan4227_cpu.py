"""Pin completed development rows and summarize saved public/truth evidence only."""

import hashlib
import importlib.util
import json
import math
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5/grasp_runtime546_monitor_CPU_20261006'
OUT = Path(__file__).resolve().parent / 'final_completed_20261006'
job = json.loads((BASE / 'monitor_jobs_index.json').read_text())['jobs']['4227']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def norm(v):
    return math.sqrt(sum(x * x for x in v))


manifest_file = Path(job['manifest']['path'])
assert digest(manifest_file) == job['manifest']['sha256']
source_file = Path(job['source']['path']) / 'robots/libero/v5_grasp_truth.py'
assert digest(source_file) == '5dc88383bcd5bc2bbab47256f1b0722e42cd54636dabd2ac27306b1af90cd541'
spec = importlib.util.spec_from_file_location('pinned_truth', source_file)
truth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(truth)
subprocess.run(job['summarizer_command'], check=True, cwd=ROOT)
rows, inputs = [], []
for shard in job['ledgers']:
    for key in ('episodes', 'infrastructure_attempts', 'case_infrastructure_events', 'preflight'):
        path = Path(shard[key])
        inputs.append({'kind': key, 'shard': shard['shard'], 'path': str(path),
                       'sha256': digest(path), 'bytes': path.stat().st_size})
    rows.extend(json.loads(line) for line in Path(shard['episodes']).read_text().splitlines() if line.strip())
assert len(rows) == len({r['case']['name'] for r in rows}) == 10
(OUT / 'original10_rows.json').write_text(json.dumps(rows, indent=2) + '\n')

cases, counts, per_view, frame_patterns = [], Counter(), {}, Counter()
for row in rows:
    hold = row['sustained_hold']
    recomputed = truth.sustained_grasp(hold['samples'], row['support_reference'], .5)
    assert recomputed == hold['truth']
    assert row['true_sustained_grasp'] is recomputed['success']
    stable = row['stable_visual_grasp']
    paired = stable['paired_verdict']
    frames = paired['frames']
    robot_delta = [b-a for a,b in zip(frames[0]['eef_xyz'], frames[1]['eef_xyz'])]
    views = {}
    evidence = paired['coupled_lift_evidence']
    for view in sorted(set(frames[0]['per_view']) | set(frames[1]['per_view']) | {'agentview', 'wrist'}):
        counter = per_view.setdefault(view, Counter())
        item = {'saved_coupling': evidence['per_view'].get(view), 'robot_translation_vector_m': robot_delta,
                'robot_translation_m': norm(robot_delta), 'frame_evidence': []}
        measurements = []
        for frame in frames:
            v = frame['per_view'].get(view)
            measurements.append(v.get('measurement') if v else None)
            item['frame_evidence'].append(None if v is None else {
                'measurement': v.get('measurement'), 'current_measurement': v.get('current_measurement'),
                'conditions': v.get('conditions'), 'verified': v.get('verified'), 'reason': v.get('reason'),
                'lower_lift_m': v.get('lower_lift_m'),
                'original_support_clearance_m': v.get('original_support_clearance_m')})
        if all(measurements):
            object_delta = [b-a for a,b in zip(measurements[0]['xyz'], measurements[1]['xyz'])]
            residual = norm([a-b for a,b in zip(object_delta, robot_delta)])
            item.update(object_translation_vector_m=object_delta, object_translation_m=norm(object_delta),
                        recomputed_object_robot_translation_residual_m=residual)
            saved = item['saved_coupling']
            if saved and saved['object_robot_translation_residual_m'] is not None:
                assert math.isclose(residual, saved['object_robot_translation_residual_m'], abs_tol=1e-12)
            counter['paired_body_measurements'] += 1
        else:
            item.update(object_translation_vector_m=None, object_translation_m=None,
                        recomputed_object_robot_translation_residual_m=None)
            counter['ordinary_paired_body_measurement_missing'] += 1
        counter['coupling_true' if item['saved_coupling'] and item['saved_coupling']['coupling_measured'] else 'coupling_not_true'] += 1
        views[view] = item
    for frame in stable['frames']:
        pattern = {}
        for view, acquisition in frame['handle_acquisition'].items():
            n = acquisition['accepted_instances']
            kind = 'unique' if n == 1 else 'missing' if n == 0 else 'ambiguous'
            pattern[view] = kind
            per_view.setdefault(view, Counter())['handle_' + kind + '_frames'] += 1
        frame_patterns[json.dumps(pattern, sort_keys=True)] += 1
    public = row['first_receipt'].get('grasp_verified')
    handle_only = stable['handle_only_paired_verdict'].get('verified')
    counts['truth_' + str(recomputed['success'])] += 1
    counts['public_' + str(public)] += 1
    counts['handle_only_' + str(handle_only)] += 1
    cases.append({'case': row['case']['name'], 'registered_case': row['case'],
                  'saved_hold_truth': recomputed, 'public': public,
                  'handle_only_public': handle_only, 'coupled_public': paired['verified'],
                  'coupled_lift_thresholds': {k:v for k,v in evidence.items() if k != 'per_view'},
                  'per_view': views, 'hold_interval_s': paired['interval_s'],
                  'runtime_inputs': stable['runtime_inputs'],
                  'coupled_motion': {k:stable['coupled_lift_motion'].get(k) for k in
                      ('target_xyz', 'final_eef_pos', 'final_dist_m', 'steps_used', 'actions_used', 'waypoint_reached')}})
report = {'scope': 'Completed4227 original pan same10 development replay; no confirmation claim',
          'manifest': job['manifest'], 'source': job['source'],
          'producer_sha256': digest(__file__), 'truth_source_sha256': digest(source_file),
          'original_rows_sha256': digest(OUT / 'original10_rows.json'), 'inputs': inputs,
          'saved_sample_recomputations_equal_original_truth': 10, 'counts': dict(counts),
          'per_view_counts': {k:dict(v) for k,v in per_view.items()},
          'frame_handle_patterns': dict(frame_patterns), 'cases': cases,
          'same_registered_states_as_4200': True, 'legacy_4148_4200_preserved': True,
          'ordinary_missing_is_not_infrastructure': True, 'qualification_authorized': False,
          'new_model_calls_by_producer': 0, 'new_physical_trials_by_producer': 0}
(OUT / 'coupled_lift_evidence_report.json').write_text(json.dumps(report, indent=2) + '\n')
(OUT / 'input_index.json').write_text(json.dumps({'manifest': job['manifest'], 'source': job['source'], 'inputs': inputs}, indent=2) + '\n')
print(json.dumps({'counts': report['counts'], 'per_view_counts': report['per_view_counts'],
                  'formal_report_sha256': digest(OUT / 'report.json'),
                  'coupled_evidence_sha256': digest(OUT / 'coupled_lift_evidence_report.json')}))
