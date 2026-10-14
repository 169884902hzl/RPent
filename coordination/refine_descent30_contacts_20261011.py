"""Name the observed blockers separately from target contact and missing evidence."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
INDEX = ROOT/'coordination/grasp_closed_measurement_diagnosis_20261011_r1/descent30.jsonl'
OUT = ROOT/'coordination/grasp_descent30_contacts_20261011_r2'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def kind(name, target):
    if name == target or name.startswith(target+'_'):
        return 'selected_target_object'
    if any(token in name for token in ('table', 'floor')):
        return 'table_or_floor'
    if any(token in name for token in ('cabinet', 'drawer', 'microwave', 'stove', 'wine_rack')):
        return 'cabinet_or_fixture'
    return 'other_object'


def main():
    rows, cache = [], {}
    for old in map(json.loads, INDEX.read_text().splitlines()):
        path = Path(old['input']['path'])
        if path not in cache:
            if pin(path) != old['input']:
                raise ValueError('closed original ledger changed')
            cache[path] = path.read_text().splitlines()
        raw = json.loads(cache[path][old['line']-1])
        first = raw['first_attempt']
        motion = [move for move in first['motion_evidence'] if move.get('analytic_stage')=='descend'][-1]
        target = raw['case']['object_symbol']
        names = old['obstacle_names']
        categories = sorted({kind(name, target) for name in names})
        last = (motion.get('trajectory') or [])[-10:]
        start_dist = (last[0].get('dist', last[0].get('dist_to_target_m')) if last else None)
        end_dist = (last[-1].get('dist', last[-1].get('dist_to_target_m')) if last else None)
        rows.append({'case': old['case'], 'category': old['group'], 'layout_seed': old['layout_seed'],
                     'input': old['input'], 'line': old['line'], 'target_symbol': target,
                     'contact_evidence': 'missing' if old['classification']=='contact_evidence_missing' else 'saved',
                     'observed_contact_classes': categories,
                     'observed_contacts': [{'geom': name, 'class': kind(name, target)} for name in names],
                     'classification': '+'.join(categories) if categories else old['classification'],
                     'final_dist_m': motion.get('final_dist_m'),
                     'final_pitch_rad': motion.get('final_pitch'),
                     'final_yaw_error_rad': motion.get('final_yaw_err'),
                     'steps_used': motion.get('steps_used'), 'max_steps': motion.get('max_steps'),
                     'last10_distance_reduction_m': start_dist-end_dist if start_dist is not None and end_dist is not None else None,
                     'contact_is_observation_not_causal_proof': True, 'closed_verdict_changed': False,
                     'training_allowed': False})
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT/'descent30.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    report = {'n': len(rows), 'contact_evidence_missing': sum(row['contact_evidence']=='missing' for row in rows),
              'observed_contact_classes': dict(Counter(row['classification'] for row in rows)),
              'rows': pin(path), 'input': pin(INDEX), 'producer': pin(Path(__file__)),
              'legacy_report_retained': True, 'closed_verdicts_changed': False, 'training_allowed': False}
    (OUT/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__=='__main__':
    main()
