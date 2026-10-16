"""Recheck saved payload-collision pixels using public pre-lift observations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.bounded_payload import moving_payload_pixels
from robots.libero.v5_geometric_grasp import _voxel


def replay(path, index):
    sources = {}
    def record(p):
        p = Path(p)
        sources[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        return p
    def load(p):
        with np.load(record(p)) as data:
            return data[data.files[0]]
    rows = [json.loads(line) for line in record(path).read_text().splitlines()]
    current = rows[index]
    prior = rows[index-1]
    held = current['request']['robot']['held_anchor_id']
    if not any(r['skill'] == 'lift' and r['outcome'] == 'success' for r in prior['receipts']):
        raise ValueError('the preceding row must contain a publicly verified lift')
    targets, scenes = [], []
    for camera, reference in prior['perception_evidence'][held]['sam_mask_files'].items():
        world = load(path.parent/(camera+'_world_high.npz')/f"{reference['source_step']:02d}.npz")
        mask = load(reference['path']).astype(bool)
        targets.append(world[mask])
        scenes.append(world.reshape(-1, 3))
    reference = {'target': np.concatenate(targets), 'scene': _voxel(np.concatenate(scenes), .001),
        'robot': prior['request']['robot'],
        'capture_step': prior['request']['anchors'][0]['evidence'][0]['capture_step']}
    failures = [r for r in current['candidate_screen_diagnostics'] if r.get('payload_point')]
    points = np.array([r['obstacle_point'] for r in failures])
    associated, evidence = moving_payload_pixels(points, reference, current['request']['robot'])
    return {'choices': str(path), 'row_index': index, 'public_evidence': evidence,
        'obstacles': [{'skill': row['skill'], 'parameters': row['parameters'],
            'point': row['obstacle_point'], 'identified_as_moving_payload': bool(owned)}
            for row, owned in zip(failures, associated)],
        'sources': sources, 'simulation_executed': False, 'task_success_claim': False,
        'private_truth_used': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--choices', type=Path, required=True)
    parser.add_argument('--row', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.choices.resolve(strict=True), args.row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result['public_evidence']))


if __name__ == '__main__':
    main()
