"""Trace saved public identity jumps; export measured RGB-D bounds without truth."""
import hashlib
import json
import math
from pathlib import Path
from collections import Counter
import numpy as np

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = ROOT / 'coordination/r14_public_geometry_anomalies_20261010_r2'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    records = json.loads((ROOT / 'coordination/grasp_anomalies_r14_20261010.json').read_text())
    OUT.mkdir(exist_ok=False)
    rows = []
    for group, inputs in records.items():
        for input_row in inputs:
            directory = Path(input_row['output_dir'])
            path = directory / 'choices.jsonl'
            choices = [json.loads(l) for l in path.open() if l.strip()]
            if not choices:
                rows.append({'case': input_row['case'], 'category': group, 'input': pin(path),
                             'status': 'no_executed_choice', 'training_allowed': False})
                continue
            choice = choices[-1]
            receipt = choice['receipt']
            before = choice.get('public_before', {}).get('entities', [])
            after = choice.get('public_after', {}).get('entities', [])
            oid = receipt['object']
            obj = next((e for e in before if e['id'] == oid), None)
            final = next((e for e in after if e['id'] == oid), None)
            plan = receipt.get('analytic_grasp_plan', {})
            xyz = plan.get('xyz')
            peers = [e for e in before if obj and e['name'] == obj['name']]
            distances = sorted(({'entity': e['id'], 'distance_m': math.dist(xyz[:2], e['xyz'][:2]),
                                 'xyz': e['xyz'], 'lower': e['lower'], 'upper': e['upper']}
                                for e in peers), key=lambda e: e['distance_m']) if xyz else []
            detail = {'case': input_row['case'], 'category': group, 'state_sha256': input_row['state_sha256'],
                'baseline_method': input_row['method'], 'input': pin(path), 'plan': plan,
                'selected_entity_before': obj, 'same_id_after': final,
                'grasp_point_distance_to_same_category_before': distances,
                'original_metric_outside_initial_bbox_m': input_row.get('precontact_plan_outside_original_measured_xy_m'),
                'private_pose_used': False, 'training_allowed': False}
            if group == 'box':
                case_out = OUT / input_row['case']
                case_out.mkdir()
                states = json.loads((directory / 'states.json').read_text())['steps']
                step = obj.get('source_step', obj.get('step', 0))
                frame = next(s for s in states if s['step_idx'] == step)
                world_records = []
                # Old runs did not persist SAM masks. Export public points in
                # the recorded bounds, retaining that reconstruction limitation.
                bound = obj
                for camera in ('agentview', 'wrist'):
                    folder = directory / (camera + '_world_high.npz')
                    candidates = sorted(folder.glob('*')) if folder.is_dir() else [folder]
                    candidates = [p for p in candidates if p.is_file()]
                    if not candidates or bound is None:
                        continue
                    indexed = [p for p in candidates if p.stem.isdigit() and int(p.stem) == step]
                    source = indexed[0] if indexed else candidates[min(step, len(candidates) - 1)]
                    with np.load(source) as payload:
                        world = payload[payload.files[0]]
                    lo, hi = np.asarray(bound['lower']), np.asarray(bound['upper'])
                    flat = world.reshape(-1, 3)
                    mask = np.isfinite(flat).all(axis=1) & ((flat >= lo - .005) & (flat <= hi + .005)).all(axis=1)
                    output = case_out / (camera + '_public_bbox_cloud.npz')
                    np.savez_compressed(output, xyz_world=flat[mask], pixel_indices=np.flatnonzero(mask))
                    world_records.append({'camera': camera, 'frame': step, 'world_input': pin(source),
                        'cloud': pin(output), 'points': int(mask.sum()), 'bounds': bound,
                        'extraction': 'recorded_public_bbox_not_original_sam_mask'})
                detail.update(public_clouds=world_records, original_sam_mask_saved=False,
                    exact_original_mask_recoverable=False, frame_record=frame)
            rows.append(detail)
    ledger = OUT / 'records.jsonl'
    ledger.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    cup = [r for r in rows if r['category'] == 'cup' and r.get('grasp_point_distance_to_same_category_before')]
    swaps = [r for r in cup if r['grasp_point_distance_to_same_category_before'][0]['entity'] != r['selected_entity_before']['id']]
    summary = {'counts': dict(Counter(r['category'] for r in rows)), 'cup_plan_nearest_other_known_identity': len(swaps),
        'cup_evaluable': len(cup), 'identity_swap_cases': [r['case'] for r in swaps],
        'box_cloud_limitation': 'Original SAM masks absent; exported bounds clouds are explicitly reconstructed.',
        'records': pin(ledger), 'producer': pin(Path(__file__)), 'private_pose_used': False,
        'selection_only': True, 'training_allowed': False}
    (OUT / 'manifest.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
