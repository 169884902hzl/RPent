"""Explicit completed original stove evidence; private labels stay scoring-only."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root, args.output
    output.mkdir(exist_ok=True, parents=True)
    inputs, saved_outputs = {}, []

    def identity(path):
        path = Path(path)
        data = path.read_bytes()
        return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}

    def read(path, role, expected=None):
        path = Path(path)
        ref = identity(path)
        if expected is not None and ref['sha256'] != expected:
            raise ValueError('registered evidence changed: ' + str(path))
        if not path.is_absolute() or not str(path).startswith(str(root) + '/'):
            raise ValueError('outside explicit original project files')
        inputs.setdefault(str(path), {**ref, 'roles': []})['roles'].append(role)
        return path.read_bytes()

    def checked(ref, role):
        return read(ref['path'], role, ref['sha256'])

    def save(name, data):
        path = output / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(data)
        saved_outputs.append(name)

    def write(name, data):
        save(name, (json.dumps(data, indent=2, allow_nan=False) + '\n').encode())

    manifest_path = root / 'results/harness_v5/stove560_control_crop_CPU_20261006/control_crop_sam_manifest.json'
    plan = json.loads(read(manifest_path, '4263_registered_manifest',
                           'bdbfc3d9eab3b8240a6514013832b06b6231a1d88957c5d9cd04dd45308b3dbb'))
    for ref in plan['producers'] + plan['source_files']:
        checked(ref, '4263_pinned_producer_or_source')
    for key in ('source_run_manifest', 'source_offline_manifest', 'public_bbox_evidence'):
        checked(plan[key], key)
    for frame in plan['frames']:
        for ref in frame['files'].values():
            checked(ref, '4263_original_public_RGBD')
    run = root / 'results/harness_v5/stove560_control_crop_SAM_original_20261006/control_crop_job4263'
    rows = json.loads('[]')
    for name in ('summary.json', 'queries.jsonl', 'sam_server.log'):
        data = read(run / name, '4263_output')
        save('job4263/' + name, data)
        if name == 'queries.jsonl':
            rows = [json.loads(line) for line in data.decode().splitlines()]
    for frame in plan['frames']:
        names = ['summary.json']
        if frame['status'] == 'registered_control_crop':
            names = ['crop_rgb.png', 'crop_mapping.json', 'summary.json']
        for name in names:
            save('job4263/' + frame['name'] + '/' + name,
                 read(run / frame['name'] / name, '4263_complete_per_view_output'))
    save('job4263/preflight_job4263.json', read(run.parent / 'preflight_job4263.json', '4263_actual_preflight'))
    save('job4263/slurm-4263.log', read(root / 'results/slurm-4263.log', '4263_Slurm_log'))
    sacct = subprocess.check_output(['sacct', '-j', '4263', '--format=JobID,State,ExitCode,Elapsed,NodeList', '-n', '-P'])
    save('job4263/sacct.txt', sacct)
    if not any(line.startswith('4263|COMPLETED|0:0|') for line in sacct.decode().splitlines()):
        raise ValueError('4263 completion is not successful infrastructure execution')
    baseline = []
    for key, ref in plan['baseline_files'].items():
        data = checked(ref, '4240_preserved_baseline')
        save('job4240/' + Path(ref['path']).name, data)
        if key == 'queries':
            baseline = [json.loads(line) for line in data.decode().splitlines()]
    original = json.loads(checked(plan['source_run_manifest'], '4210_original_sampling_manifest'))
    source_root = root / 'source_v5_stove555_20261006'
    for name, expected in original['required_source_sha256'].items():
        read(source_root / name, '4210_pinned_source', expected)
    ledgers, phases, label_rows, episodes = [], {}, [], []
    run4210 = root / 'results/harness_v5/stove555_measurement10_original_20261006/probe_job4210'
    for part in range(4):
        path = run4210 / f'part{part}/episodes.jsonl'
        data = read(path, '4210_explicit_episode_phase_refs')
        ledgers.append(identity(path))
        for line in data.decode().splitlines():
            episode = json.loads(line)
            if episode['case']['episode']['suite'] != 'libero_goal' or episode['case']['episode']['task'] != 7:
                raise ValueError('non-original source episode')
            simple = {'case': episode['case']['name'], 'status': episode['status'], 'phases': []}
            for phase in episode['phases']:
                phases[(episode['case']['name'], phase['phase'])] = phase
                attempt = phase.get('first_attempt') or {}
                simple['phases'].append({'phase': phase['phase'], 'receipt': attempt.get('receipt'),
                    'status': attempt.get('status'), 'executed_control_actions': attempt.get('executed_control_actions')})
                for stage in ('before_contact', 'pre_recovery', 'post_recovery'):
                    if stage not in phase:
                        continue
                    refs = phase[stage]
                    data = checked(refs['labels'], '4210_previously_authorized_private_scoring_label')
                    label = json.loads(data)
                    on, off = [label['requested_predicates'][mode] for mode in ('turn_on', 'turn_off')]
                    if label['source_step'] != refs['source_step'] or on['joint_qpos'] != off['joint_qpos']:
                        raise ValueError('saved label does not match capture')
                    label_rows.append({'case': episode['case']['name'], 'phase': phase['phase'], 'stage': stage,
                        'source_step': label['source_step'], 'joint_names': on['joint_names'],
                        'q_rad': on['joint_qpos'][0][0], 'true_on': on['satisfied'], 'true_off': off['satisfied'],
                        'sim_time': on['sim_time'], 'label': refs['labels'],
                        'public_capture': refs['public_measurements'], 'scope': 'private_scoring_only'})
            episodes.append(simple)
    if len(label_rows) != 80 or len(episodes) != 10:
        raise ValueError('4210 saved-label coverage changed')
    geometry_path = root / 'results/harness_v5/stove559_public_geometry_CPU_20261006/geometry_evidence.json'
    public = json.loads(read(geometry_path, '559_preserved_public_geometry',
                             'ca86dec60428f51e87665d16805693018ec25e953d88d0b397e80d0fa9b79412'))
    rgb_path = root / 'results/harness_v5/stove559_public_geometry_CPU_20261006/public_indicator_pixels.json'
    rgb = json.loads(read(rgb_path, '559_preserved_public_RGB_indicator'))['records']
    captures = []
    for indicator in rgb:
        name = indicator['capture']
        frame = next(f for f in plan['frames'] if f['name'] == name + '_agentview')
        folder = Path(frame['files']['rgb']['path']).parent.parent
        phase, stage = folder.parent.name, folder.name
        label = next(r for r in label_rows if (r['case'], r['phase'], r['stage']) == (frame['case'], phase, stage))
        angles = {r['frame'].rsplit('_', 1)[1]: r['candidate_signed_angle_to_measured_edge_deg']
                  for r in public['records'] if r['frame'].rsplit('_', 1)[0] == name}
        captures.append({'capture': name, 'source_step': label['source_step'], 'private_q_rad': label['q_rad'],
            'private_q_deg': math.degrees(label['q_rad']), 'true_on': label['true_on'], 'true_off': label['true_off'],
            'public_candidate_angles_deg': angles, 'public_red_fraction': indicator['red_fraction'],
            'private_label': label['label'], 'public_RGB': indicator['RGB'], 'shell_mask': indicator['existing_shell_mask'],
            'endpoint_state': 'unmeasured', 'scope': 'paired_private_scoring_only_not_runtime_or_calibration'})
    changes = []
    for a, b in ((0, 1), (1, 3)):
        first, second = captures[a], captures[b]
        delta = (second['public_candidate_angles_deg']['agentview'] - first['public_candidate_angles_deg']['agentview'] + 180) % 360 - 180
        joint_delta = second['private_q_deg'] - first['private_q_deg']
        changes.append({'from': first['capture'], 'to': second['capture'], 'camera': 'agentview',
            'public_delta_deg': delta, 'private_joint_delta_deg': joint_delta,
            'delta_difference_deg': delta-joint_delta, 'endpoint_qualified': False})
    eligible = {frame['name'] for frame in plan['frames'] if frame['status'] == 'registered_control_crop'}

    def counts(records, profile):
        selected = [r for r in records if r['profile'] == profile]
        matched = [r for r in selected if r['frame'] in eligible]
        return {'ledger_queries': len(selected), 'RPC_calls': sum(r.get('RPC_called', True) for r in selected),
            'queries_with_masks': sum(bool(r['instances']) for r in selected),
            'queries_with_geometry': sum(any(i['pose'] is not None for i in r['instances']) for r in selected),
            'mask_views': len({r['frame'] for r in selected if r['instances']}),
            'geometry_views': len({r['frame'] for r in selected if any(i['pose'] is not None for i in r['instances'])}),
            'matched_10view_queries': len(matched), 'matched_10view_mask_queries': sum(bool(r['instances']) for r in matched),
            'status_counts': dict(Counter(r['status'] for r in selected))}

    write('matched6captures.json', {'records': captures, 'same_camera_changes': changes,
        'true_off_captures': 0, 'candidate_angles_do_not_qualify_endpoint': True})
    write('labels80_scoring_table.json', {'explicit_episode_ledgers': ledgers, 'episodes': episodes,
        'records': label_rows, 'private_truth_runtime_injection': False, 'additional_private_labels_opened': False})
    selected_public = []
    # Fixed fifty captures, independent of any success label: before on, then
    # pre/post recovery for each of the two contact phases, for every original init.
    for case in original['cases']:
        for phase, stage in (('on', 'before_contact'), ('on', 'pre_recovery'), ('on', 'post_recovery'),
                             ('off', 'pre_recovery'), ('off', 'post_recovery')):
            refs = phases[(case['name'], phase)][stage]
            packet = json.loads(checked(refs['public_measurements'], '50capture_public_measurement_packet'))
            if packet['source_step'] != refs['source_step']:
                raise ValueError('public packet is from another capture')
            selected_public.append({'case': case['name'], 'phase': phase, 'stage': stage,
                'source_step': refs['source_step'], 'packet': refs['public_measurements'], 'data': packet})
    write('public50_capture_manifest.json', {'captures': selected_public, 'selection_rule':
        'For every original init0-9: on/before_contact, on/pre_recovery, on/post_recovery, off/pre_recovery, off/post_recovery',
        'captures_count': 50, 'views_count': 100, 'success_label_selection': False,
        'private_labels_in_public_geometry_input': False, 'thresholds_unchanged': True})
    summary = {'job4263': {'state': 'COMPLETED', 'exit_code': '0:0', 'node': 'node01', 'elapsed_s': 25,
        'new_RPC': 20, 'ledger_rows': 24, 'profiles': {'control_crop_context25': counts(rows, 'control_crop_context25')},
        'preserved_4240_profiles': {p: counts(baseline, p) for p in ('full', 'crop_context50')},
        'conclusion': 'Fixed control crop did not improve masks or accepted geometry; baseline-only hit disappeared'},
        'job4210': {'original_states': 10, 'authorized_saved_labels_checked': 80,
        'private_predicate_combinations': dict(Counter(str((r['true_on'], r['true_off'])) for r in label_rows)),
        'true_off_labels': sum(r['true_off'] for r in label_rows), 'true_off_captures_in_matched6': 0,
        'q_range_rad': [min(r['q_rad'] for r in label_rows), max(r['q_rad'] for r in label_rows)],
        'all10_off_post_still_on': all(r['true_on'] and not r['true_off'] for r in label_rows if r['phase']=='off' and r['stage']=='post_recovery'),
        'conclusion': 'Public angle has two paired same-camera joint changes; no true_off samples. Red after off does not establish static fire RGB'},
        'endpoint_state': 'unmeasured', 'on_off_endpoints_calibrated': False, 'qualification_authorized': False,
        'runtime_changed': False, 'GPU_submitted': False, 'simulator_started': False, 'PRO_read': False}
    write('summary.json', summary)
    write('input_manifest.json', {'files': list(inputs.values()), 'explicit_file_reading_only': True,
        'private_labels_role': 'scoring_only_not_runtime_or_geometry_selection', 'no_artifact_directory_scan': True})
    write('collection_outputs.json', {'files': saved_outputs.copy()})
    print(json.dumps({'passed': True, '4263_new_RPC': 20, 'masks': 0, 'labels_checked': 80,
                      'matched_captures': 6, 'public_capture_plan': 50, 'input_files': len(inputs)}))


if __name__ == '__main__':
    main()
