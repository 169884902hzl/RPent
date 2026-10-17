"""Recheck saved payload-collision pixels using public pre-lift observations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.bounded_payload import moving_payload_pixels
from robots.libero.v5_geometric_grasp import _voxel
from robots.libero.v5_grasp_geometry import (
    clean_object_mask,
    complete_crossview_boundary,
    complete_instance_boundary,
    complete_planar_boundary,
)


def replay(path, index, capture_dir=None):
    sources = {}
    def record(p):
        p = Path(p)
        sources[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        return p
    def load(p):
        with np.load(record(p)) as data:
            return data[data.files[0]]
    capture_dir = Path(capture_dir) if capture_dir is not None else path.parent
    def artifact(p):
        p = Path(p)
        copied = capture_dir/p.parent.name/p.name
        return copied if copied.is_file() else p
    def instance(row, anchor_id):
        views, scenes = {}, []
        anchor = next(a for a in row['request']['anchors'] if a['id'] == anchor_id)
        lower = np.asarray(anchor['xyz_m'])-np.asarray(anchor['size_m'])/2
        upper = np.asarray(anchor['xyz_m'])+np.asarray(anchor['size_m'])/2
        for camera, item in row['perception_evidence'][anchor_id]['sam_mask_files'].items():
            world = load(capture_dir/(camera+'_world_high.npz')/f"{item['source_step']:02d}.npz")
            mask = load(artifact(item['path'])).astype(bool)
            if row['request']['robot']['held_anchor_id'] == anchor_id:
                mask, _ = clean_object_mask(world, mask, prior_lower=lower, prior_upper=upper)
            mask, _ = complete_instance_boundary(world, mask)
            mask, _ = complete_planar_boundary(world, mask)
            views[camera] = world, mask
            scenes.append(world.reshape(-1, 3))
        clouds = []
        for camera, (world, mask) in views.items():
            if len(views) == 2:
                other = next(c for c in views if c != camera)
                step = row['perception_evidence'][anchor_id]['sam_mask_files'][other]['source_step']
                metadata = json.loads(record(capture_dir/(other+'_metadata.json')/f'{step:02d}.json').read_text())
                mask, _ = complete_crossview_boundary(world, mask, *views[other], metadata)
            clouds.append(world[mask])
        return np.concatenate(clouds), np.concatenate(scenes)
    rows = [json.loads(line) for line in record(path).read_text().splitlines()]
    current = rows[index]
    prior = rows[index-1]
    held = current['request']['robot']['held_anchor_id']
    if not any(r['skill'] == 'lift' and r['outcome'] == 'success' for r in prior['receipts']):
        raise ValueError('the preceding row must contain a publicly verified lift')
    target, scene = instance(prior, held)
    current_target, _ = instance(current, held)
    reference = {'target': target, 'scene': _voxel(scene, .001),
        'robot': prior['request']['robot'],
        'capture_step': prior['request']['anchors'][0]['evidence'][0]['capture_step']}
    failures = [r for r in current['candidate_screen_diagnostics'] if r.get('payload_point')]
    points = np.array([r['obstacle_point'] for r in failures])
    associated, evidence = moving_payload_pixels(points, reference, current['request']['robot'],
                                                  current_target=current_target)
    return {'choices': str(path), 'row_index': index, 'public_evidence': evidence,
        'obstacles': [{'skill': row['skill'], 'parameters': row['parameters'],
            'point': row['obstacle_point'], 'identified_as_moving_payload': bool(owned)}
            for row, owned in zip(failures, associated)],
        'sources': sources, 'simulation_executed': False, 'task_success_claim': False,
        'private_truth_used': False,
        'limitations': ['CPU surface association only; robot self filtering is not replayed.',
                        'A fresh route screen and simulator run are required before claiming repair.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--choices', type=Path, required=True)
    parser.add_argument('--row', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capture-dir', type=Path, help='Local copies retaining artifact-directory names')
    args = parser.parse_args()
    result = replay(args.choices.resolve(strict=True), args.row, args.capture_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result['public_evidence']))


if __name__ == '__main__':
    main()
