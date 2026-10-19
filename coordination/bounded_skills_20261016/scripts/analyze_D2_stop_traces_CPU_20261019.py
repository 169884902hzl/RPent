"""Describe the old stopped VLA paths without running or relabeling them."""
import argparse
import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    rows = []
    for item in json.loads(args.registry.read_bytes())['rows']:
        old = json.loads(Path(item['raw_summary']).read_bytes())
        if old['success'] is not False:
            continue
        checkpoint = pickle.loads(Path(item['branchpoint']).read_bytes())
        records = [json.loads(line) for line in Path(old['choices']['path']).read_bytes().splitlines()]
        execution = next(detail['execution'] for record in records
            for detail in record['execution_details'] if 'skill_stop_reason' in detail.get('execution', {}))
        trace, checks = execution['trace'], execution['checks']
        positions = np.asarray([trace[0]['before']['eef_xyz_m'],
            *[r['after']['eef_xyz_m'] for r in trace]])
        entities = checkpoint['public_runtime']['scene']['entities']
        source = entities[old['source_public_id']]
        closest = sorted([{'id': e.id, 'name': e.name, 'visible': e.visible,
            'capture_step': e.source_step, 'distance_m': float(np.linalg.norm(positions[-1]-e.xyz))}
            for e in entities.values() if e.name != 'table' and not e.name.startswith('area ')],
            key=lambda r: (r['distance_m'], r['id']))[:3]
        tail = positions[-16:]
        rows.append({'case': item['case'], 'sampling_seed': item['seed'],
            'old_private_endpoint_success': old['success'], 'old_outer_reason': old['reason'],
            'old_skill_stop_reason': execution['skill_stop_reason'], 'controls': len(trace),
            'inference_blocks': execution['blocks_used'], 'public_source_id': source.id,
            'source_distance_initial_m': float(np.linalg.norm(positions[0]-source.xyz)),
            'source_distance_final_m': float(np.linalg.norm(positions[-1]-source.xyz)),
            'path_length_m': float(np.linalg.norm(np.diff(positions, axis=0), axis=1).sum()),
            'last15_controls_net_displacement_m': float(np.linalg.norm(tail[-1]-tail[0])),
            'last15_controls_path_length_m': float(np.linalg.norm(np.diff(tail, axis=0), axis=1).sum()),
            'public_checks': len(checks),
            'checks_with_nonfinite_progress': sum(not np.isfinite(c['progress_vector_m']).all() for c in checks),
            'tail15_checks_with_nonfinite_progress': sum(not np.isfinite(c['progress_vector_m']).all() for c in checks[-15:]),
            'nearest_initial_public_entities_at_vla_end': closest,
            'closest_entity_interpretation': 'measured initial centres only; not contact identity or private final object pose',
            'raw_summary': {'path': item['raw_summary'], 'sha256': hashlib.sha256(Path(item['raw_summary']).read_bytes()).hexdigest()}})
    with args.output.open('x') as stream:
        json.dump({'rows': rows, 'training': False, 'physics_steps': 0, 'gpu_used': False,
            'scope': 'descriptive CPU audit of the three stopped old-rule traces; labels unchanged'}, stream, indent=2)
        stream.write('\n')
    print(json.dumps(rows))


if __name__ == '__main__':
    main()
