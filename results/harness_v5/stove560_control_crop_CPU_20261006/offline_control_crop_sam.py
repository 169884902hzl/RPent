"""Fixed public control crops; reuse job4240 full/body baselines without reruns."""

import argparse
import base64
from dataclasses import fields
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image

from crop_mapping import crop_rgb, mask_bbox, measured_crop_points, padded_roi


def identity(path):
    return {'path': str(path), 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def checked_file(ref):
    path = Path(ref['path'])
    if not path.is_absolute():
        raise ValueError('control crop input must be an explicit absolute file')
    if identity(path)['sha256'] != ref['sha256']:
        raise ValueError('registered public input changed: ' + str(path))
    return path


def preflight(manifest, expected_sha):
    if not manifest.is_absolute():
        raise ValueError('manifest must be absolute')
    actual = identity(manifest)
    if expected_sha is not None and actual['sha256'] != expected_sha:
        raise ValueError('registered control crop manifest changed')
    plan = json.loads(manifest.read_text())
    if (plan['version'] != 'original-stove-public-control-crop-SAM/1-dev'
            or plan['queries'] != ['stove knob', 'stove switch handle']
            or plan['minimum_score'] != .2 or plan['frames_count'] != 12
            or plan['profiles'] != ['control_crop_context25']
            or plan['control_crop_frames'] != 10 or plan['new_RPC_calls'] != 20
            or plan['context_fraction'] != .25 or plan['minimum_context_px'] != 20):
        raise ValueError('registered control crop protocol changed')
    checked = []
    for ref in plan['producers'] + plan['source_files']:
        checked.append(identity(checked_file(ref)))
    source = json.loads(checked_file(plan['source_run_manifest']).read_text())
    old = json.loads(checked_file(plan['source_offline_manifest']).read_text())
    components = json.loads(checked_file(plan['public_bbox_evidence']).read_text())
    component_by_name = {row['frame']: row for row in components['records']}
    if len(component_by_name) != 12 or len(plan['frames']) != 12 or not source['stove_control_features_v1']:
        raise ValueError('original public input count changed')
    allowed = {case['name'] for case in source['cases']}
    if [f['name'] for f in plan['frames']] != [f['name'] for f in old['frames']]:
        raise ValueError('control smoke must retain all twelve original views in order')
    for ref in plan['baseline_files'].values():
        checked.append(identity(checked_file(ref)))
    baseline = [json.loads(line) for line in Path(plan['baseline_files']['queries']['path']).read_text().splitlines()]
    expected_baseline = [(frame['name'], profile, query) for frame in old['frames']
                         for profile in ['full', 'crop_context50'] for query in plan['queries']]
    if [(row['frame'], row['profile'], row['query']) for row in baseline] != expected_baseline:
        raise ValueError('job4240 baseline rows changed')
    mapping_checks, missing, crops = 0, [], []
    for frame, original in zip(plan['frames'], old['frames']):
        if frame['case'] not in allowed or frame['camera'] not in ('agentview', 'wrist'):
            raise ValueError('control crop outside registered original tasks')
        for key in ('files', 'current_shell', 'case', 'camera', 'source_step'):
            if frame[key] != original[key]:
                raise ValueError('control crop altered original public capture')
        if frame['current_shell']['source_step'] != frame['source_step']:
            raise ValueError('coarse stove is not from this capture')
        for ref in frame['files'].values():
            checked.append(identity(checked_file(ref)))
        image = Image.open(frame['files']['rgb']['path']).convert('RGB')
        metadata = json.loads(Path(frame['files']['metadata']['path']).read_text())
        with np.load(frame['files']['world']['path'], allow_pickle=False) as archive:
            world = archive['array']
        if world.shape != (image.height, image.width, 3):
            raise ValueError('original RGB-D pixels differ')
        candidates = component_by_name[frame['name']]['thresholds']['64']
        if len(candidates) == 0:
            if frame['status'] != 'missing_control_bbox' or frame['roi_xyxy'] is not None:
                raise ValueError('missing control must not receive an invented ROI')
            missing.append(frame['name'])
            continue
        if len(candidates) != 1 or frame['status'] != 'registered_control_crop':
            raise ValueError('control crop requires one public component')
        bbox = candidates[0]['bbox_pixel_xyxy']
        expected_roi = padded_roi(bbox, image.size, fraction=.25, minimum_px=20)
        if frame['control_bbox_xyxy'] != bbox or frame['roi_xyxy'] != expected_roi:
            raise ValueError('fixed public crop differs from preregistered geometric evidence')
        x0, y0, x1, y1 = expected_roi
        if not (x0 <= bbox[0] < bbox[2] <= x1 and y0 <= bbox[1] < bbox[3] <= y1):
            raise ValueError('crop omits measured bar or base-rim component pixels')
        _, mapping = crop_rgb(np.asarray(image), metadata, expected_roi)
        points, _ = measured_crop_points(world, np.ones(tuple(reversed(mapping['crop_size'])), bool), mapping)
        portion = world[y0:y1, x0:x1]
        valid = np.isfinite(portion).all(axis=-1) & (np.abs(portion).sum(axis=-1) > 1e-6)
        if not np.array_equal(points, portion[valid]):
            raise ValueError('mask mapping altered original XYZ samples')
        mapping_checks += 1
        crops.append({'frame': frame['name'], 'control_bbox_xyxy': bbox,
                      'roi_xyxy': expected_roi, 'mapping': mapping})
    if mapping_checks != 10 or len(missing) != 2:
        raise ValueError('fixed crop and missing-view counts changed')
    for resource in plan['resources']:
        path = Path(resource['path'])
        if not path.is_absolute() or not path.exists():
            raise ValueError('missing explicit control crop resource')
    report = {'passed': True, 'manifest': actual, 'cwd': str(Path.cwd()),
              'files_checked': checked, 'frames_checked': 12, 'new_RPC_calls_planned': 20,
              'baseline_RPC_calls_reused': 48, 'baseline_files': plan['baseline_files'],
              'missing_control_bbox': missing, 'pixel_to_world_checks_passed': mapping_checks,
              'fixed_crops': crops, 'GPU_services_started': False, 'simulator_started': False,
              'private_labels_opened': False, 'endpoint_state': 'unmeasured'}
    return plan, report


def run(plan, output):
    from robots.libero.v5_fixture_parts import measured_stove_control_pose
    from robots.libero.v5_perception_geometry import same_segmented_instance
    from robots.libero.v5_state import Entity
    from rpent.robots.components.sam3_client import Sam3Client
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    output.mkdir(parents=True, exist_ok=False)
    port = pick_free_port()
    endpoint = f'http://127.0.0.1:{port}'
    daemon = ProcessDaemon(name='stove_public_control_crop_SAM',
                          cmd=[sys.executable, '-m', 'robots.libero.v5_sam3_server',
                               '--transport', 'http', '--host', '127.0.0.1', '--port', str(port), '--parent-watch'],
                          log_path=str(output / 'sam_server.log'))
    rows = []
    try:
        daemon.start()
        rpc = HttpRpcClient(endpoint)
        wait_for_ready(rpc, daemon=daemon, timeout_s=300)
        with (output / 'queries.jsonl').open('x') as ledger:
            for frame in plan['frames']:
                directory = output / frame['name']
                directory.mkdir()
                if frame['status'] == 'missing_control_bbox':
                    for query in plan['queries']:
                        row = {'frame': frame['name'], 'profile': plan['profiles'][0], 'query': query,
                               'status': 'missing_control_bbox', 'RPC_called': False,
                               'instances': [], 'source_files': frame['files'], 'endpoint_state': 'unmeasured'}
                        rows.append(row)
                        ledger.write(json.dumps(row, allow_nan=False) + '\n')
                    ledger.flush()
                    (directory / 'summary.json').write_text(json.dumps({'status': 'missing_control_bbox',
                        'endpoint_state': 'unmeasured', 'accepted_unique_control_geometries': 0}, indent=2) + '\n')
                    continue
                image = np.asarray(Image.open(frame['files']['rgb']['path']).convert('RGB'))
                metadata = json.loads(Path(frame['files']['metadata']['path']).read_text())
                with np.load(frame['files']['world']['path'], allow_pickle=False) as archive:
                    world = archive['array']
                crop, mapping = crop_rgb(image, metadata, frame['roi_xyxy'])
                stream = BytesIO()
                Image.fromarray(crop).save(stream, format='PNG')
                cropped = stream.getvalue()
                (directory / 'crop_rgb.png').write_bytes(cropped)
                (directory / 'crop_mapping.json').write_text(json.dumps(mapping, indent=2) + '\n')
                parent = Entity(**{field.name: frame['current_shell'][field.name]
                                   for field in fields(Entity) if field.name in frame['current_shell']})
                camera_xyz = np.asarray(metadata['extrinsic_cam2world'])[:3, 3]
                selected_masks = []
                for query_index, prompt in enumerate(plan['queries']):
                    row = {'frame': frame['name'], 'profile': plan['profiles'][0], 'query': prompt,
                           'minimum_score': plan['minimum_score'], 'input_rgb_sha256': hashlib.sha256(cropped).hexdigest(),
                           'source_files': frame['files'], 'roi_xyxy': frame['roi_xyxy'], 'instances': [],
                           'RPC_called': True, 'endpoint_state': 'unmeasured'}
                    started = time.perf_counter()
                    try:
                        response = rpc.call('sam3.segment_all', kwargs={'image_base64': base64.b64encode(cropped).decode('ascii'),
                                            'text_prompt': prompt, 'min_score': plan['minimum_score']}, timeout_s=120)
                        for index, item in enumerate(response.get('instances', [])):
                            decoded = Sam3Client._decode_result(item)
                            if decoded.mask is None:
                                raise ValueError('SAM returned no registered mask')
                            points, mask = measured_crop_points(world, decoded.mask, mapping)
                            pose, geometry = measured_stove_control_pose(points, parent, camera_xyz)
                            duplicate = any(same_segmented_instance(mask, prior) for prior in selected_masks)
                            if pose is not None and not duplicate:
                                selected_masks.append(mask)
                            stem = f'control_crop_q{query_index}_i{index}'
                            Image.fromarray(mask.astype(np.uint8) * 255).save(directory / (stem + '_full_mask.png'))
                            np.savez_compressed(directory / (stem + '_original_world_points.npz'), array=points)
                            row['instances'].append({'score': decoded.score, 'full_mask_bbox': mask_bbox(mask),
                                'mask_pixels': int(mask.sum()), 'original_world_points': len(points), 'pose': pose,
                                'geometry': geometry, 'duplicate_accepted_control': duplicate,
                                'mask': identity(directory / (stem + '_full_mask.png')),
                                'cloud': identity(directory / (stem + '_original_world_points.npz'))})
                        row['status'] = 'measured'
                    except Exception as error:
                        row.update(status='development_error', error=repr(error))
                    row['wall_s'] = time.perf_counter() - started
                    rows.append(row)
                    ledger.write(json.dumps(row, allow_nan=False) + '\n')
                    ledger.flush()
                    if row['status'] == 'development_error':
                        raise RuntimeError('preserved control crop SAM error; repair and rerun this command')
                (directory / 'summary.json').write_text(json.dumps({'accepted_unique_control_geometries': len(selected_masks),
                    'endpoint_state': 'unmeasured', 'directed_features_calibrated': False}, indent=2) + '\n')
        (output / 'summary.json').write_text(json.dumps({'frames': 12, 'ledger_rows': len(rows),
            'new_RPC_calls': sum(row['RPC_called'] for row in rows), 'baseline_RPC_calls_reused': 48,
            'baseline_files': plan['baseline_files'], 'queries_with_instances': sum(bool(row['instances']) for row in rows),
            'queries_with_accepted_control_geometry': sum(any(item['pose'] is not None for item in row['instances']) for row in rows),
            'missing_control_bbox_views': 2, 'endpoint_state': 'unmeasured', 'simulator_started': False,
            'private_labels_opened': False, 'qualification_authorized': False}, indent=2) + '\n')
    finally:
        daemon.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--expected-manifest-sha256')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    if not args.output.is_absolute():
        parser.error('output must be absolute')
    plan, report = preflight(args.manifest, args.expected_manifest_sha256)
    if args.preflight_only:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'passed': True, 'frames_checked': 12, 'new_RPC_calls_planned': 20,
                          'baseline_RPC_calls_reused': 48, 'missing_views': 2, 'GPU_services_started': False}))
    else:
        run(plan, args.output)


if __name__ == '__main__':
    main()
