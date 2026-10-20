"""Calibrate public stagnation on original220 only and register move forks."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from rpent.skill_package.progress import PublicProgress, VERSION


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--windows', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    data = json.load(gzip.open(args.windows))
    assert not data['errors'] and len(data['episodes']) == 220
    episodes, forks = [], []
    for episode in data['episodes']:
        path = Path(episode['choices_meta']['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != episode['choices_meta']['sha256']:
            raise ValueError(f'changed choices: {path}')
        monitor = PublicProgress()
        decisions = []
        windows = {w['index']: w for w in episode['windows']}
        with path.open() as stream:
            for ordinal, line in enumerate(stream):
                row = json.loads(line)
                if 'request' not in row:
                    continue
                request = row['request']
                count = monitor.update(request)
                index = row.get('index', ordinal)
                decisions.append({'index': index, 'stagnant': count,
                    'reasons': list(monitor.last_reasons),
                    'window_end_s': windows.get(index, {}).get('end_s')})
                chosen = (row.get('decision') or {}).get('candidate_ids', [])
                catalog = {c['id']: c for c in request['candidates']}
                for cid in chosen:
                    candidate = catalog[cid]
                    if candidate['skill'] == 'move_to':
                        forks.append({'episode_index': episode['index'],
                            'case': episode['case'], 'decision_index': index,
                            'choices': episode['choices_meta'], 'candidate': candidate,
                            'snapshot': row.get('private_pre_execution_snapshot'),
                            'annotation_state': row.get('private_prefix_annotation_state'),
                            'prefix': chosen[:chosen.index(cid)]})
        episodes.append({'index': episode['index'], 'case': episode['case']['name'],
            'success': episode['success'], 'wall_s': episode['wall_s'],
            'max_stagnant': max((d['stagnant'] for d in decisions), default=0),
            'decisions': decisions})
    threshold = 1 + max(e['max_stagnant'] for e in episodes if e['success'])
    sweep = []
    for n in range(1, max(e['max_stagnant'] for e in episodes)+2):
        cut = []
        for episode in episodes:
            row = next((d for d in episode['decisions'] if d['stagnant'] >= n), None)
            if row:
                # Terminate before the stagnant request is executed.
                previous = [d['window_end_s'] for d in episode['decisions']
                    if d['index'] < row['index'] and d['window_end_s'] is not None]
                end = previous[-1] if previous else 0.
                cut.append({'index': episode['index'], 'success': episode['success'],
                    'saved_wall_s': max(0., episode['wall_s']-end)})
        sweep.append({'N': n, 'cut_successes': sum(e['success'] for e in cut),
            'cut_episodes': len(cut), 'saved_wall_s': sum(e['saved_wall_s'] for e in cut),
            'episodes': cut})
    # Deterministic first 100 positions, in registered episode/decision order.
    selected = [f for f in forks if not f['prefix'] and f['snapshot']][:100]
    output = {'progress_version': VERSION, 'selected_N': threshold,
        'selection_domain': 'original220_only', 'windows': str(args.windows),
        'windows_sha256': hashlib.sha256(args.windows.read_bytes()).hexdigest(),
        'episodes': episodes, 'threshold_sweep': sweep,
        'move_to_positions': len(forks), 'move_fork_registration': selected,
        'training': False, 'physics_steps': 0,
        'saved_wall_scope': 'historical remaining elapsed time; excludes new terminal request overhead'}
    with args.output.open('x') as stream:
        json.dump(output, stream, indent=2)
    print(json.dumps({'N': threshold, 'episodes': len(episodes), 'move_forks': len(selected)}))


if __name__ == '__main__':
    main()
