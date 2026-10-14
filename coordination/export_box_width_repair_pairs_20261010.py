"""Account for all 13 old width failures using fresh, preserved public masks."""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = ROOT / 'coordination/box_width_repair_pairs_20261010_r1'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def load_array(path):
    with np.load(path) as archive:
        if len(archive.files) != 1:
            raise ValueError(f'expected one preserved array: {path}')
        return archive[archive.files[0]]


def measured_widths(points, axis):
    points = np.asarray(points, dtype=float)
    points = points[np.isfinite(points).all(axis=1)]
    if len(points) < 30:
        return {'points': len(points), 'width_unmeasured': True}
    bounds = np.quantile(points, (.02, .98), axis=0)
    _, axes = np.linalg.eigh(np.cov(points[:, :2].T))
    projections = points[:, :2] @ axes
    widths = np.diff(np.quantile(projections, (.02, .98), axis=0), axis=0)[0]
    result = {'points': len(points), 'world_AABB_xy_narrow_m': float(min(bounds[1, :2] - bounds[0, :2])),
              'PCA_xy_widths_m': widths.tolist(), 'PCA_xy_narrow_m': float(min(widths))}
    if axis is not None:
        p = points[:, :2] @ np.asarray(axis)
        result['current_grasp_axis_width_m'] = float(np.diff(np.quantile(p, (.02, .98)))[0])
    return result


def main():
    old_path = ROOT / 'coordination/r14_box_component_diagnosis_20261010_r1/records.jsonl'
    new_path = ROOT / 'coordination/geometric_grasp_second_round_r4_closed_20261010_r2/rows.jsonl'
    plan_path = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r4/box_depth_identity_cleanup/preparation/selection.json'
    plan = json.loads(plan_path.read_text())
    geometry = Path(plan['source_path']) / 'robots/libero/v5_grasp_geometry.py'
    expected = next(item['sha256'] for item in plan['source_snapshot']['files']
                    if item['relative_path'] == 'robots/libero/v5_grasp_geometry.py')
    if pin(geometry)['sha256'] != expected:
        raise ValueError('registered public geometry source changed')
    spec = importlib.util.spec_from_file_location('registered_public_grasp_geometry', geometry)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clean_object_mask = module.clean_object_mask
    old = [json.loads(line) for line in old_path.open()]
    new = {row['baseline_case']: row for row in map(json.loads, new_path.open())
           if row['group'].endswith('/box_depth_identity_cleanup')}
    if len(old) != 13:
        raise ValueError('all 13 registered old width failures are required')
    OUT.mkdir(exist_ok=False)
    rows = []
    for prior in old:
        row = new[prior['case']]
        if row['state_sha256'] != prior['state_sha256']:
            raise ValueError('paired initial-state bytes differ')
        ledger = ROOT / row['input']
        if pin(ledger)['sha256'] != row['input_sha256']:
            raise ValueError('physical ledger changed')
        raw = json.loads(ledger.read_text().splitlines()[row['line']-1])
        first, directory = raw['first_attempt'], Path(raw['output_dir'])
        receipt = first['receipt']
        plan = receipt.get('analytic_grasp_plan') or {}
        entity = next(e for e in first['public_before']['entities'] if e['id'] == receipt['object'])
        dest = OUT / str(row['layout_seed'])
        dest.mkdir()
        views = []
        for camera, masks in receipt.get('precontact_identity', {}).get('matched_sam_mask_files', {}).items():
            for index, saved in enumerate(masks):
                mask_path = Path(saved['path'])
                if pin(mask_path)['sha256'] != saved['sha256']:
                    raise ValueError('preserved SAM mask changed')
                world_path = directory / (camera + '_world_high.npz') / mask_path.name
                world = load_array(world_path).astype(float)
                mask = load_array(mask_path).astype(bool)
                if world.shape[:2] != mask.shape:
                    raise ValueError('mask and depth must refer to the same view and frame')
                cleaned, components = clean_object_mask(world, mask,
                    prior_lower=entity['lower'], prior_upper=entity['upper'])
                cloud_path = dest / f'{camera}_{index}_public_points.npz'
                np.savez_compressed(cloud_path, raw=world[mask], cleaned=world[cleaned])
                views.append({'camera': camera, 'source_step': saved['source_step'],
                    'mask': pin(mask_path), 'world': pin(world_path), 'export': pin(cloud_path),
                    'components': components,
                    'raw': measured_widths(world[mask], plan.get('closing_axis_xy')),
                    'cleaned': measured_widths(world[cleaned], plan.get('closing_axis_xy'))})
        targets = []
        for path in sorted((directory / ('analytic_target_' + entity['id'] + '.npz')).glob('*.npz')):
            points = load_array(path)
            copy = dest / ('fused_target_' + path.name)
            np.savez_compressed(copy, points=points)
            targets.append({'input': pin(path), 'export': pin(copy),
                            **measured_widths(points, plan.get('closing_axis_xy'))})
        rows.append({'baseline_case': prior['case'], 'state_sha256': row['state_sha256'],
            'old_planned_width_m': prior['refined_planned_width_m'],
            'new_planned_width_m': plan.get('measured_width_m'),
            'old_mask_available': False, 'old_exact_contamination_source': 'unrecoverable',
            'new_failure_reason': row['failure_reason'], 'registered_v3': row['registered_v3'],
            'public_verified': row['public'], 'current_public_entity': entity,
            'new_plan': plan, 'views': views, 'targets': targets,
            'physical_record': {**pin(ledger), 'line': row['line']}, 'training_allowed': False})
    records = OUT / 'records.jsonl'
    records.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    manifest = {'records': pin(records), 'producer': pin(Path(__file__)),
        'inputs': [pin(old_path), pin(new_path), pin(plan_path), pin(geometry)], 'n': len(rows),
        'width_over_72mm': sum((r['new_planned_width_m'] or 0) >= .072 for r in rows),
        'geometry_unmeasured': sum(r['new_planned_width_m'] is None for r in rows),
        'v3_success': sum(r['registered_v3'] is True for r in rows),
        'limits': ['New masks are from a fresh same-state replay, not recovered old SAM masks.',
                   'World AABB, PCA footprint and closing-axis widths are reported separately.',
                   'No simulator object positions or contact labels drive these public-cloud measurements.'],
        'training_allowed': False, 'qualification_allowed': False}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
