"""Export only public geometry and matching robot sensors for offline diagnosis."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = ROOT / 'coordination/geometric_startups_public_clouds_20261010_r3'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    OUT.mkdir(exist_ok=False)
    rows, inputs = [], []
    for category, job in (('bottle', 5896), ('bowl', 5897), ('box', 5898)):
        ledger = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r3' / (
            category + '_geometric_sampling') / ('job' + str(job)) / 'part0/probe/episodes.jsonl'
        raw = json.loads(next(ledger.open()))
        attempt = raw['first_attempt']
        receipt = attempt['receipt']
        source = Path(raw['output_dir'])
        states_path = source / 'states.json'
        saved = json.loads(states_path.read_text())
        records = saved['steps']
        measured = next(s['state'] for s in records if s['step_idx'] == 1)
        robot = {k: measured[k] for k in ('robot0_eef_pos', 'robot0_eef_quat', 'robot0_gripper_qpos')}
        entity = next(e for e in attempt['public_before']['entities'] if e['id'] == receipt['object'])
        dest = OUT / category
        dest.mkdir()
        files = []
        cloud_path = source / ('analytic_target_' + entity['id'] + '.npz/01.npz')
        for path, name in [(cloud_path, 'target.npz'), *[(source / (camera + '_world_high.npz/01.npz'),
                            camera + '_world.npz') for camera in ('agentview', 'wrist')]]:
            copied = dest / name
            shutil.copyfile(path, copied)
            files.append({'original': pin(path), 'copied': pin(copied)})
        inputs.extend([pin(ledger), pin(states_path)])
        rows.append({'category': category, 'case_name': raw['case']['name'],
                     'state_sha256': raw['case']['state_sha256'], 'public_name': entity['name'],
                     'public_robot': robot, 'saved_measurement_step': 1, 'files': files,
                     'initial_plan': receipt['analytic_initial_plan'],
                     'measurement_step_matched': all('/01.npz' in f['original']['path'] for f in files),
                     'private_pose_or_contact_fields_included': False,
                     'training_allowed': False, 'qualification_allowed': False})
    path = OUT / 'records.json'
    path.write_text(json.dumps(rows, indent=2) + '\n')
    manifest = {'producer': pin(Path(__file__)), 'inputs': inputs, 'records': pin(path),
                'n': len(rows), 'scope': 'public RGB-D plus same-step robot sensors only',
                'private_labels_available_to_candidate_replay': False,
                'training_allowed': False, 'qualification_allowed': False}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
