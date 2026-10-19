"""Check the saved public identity ambiguity and existing oracle recovery."""
import argparse
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--mask-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    from robots.libero.bounded_offline_labels import annotate_prefix, load_annotation_state

    rows = []
    for row in json.loads(args.mask_report.read_bytes())['rows']:
        directory = Path(row['candidates'][0]['mask']['path']).parents[1] / 'subtask00_pick'
        annotation = directory / 'private_annotation.pkl'
        checkpoint = directory / 'private_branchpoint.pkl'
        state = load_annotation_state(annotation, hashlib.sha256(annotation.read_bytes()).hexdigest())
        saved = pickle.loads(checkpoint.read_bytes())
        started = time.perf_counter()
        labels = annotate_prefix(state, saved['request'], [])
        candidates = {c['id']: c for c in saved['request']['candidates']}
        selected = candidates[labels['selected']] if labels['selected'] else None
        rows.append({'case': row['case'], 'source_binding_failure': row['source_binding_failure'],
            'same_class_measurements': row['candidates'], 'labels': labels, 'selected': selected,
            'existing_recovery_is_observe': bool(selected and selected['skill'] == 'observe'),
            'wall_s': time.perf_counter()-started,
            'inputs': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in (annotation, checkpoint)]})
    result = {'rows': rows, 'training': False, 'gpu_used': False, 'physics_steps': 0,
        'scope': 'saved public request plus existing private oracle rules; no new PRO rule',
        'source_snapshot': str(args.source),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps([{'case': r['case'], 'selected': r['selected'], 'wall_s': r['wall_s']}
        for r in rows]))


if __name__ == '__main__':
    main()
