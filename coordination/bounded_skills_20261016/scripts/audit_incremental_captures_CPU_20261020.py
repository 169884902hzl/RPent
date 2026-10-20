"""Compare cached-vs-fresh saved public anchor measurements on original captures."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import imageio.v3 as iio
import numpy as np

from robots.libero.bounded_incremental import roi_change


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--windows', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--episodes', type=int, default=24)
    args = p.parse_args()
    episodes = json.load(gzip.open(args.windows))['episodes'][:args.episodes]
    records, missing = [], []
    for episode in episodes:
        choices = Path(episode['choices_meta']['path'])
        previous = None
        frames = {}
        def frame(camera, step):
            key = camera, step
            if key not in frames:
                rgb = choices.parent/(camera+'_high.png')/f'{step:02d}.png'
                world = choices.parent/(camera+'_world_high.npz')/f'{step:02d}.npz'
                with np.load(world) as saved:
                    points = saved['array']
                frames[key] = iio.imread(rgb), points
            return frames[key]
        with choices.open() as stream:
            for ordinal, line in enumerate(stream):
                row = json.loads(line)
                if 'request' not in row:
                    continue
                request = row['request']
                if previous is not None:
                    prior, old_row = previous
                    lookup = {a['id']: a for a in request['anchors']}
                    touched = {a for cid in (old_row.get('decision') or {}).get('candidate_ids', [])
                        for c in prior['candidates'] if c['id'] == cid
                        for a in (c['parameters'].get('anchor_id'), c['parameters'].get('target_id')) if a}
                    for anchor in prior['anchors']:
                        current = lookup.get(anchor['id'])
                        if current is None or current['cached'] or anchor['cached']:
                            continue
                        old = max(e['capture_step'] for e in anchor['evidence'])
                        new = max(e['capture_step'] for e in current['evidence'])
                        if new <= old:
                            continue
                        centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
                        try:
                            views = {}
                            for camera in ('agentview','wrist'):
                                a, wa = frame(camera, old); b, wb = frame(camera, new)
                                views[camera] = roi_change(a, b, wa, wb, centre-size/2, centre+size/2)
                            result = {'changed':any(v['changed'] for v in views.values()),'views':views}
                        except FileNotFoundError as exc:
                            missing.append(str(exc)); continue
                        dp = float(np.linalg.norm(np.asarray(current['xyz_m'])-centre))
                        ds = float(np.max(np.abs(np.asarray(current['size_m'])-size)))
                        forced = anchor['id'] in touched or prior['robot']['held_anchor_id'] == anchor['id']
                        records.append({'episode': episode['index'], 'decision': ordinal, 'anchor': anchor['id'],
                            'label': anchor['label'], 'old_capture_step': old, 'new_capture_step': new,
                            'roi': result, 'forced_by_contact_or_holding': forced,
                            'position_difference_m': dp, 'max_size_difference_m': ds,
                            'measurement_changed_over_1cm': dp > .01 or ds > .01,
                            'missed_measurement_change': not forced and not result['changed'] and (dp > .01 or ds > .01)})
                previous = request, row
                # Only adjacent request pairs are compared. Bound decoded frames.
                frames.clear()
    unchanged = [r for r in records if not r['roi']['changed'] and not r['forced_by_contact_or_holding']]
    output = {'original_episodes': len(episodes), 'records': records, 'compared_anchors': len(records),
        'cache_eligible': len(unchanged), 'missed_measurement_changes': sum(r['missed_measurement_change'] for r in records),
        'max_cached_position_difference_m': max((r['position_difference_m'] for r in unchanged), default=None),
        'max_cached_size_difference_m': max((r['max_size_difference_m'] for r in unchanged), default=None),
        'missing_captures': missing, 'physics_steps': 0, 'rpc_calls': 0, 'training': False,
        'thresholds': {'position_and_size_m': .01},
        'scope': 'saved public measurements, not ground-truth motion; ROI-only eligibility is conservative; route proximity still forces refresh',
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with args.output.open('x') as stream:
        json.dump(output, stream, indent=2)
    print(json.dumps({k:v for k,v in output.items() if k not in {'records','missing_captures'}}))


if __name__ == '__main__':
    main()
