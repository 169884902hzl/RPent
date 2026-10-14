"""Export registered confirmation states for permanent training exclusion."""
import argparse
import hashlib
import json
from pathlib import Path


def pin(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows, inputs, states = [], [], set()
    for category in ('bottle', 'bowl', 'box', 'cup', 'frypan'):
        prep = args.root / category / 'preparation'
        submission = json.loads((prep / 'submission.json').read_text())
        path = Path(submission['plan']['path'])
        if pin(path) != submission['plan']:
            raise ValueError('registered confirmation plan changed')
        plan = json.loads(path.read_text())
        if plan['training_allowed'] or not plan['confirmation']:
            raise ValueError('expected isolated confirmation')
        inputs.append(pin(path))
        for case in plan['cases']:
            if not case['permanent_training_exclusion'] or case['state_sha256'] in states:
                raise ValueError('duplicate or unprotected confirmation state')
            states.add(case['state_sha256'])
            layout = case['registered_layout_state']
            if pin(Path(layout['path'])) != layout:
                raise ValueError('registered layout changed')
            rows.append({'category': category, 'case': case['name'],
                'layout_seed': case['layout_seed'], 'state_sha256': case['state_sha256'],
                'registered_layout': layout, 'episode': case['episode'], 'plan': pin(path),
                'permanent_training_exclusion': True, 'training_allowed': False,
                'scope': 'exclusion metadata only; never a model input or training example'})
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / 'excluded_states.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    (args.output / 'manifest.json').write_text(json.dumps({
        'registered_n': len(rows), 'plans': inputs, 'records': pin(path),
        'producer': pin(Path(__file__)), 'permanent_training_exclusion': True,
        'training_allowed': False, 'physical_outcomes_used': False,
        'limits': ['This index lists the 500 executed confirmation states; it does not revoke '
                   'permanent exclusions already registered for the rest of their pools.']}, indent=2) + '\n')
    print(json.dumps({'registered_n': len(rows), 'exclusion_index': str(path)}))


if __name__ == '__main__':
    main()
