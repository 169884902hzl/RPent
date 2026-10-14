"""Read public individual-finger sensors without changing closed verdicts."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
INDEX = ROOT/'coordination/grasp_geometry_confirmation_event_closed_20261010_r2/fiveclass/rows.jsonl'
OUT = ROOT/'coordination/grasp_closed_public_finger_sensors_20261011_r1'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    rows, cache = [], {}
    for item in map(json.loads, INDEX.read_text().splitlines()):
        path = Path(item['input']['path'])
        if path not in cache:
            if pin(path) != item['input']:
                raise ValueError('closed ledger changed')
            cache[path] = path.read_text().splitlines()
        raw = json.loads(cache[path][item['line']-1])
        first = raw.get('first_attempt') or {}
        pair = (first.get('verification_measurements') or {}).get('independent_grasp') or {}
        states_path = Path(raw['output_dir'])/'states.json'
        saved = json.loads(states_path.read_text())['steps'] if states_path.exists() else []
        sensors = {step['step_idx']: step['state'] for step in saved}
        frames = []
        for frame in pair.get('frames', []):
            source_steps = {view['measurement']['source_step'] for view in frame['per_view'].values()
                            if view.get('current_measurement') and view.get('measurement')}
            if len(source_steps) != 1:
                frames.append({'status': 'no_unique_fresh_capture'})
                continue
            step = next(iter(source_steps))
            state = sensors.get(step)
            if state is None:
                frames.append({'status': 'public_capture_missing', 'step': step})
                continue
            q = np.asarray(state['robot0_gripper_qpos'], dtype=float)
            if q.shape != (2,):
                raise ValueError('expected two public finger position sensors')
            error = float(np.linalg.norm(np.asarray(state['robot0_eef_pos'])-frame['eef_xyz']))
            if error > 1e-6:
                raise ValueError('frame and public sensors do not match')
            frames.append({'status': 'matched_public_capture', 'step': step,
                'finger_qpos_m': q.tolist(), 'minimum_absolute_finger_qpos_m': float(abs(q).min()),
                'maximum_absolute_finger_qpos_m': float(abs(q).max()),
                'finger_asymmetry_m': float(abs(abs(q[0])-abs(q[1]))),
                'summed_opening_m': float(abs(q).sum()),
                'frame_opening_m': frame['opening_m'], 'eef_match_error_m': error})
        truth, public = item['registered_v3'], item['public']
        direction = ('unknown' if truth is None else 'null' if public is None else
                     ('TP' if public else 'FN') if truth else ('FP' if public else 'TN'))
        rows.append({'case': item['case'], 'category': item['group'], 'direction': direction,
            'registered_v3_unchanged': truth, 'saved_public_unchanged': public,
            'frames': frames, 'input': item['input'], 'line': item['line'],
            'states': pin(states_path) if states_path.exists() else None,
            'closed_verdict_changed': False, 'training_allowed': False})
    OUT.mkdir(parents=True, exist_ok=False)
    records = OUT/'records.jsonl'
    records.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    groups = {}
    for direction in ('FP', 'FN', 'TP', 'TN', 'null', 'unknown'):
        subset = [row for row in rows if row['direction'] == direction]
        frames = [frame for row in subset for frame in row['frames']
                  if frame['status'] == 'matched_public_capture']
        values = {key: np.quantile([frame[key] for frame in frames], [0, .1, .5, .9, 1]).tolist()
                  if frames else None for key in ('minimum_absolute_finger_qpos_m',
                      'maximum_absolute_finger_qpos_m', 'finger_asymmetry_m')}
        groups[direction] = {'cases': len(subset), 'matched_frames': len(frames),
            'frame_status': dict(Counter(frame['status'] for row in subset for frame in row['frames'])),
            'quantiles_min_p10_median_p90_max': values}
    report = {'producer': pin(Path(__file__)), 'index': pin(INDEX), 'records': pin(records),
        'groups': groups, 'scope': 'diagnosis only; no threshold selected or public verdict recomputed',
        'runtime_inputs': 'saved RGB-D frame indices and same-frame robot proprioception only',
        'private_truth_used_only_for_diagnostic_grouping': True,
        'closed_verdict_changed': False, 'training_allowed': False}
    (OUT/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(groups))


if __name__ == '__main__':
    main()
