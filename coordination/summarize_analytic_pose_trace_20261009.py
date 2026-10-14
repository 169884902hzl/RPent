"""Diagnose retained reach failures without feeding private contacts to control."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records, inputs = [], []
    for path in sorted(args.root.glob('*/job*/part*/probe/episodes.jsonl')):
        inputs.append(ref(path))
        for line in path.read_text().splitlines():
            row = json.loads(line)
            choice_path = Path(row['output_dir']) / 'choices.jsonl'
            inputs.append(ref(choice_path))
            for line in choice_path.read_text().splitlines():
                event = json.loads(line)
                for motion in event.get('motion_evidence', []):
                    if not motion.get('analytic_stage'):
                        continue
                    trace = motion.get('trajectory', [])
                    tail = trace[-10:]
                    eef = [s.get('eef', s.get('eef_pos')) for s in tail]
                    delta = (np.asarray(eef[-1]) - np.asarray(eef[0])).tolist() if len(eef) >= 2 else None
                    contacts, margins = Counter(), []
                    for step in tail:
                        diagnostic = step.get('contact_and_joints', {})
                        for contact in diagnostic.get('contacts', []):
                            a, b = contact['geom1'], contact['geom2']
                            if any('gripper' in name or 'finger' in name or 'hand' in name for name in (a, b)):
                                contacts[' / '.join(sorted((a, b)))] += 1
                        margins.extend(j['limit_margin_rad'] for j in diagnostic.get('joints', [])
                                       if j.get('limit_margin_rad') is not None)
                    unreached = motion.get('final_dist_m', 0) > .015
                    progress = float(np.linalg.norm(delta)) if delta is not None else None
                    reason = ('reached' if not unreached else 'unknown_no_trace' if progress is None else
                              'stalled_with_robot_contact' if progress < .01 and contacts else
                              'stalled_near_joint_limit' if progress < .01 and margins and min(margins) < .02 else
                              'still_moving' if progress >= .01 else 'stalled_cause_unresolved')
                    records.append({'case': row['case']['name'], 'stage': motion['analytic_stage'],
                        'target_xyz': motion.get('target_xyz'), 'final_eef_pos': motion.get('final_eef_pos'),
                        'final_dist_m': motion.get('final_dist_m'), 'steps_used': motion.get('steps_used'),
                        'last10_delta_m': delta, 'last10_motion_m': progress,
                        'last10_robot_contact_samples': dict(contacts),
                        'min_last10_joint_limit_margin_rad': min(margins) if margins else None,
                        'diagnosis': reason, 'source_choices': ref(choice_path),
                        'private_diagnostic_only': True, 'training_allowed': False})
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output / 'motion_diagnoses.jsonl'
    output.write_text(''.join(json.dumps(row) + '\n' for row in records))
    report = {'recorded_motion_stages': len(records),
        'diagnoses': dict(Counter(r['diagnosis'] for r in records)), 'records': ref(output),
        'inputs': inputs, 'source': ref(Path(__file__)), 'confirmation': False, 'training_allowed': False,
        'limit': 'contacts and joints identify measured stalls; incomplete traces remain unresolved; private labels never control routes'}
    manifest = args.output / 'manifest.json'
    manifest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'manifest': ref(manifest), 'diagnoses': report['diagnoses'],
                     'records': records}))


if __name__ == '__main__':
    main()
