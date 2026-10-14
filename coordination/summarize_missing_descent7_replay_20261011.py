"""Complete the seven missing contact observations using separate development replays."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refine_descent30_contacts_20261011 import kind

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
RUN = ROOT/'results/harness_v5/grasp_measurement_development_20261011_r4/cup'
OLD = ROOT/'coordination/grasp_descent30_contacts_20261011_r2/descent30.jsonl'
OUT = ROOT/'coordination/grasp_missing_descent7_replay_20261011_r1'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    selected = [row for row in map(json.loads, OLD.read_text().splitlines())
                if row['contact_evidence']=='missing']
    if len(selected)!=7:
        raise ValueError('expected exactly seven missing old observations')
    new, inputs = {}, []
    for path in sorted(RUN.glob('job*/part*/probe/episodes.jsonl')):
        reference = pin(path)
        inputs.append(reference)
        for line, text in enumerate(path.read_text().splitlines(), 1):
            row = json.loads(text)
            seed = row['case']['layout_seed']
            if seed in new:
                raise ValueError('duplicate replayed development state')
            new[seed] = (row, reference, line)
    rows = []
    for old in selected:
        raw, reference, line = new[old['layout_seed']]
        phase = raw.get('private_grasp_phase') or {}
        first = raw.get('first_attempt') or {}
        hold_controls = (first.get('private_setup_hold') or {}).get('diagnostic_actions', 0)
        samples = phase.get('samples') or []
        if phase.get('trace_version')!='every-executed-skill-control/1-dev':
            raise ValueError('full replay control trace is missing')
        if hold_controls:
            samples = samples[:-hold_controls]
        reason = (first.get('receipt') or {}).get('failure_reason')
        reproduced = reason=='analytic_descend_not_reached'
        terminal = samples[-10:] if reproduced else []
        contacts = [contact for sample in terminal for contact in sample['scene_contacts']
                    if any('gripper' in contact[key] or 'robot0' in contact[key]
                           for key in ('geom1', 'geom2'))]
        names = sorted({contact[key] for contact in contacts for key in ('geom1','geom2')
                        if 'gripper' not in contact[key] and 'robot0' not in contact[key]})
        target = raw['case']['object_symbol']
        categories = sorted({kind(name, target) for name in names})
        movements = [move for move in first.get('motion_evidence', []) if move.get('analytic_stage')=='descend']
        motion = movements[-1] if movements else {}
        rows.append({'case': old['case'], 'layout_seed': old['layout_seed'],
                     'state_sha256': raw['case']['state_sha256'], 'old_input': old['input'],
                     'old_line': old['line'], 'new_input': reference, 'new_line': line,
                     'old_contact_evidence_still_missing': True,
                     'separate_development_replay': True, 'same_descent_failure_reproduced': reproduced,
                     'new_failure_reason': reason, 'trace_controls_before_private_hold': len(samples),
                     'replayed_terminal_contact_class': ('+'.join(categories) if categories else
                         'no_robot_collision_observed_at_servo_timeout' if reproduced else 'old_descent_failure_not_reproduced'),
                     'observed_contacts': [{'geom': name, 'class': kind(name,target)} for name in names],
                     'final_dist_m': motion.get('final_dist_m'), 'steps_used': motion.get('steps_used'),
                     'max_steps': motion.get('max_steps'), 'last10': terminal,
                     'contact_is_observation_not_causal_proof': True,
                     'closed_confirmation_score_changed': False, 'training_allowed': False})
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT/'paired_descent7.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    report = {'n': len(rows), 'same_failure_reproduced': sum(row['same_descent_failure_reproduced'] for row in rows),
              'replay_classes': dict(Counter(row['replayed_terminal_contact_class'] for row in rows)),
              'paired_rows': pin(path), 'old_rows': pin(OLD), 'inputs': inputs, 'producer': pin(Path(__file__)),
              'old_missing_evidence_not_backfilled_as_historical_fact': True,
              'closed_confirmation_scores_changed': False, 'training_allowed': False}
    (OUT/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: value for key, value in report.items() if key!='inputs'}, indent=2))


if __name__=='__main__':
    main()
