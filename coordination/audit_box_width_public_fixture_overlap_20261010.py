"""Locate old oversized package bounds using saved public RGB-D evidence."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from robots.libero.v6_som import project_bounds


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def bounds_fraction(inner, outer):
    lo, hi = np.array(inner['lower']), np.array(inner['upper'])
    extent = np.maximum(hi - lo, 0)
    overlap = np.maximum(np.minimum(hi, outer['upper']) - np.maximum(lo, outer['lower']), 0)
    return float(np.prod(overlap) / np.prod(extent)) if np.prod(extent) else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--anomalies', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for row in map(json.loads, args.anomalies.open()):
        if row['category'] != 'box':
            continue
        record = row['input']
        path = Path(record['path'])
        if pin(path)['sha256'] != record['sha256']:
            raise ValueError('saved public choice changed')
        choice = json.loads(path.read_text().splitlines()[-1])
        before = row['selected_entity_before']
        after = row['same_id_after']
        if after is None:
            raise ValueError('expected every old width anomaly to have measured refined bounds')
        fixtures = [e for e in choice['public_after']['entities']
                    if e['name'] == 'cabinet' and e['visible']]
        fixtures = sorted(fixtures, key=lambda e: bounds_fraction(after, e), reverse=True)
        nearest = fixtures[0] if fixtures else None
        item = {'case': row['case'], 'state_sha256': row['state_sha256'],
                'choice': pin(path), 'entity_before': before, 'entity_refined': after,
                'refined_planned_width_m': row['plan']['measured_width_m'],
                'measured_centre_shift_m': math.dist(before['xyz'], after['xyz']),
                'best_measured_fixture': nearest,
                'refined_bound_fraction_in_fixture': bounds_fraction(after, nearest) if nearest else None,
                'old_sam_mask_available': False, 'exact_old_mask_contamination': 'unrecoverable',
                'public_only': True, 'training_allowed': False, 'views': []}
        frames = json.loads((path.parent / 'states.json').read_text())['steps']
        # source_step refers to the public measurement frame in these saved
        # single-decision runs. Require it, instead of substituting a new view.
        step = after['source_step']
        frame = next(s for s in frames if s['step_idx'] == step)
        if step != 0 and frame.get('command', {}).get('action') != 'v5_measurement':
            raise ValueError('refined public evidence is not a saved measurement frame')
        images = []
        destination = args.output / row['case']
        destination.mkdir()
        for view in ('agentview', 'wrist'):
            image_path = path.parent / (view + '_high.png') / f'{step:02d}.png'
            metadata_path = path.parent / (view + '_metadata.json') / f'{step:02d}.json'
            world_path = path.parent / (view + '_world_high.npz') / f'{step:02d}.npz'
            image = Image.open(image_path).convert('RGB')
            metadata = json.loads(metadata_path.read_text())
            draw = ImageDraw.Draw(image)
            for entity, colour, label in ((nearest, 'cyan', 'public cabinet'),
                                          (before, 'lime', 'initial package'),
                                          (after, 'red', 'refined package')):
                box = project_bounds(entity, metadata, image.size) if entity else None
                if box:
                    draw.rectangle(box, outline=colour, width=4)
                    draw.text((box[0]+4, box[1]+4), label, fill=colour, stroke_width=1, stroke_fill='black')
            with np.load(world_path) as data:
                world = data[data.files[0]].astype(float)
            mask = np.isfinite(world).all(axis=-1) & (
                (world >= np.array(after['lower'])-.002)
                & (world <= np.array(after['upper'])+.002)).all(axis=-1)
            points = world[mask]
            cloud_path = destination / (view + '_refined_bounds_cloud.npz')
            np.savez_compressed(cloud_path, xyz_world=points, pixel_indices=np.flatnonzero(mask))
            inside = (((points >= np.array(nearest['lower'])-.002)
                       & (points <= np.array(nearest['upper'])+.002)).all(axis=-1)
                      if nearest else None)
            item['views'].append({'camera': view, 'step': step, 'rgb': pin(image_path),
                'metadata': pin(metadata_path), 'world': pin(world_path), 'cloud': pin(cloud_path),
                'cloud_extraction': 'refined_public_bounds_region_not_original_SAM_mask',
                'points': len(points), 'points_inside_public_fixture_fraction':
                    float(inside.mean()) if inside is not None and len(inside) else None})
            image.thumbnail((640, 640))
            images.append(image)
        montage = Image.new('RGB', (sum(i.width for i in images), max(i.height for i in images)))
        left = 0
        for image in images:
            montage.paste(image, (left, 0)); left += image.width
        montage_path = destination / 'public_bounds_overlay.png'
        montage.save(montage_path)
        item['overlay'] = pin(montage_path)
        rows.append(item)
    if len(rows) != 13:
        raise ValueError('all 13 registered width anomalies required')
    ledger = args.output / 'records.jsonl'
    ledger.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    report = {'n': len(rows), 'source': pin(args.anomalies), 'producer': pin(Path(__file__)),
        'public_projector': pin(Path(project_bounds.__code__.co_filename)),
        'records': pin(ledger), 'centre_shift_over_10cm': sum(r['measured_centre_shift_m'] > .10 for r in rows),
        'refined_bound_majority_inside_measured_cabinet': sum(
            (r['refined_bound_fraction_in_fixture'] or 0) > .5 for r in rows),
        'scope': 'public measured bounds, saved RGB-D, and camera calibration; no simulator object poses',
        'limitation': 'Cabinet-region association is observable; absent historical SAM masks prevent exact segmentation contamination diagnosis.',
        'qualification_allowed': False, 'training_allowed': False}
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
