"""Report exact4271 public runtime recipe evidence; no replay or relabeling."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
MANIFEST = ROOT / 'results/harness_v5/pan562_runtime_smoke10_CPU_20261006/preparation/pan562_runtime_direct_same10_selection.json'
MANIFEST_SHA = '6800976d91fab44c3195bed378e83370aa1ae0ffa6f27615a537e91af75b9e63'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def motion_summary(motion):
    keys = ('name', 'target_xyz', 'final_eef_pos', 'final_dist_m', 'steps_used', 'actions_used',
            'max_steps', 'terminated', 'truncated', 'waypoint_reached', 'acceptance_distance_m')
    value = {key: motion.get(key) for key in keys}
    trace = motion.get('trajectory') or []
    if trace and motion.get('target_xyz') and trace[0].get('eef_pos'):
        value['initial_public_eef_xyz'] = trace[0]['eef_pos']
        value['requested_translation_m'] = [t - s for t, s in zip(motion['target_xyz'], trace[0]['eef_pos'])]
    return value


def frame_summary(frame):
    keys = ('version', 'verified', 'reason', 'selected_view', 'eef_xyz', 'opening_m',
            'captured_step', 'body_quat_xyzw', 'handle_acquisition')
    value = {key: frame.get(key) for key in keys}
    value['per_view'] = {view: {key: record.get(key) for key in
                              ('current_measurement', 'verified', 'reason', 'conditions', 'measurement',
                               'lower_lift_m', 'original_support_clearance_m')}
                         for view, record in frame.get('per_view', {}).items()}
    return value


parser = argparse.ArgumentParser()
parser.add_argument('--report-dir', required=True, type=Path)
args = parser.parse_args()
out = args.report_dir.resolve(strict=True)
if not out.is_relative_to(Path(__file__).resolve().parent):
    raise ValueError('Owned report directory required')
monitor = json.loads((out / 'monitor_report.json').read_text())
formal = json.loads((out / 'statistic/report.json').read_text())
plan = json.loads(MANIFEST.read_text())
assert ref(MANIFEST)['sha256'] == MANIFEST_SHA
assert monitor['final'] and monitor['complete_first_physical'] and formal['first_physical_attempts'] == 10
condition = next(iter(plan['conditions'].values()))
records, anomalies, fusion_cameras = [], [], Counter()
totals = Counter()
for part in range(8):
    captured = out / f'input_snapshot/part{part}/episodes/episodes.jsonl'
    for line_number, line in enumerate(captured.read_text().splitlines(), 1):
        row = json.loads(line)
        choice_path = Path(row['output_dir']) / 'choices.jsonl'
        choice_ref = ref(choice_path)
        if choice_ref['sha256'] != row['choices_sha256']:
            raise ValueError('Original choices changed: ' + row['case']['name'])
        choices = [json.loads(item) for item in choice_path.read_text().splitlines()]
        candidate = next((item for item in choices
                          if 'pan_coupled_lift' in (item.get('verification_measurements') or {})), None)
        evidence = ((candidate or {}).get('verification_measurements') or {}).get('pan_coupled_lift') or {}
        stable = evidence.get('stable_visual_grasp') or {}
        receipt = row.get('first_receipt') or {}
        frames = stable.get('frames') or []
        pair = stable.get('paired_verdict') or {}
        trial = motion_summary(stable.get('trial_lift_motion') or {})
        coupled = motion_summary(stable.get('coupled_lift_motion') or {})
        motions = (candidate or {}).get('motion_evidence') or []
        vla = [motion for motion in motions if motion.get('name') == 'vla_act_chunk']
        fusion = (row.get('result') or {}).get('fusion_measurements') or {}
        actual = {'PAN_receipt': receipt.get('grasp_profile') == 'PAN',
                  'original_prompt': receipt.get('contact_prompt') == 'pick up the frying pan',
                  'contact_max320': receipt.get('contact_max_chunks') == 320,
                  'reset_pose_proprioception': receipt.get('approach') == 'reset_pose_proprioception',
                  'trial_lift_point10': stable.get('trial_lift_m') == .10,
                  'trial_waypoint_reached': trial.get('waypoint_reached') is True,
                  'extra_lift_point05_requested': abs((coupled.get('requested_translation_m') or [0, 0, -1])[2] - .05) <= .0001,
                  'extra_lift_waypoint_reached': coupled.get('waypoint_reached') is True,
                  'two_current_frames': len(frames) == 2,
                  'cross_view_queries_both_frames': len(frames) == 2 and all(
                      {'agentview', 'wrist'} <= set(frame.get('handle_acquisition', {})) for frame in frames),
                  'coupled_verifier': pair.get('version') == 'measured-grasp-independent-views/4-coupled-lift-dev',
                  'fusion_enabled': fusion.get('enabled') is True,
                  'all_vla_chunks_five_controls': bool(vla) and all(
                      motion.get('requested_action_count') == motion.get('executed_action_count') == 5 for motion in vla)}
        totals.update({key: int(value) for key, value in actual.items()})
        totals['vla_chunks'] += len(vla)
        totals['vla_controls'] += sum(motion.get('executed_action_count', 0) for motion in vla)
        totals['fusion_refreshes'] += fusion.get('refreshes', 0)
        fusion_cameras.update(fusion.get('source_camera_distribution', {}))
        item = {'case': row['case']['name'], 'episode': row['case']['episode'], 'part': part,
                'state_sha256': row['case']['state_sha256'], 'attempt_index': row.get('attempt_index'),
                'captured_ledger': {**ref(captured), 'line': line_number}, 'choices': choice_ref,
                'saved_private_sustained_truth': row.get('true_sustained_grasp'),
                'saved_public_verdict': receipt.get('grasp_verified'), 'actual_recipe_checks': actual,
                'first_receipt': receipt, 'runtime_shared_measurement_version': stable.get('version'),
                'trial_lift_motion_public_summary': trial, 'extra_lift_motion_public_summary': coupled,
                'current_frames': [frame_summary(frame) for frame in frames],
                'paired_verdict_public_summary': {key: pair.get(key) for key in
                    ('version', 'verified', 'verification', 'conditions', 'interval_s', 'coupled_lift_evidence')},
                'fusion_measurements': fusion, 'actual_vla_chunks': len(vla),
                'actual_vla_controls': sum(motion.get('executed_action_count', 0) for motion in vla),
                'model_source_hashes': (row.get('result') or {}).get('source_hashes'),
                'outer_probe_contact_prompt': row.get('contact_prompt'),
                'outer_probe_contact_max_chunks': row.get('contact_max_chunks'),
                'new_physical_execution_by_reporter': False, 'saved_labels_changed': False}
        records.append(item)
        if not all(actual.values()):
            anomalies.append({'case': item['case'], 'failed_checks': [key for key, value in actual.items() if not value]})

assert len(records) == 10
report = {'scope': 'SOURCE562/job4271 same10 visited development runtime evidence only; not confirmation or qualification',
          'manifest': ref(MANIFEST), 'formal_report': ref(out / 'statistic/report.json'),
          'CPU_runtime_entry_report': ref(ROOT / 'results/harness_v5/pan562_runtime_smoke10_CPU_20261006/preparation/runtime_entry_cpu_report.json'),
          'source': plan['source_snapshot'], 'registered_runtime_flags': condition['overrides'],
          'actual_evidence_counts': dict(totals), 'fusion_source_camera_distribution': dict(fusion_cameras),
          'runtime_recipe_anomalies': anomalies, 'cases': records,
          'outer_probe_field_scope': 'ProbeExecutor.vla_act is bypassed by runtime profile; first_receipt and choices carry actual recipe',
          'physics_scope': 'Ten fresh development replays of already visited4227 states, no4246 confirmation states',
          'prior_physical_labels_replaced': False, 'new_training_rows': 0, 'qualification_authorized': False,
          'new_model_calls_by_reporter': 0, 'new_physics_by_reporter': 0, 'producer': ref(Path(__file__).resolve())}
path = out / 'runtime_pan_recipe_report.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'report': ref(path), 'actual_evidence_counts': dict(totals),
                  'fusion_source_camera_distribution': dict(fusion_cameras),
                  'runtime_recipe_anomalies': anomalies,
                  'truth': [item['saved_private_sustained_truth'] for item in records],
                  'public': [item['saved_public_verdict'] for item in records]}))
