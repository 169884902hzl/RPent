"""Pinned public-frame full/crop SAM recheck; no environment or private labels."""

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

from crop_mapping import crop_rgb, measured_crop_points, mask_bbox


def identity(path):
    return {'path': str(path), 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def checked_file(ref):
    path = Path(ref['path'])
    if not path.is_absolute():
        raise ValueError('offline crop inputs must be absolute')
    actual = identity(path)
    if actual['sha256'] != ref['sha256']:
        raise ValueError('registered public crop input changed: ' + str(path))
    return path


def preflight(manifest, expected_sha):
    if not manifest.is_absolute():
        raise ValueError('manifest must be absolute')
    actual = identity(manifest)
    if expected_sha is not None and actual['sha256'] != expected_sha:
        raise ValueError('registered offline crop manifest changed')
    plan = json.loads(manifest.read_text())
    if (plan['version'] != 'original-stove-public-crop-SAM/1-dev'
            or plan['queries'] != ['stove knob', 'stove switch handle']
            or plan['minimum_score'] != .2 or plan['frames_count'] != 12
            or plan['profiles'] != ['full', 'crop_context50']):
        raise ValueError('registered paired offline crop protocol changed')
    checked = []
    for ref in plan['producers'] + plan['source_files']:
        checked.append(identity(checked_file(ref)))
    source_manifest = checked_file(plan['source_run_manifest'])
    source_plan = json.loads(source_manifest.read_text())
    allowed = {case['name'] for case in source_plan['cases']}
    assert len(plan['frames']) == 12 and source_plan['stove_control_features_v1']
    for frame in plan['frames']:
        if frame['case'] not in allowed or frame['camera'] not in ('agentview', 'wrist'):
            raise ValueError('offline crop frame is outside explicit original measurement run')
        for ref in frame['files'].values(): checked.append(identity(checked_file(ref)))
        if frame['current_shell']['source_step'] != frame['source_step']:
            raise ValueError('offline coarse stove must have current same-capture measurement')
        rgb = Image.open(frame['files']['rgb']['path']).convert('RGB')
        metadata = json.loads(Path(frame['files']['metadata']['path']).read_text())
        with np.load(frame['files']['world']['path'], allow_pickle=False) as archive: world = archive['array']
        if world.shape != (rgb.height, rgb.width, 3):
            raise ValueError('offline crop RGB-D pixels differ')
        _, mapping = crop_rgb(np.asarray(rgb), metadata, frame['roi_xyxy'])
        points, _ = measured_crop_points(world, np.ones(tuple(reversed(mapping['crop_size'])), bool), mapping)
        x0,y0,x1,y1=frame['roi_xyxy']; portion=world[y0:y1,x0:x1]
        valid=np.isfinite(portion).all(axis=-1)&(np.abs(portion).sum(axis=-1)>1e-6)
        if not np.array_equal(points,portion[valid]):
            raise ValueError('crop mask mapping changed original XYZ samples')
    for resource in plan['resources']:
        path=Path(resource['path'])
        if not path.is_absolute() or not path.exists():raise ValueError('missing explicit crop resource')
    return plan, {'passed': True, 'manifest': actual, 'cwd': str(Path.cwd()), 'files_checked': checked,
                  'frames_checked': 12, 'paired_query_calls_planned': 48, 'pixel_to_world_checks_passed':12,
                  'GPU_services_started':False,'simulator_started':False,'private_labels_opened':False}


def run(plan, output):
    from robots.libero.v5_fixture_parts import measured_stove_control_pose
    from robots.libero.v5_perception_geometry import same_segmented_instance
    from robots.libero.v5_state import Entity
    from rpent.robots.components.sam3_client import Sam3Client
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    output.mkdir(parents=True,exist_ok=False)
    port=pick_free_port();endpoint=f'http://127.0.0.1:{port}'
    daemon=ProcessDaemon(name='stove_public_crop_SAM',cmd=[sys.executable,'-m','robots.libero.v5_sam3_server',
        '--transport','http','--host','127.0.0.1','--port',str(port),'--parent-watch'],log_path=str(output/'sam_server.log'))
    rows=[]
    try:
        daemon.start();rpc=HttpRpcClient(endpoint);wait_for_ready(rpc,daemon=daemon,timeout_s=300)
        with (output/'queries.jsonl').open('x') as ledger:
            for frame in plan['frames']:
                directory=output/frame['name'];directory.mkdir()
                original=Path(frame['files']['rgb']['path']).read_bytes()
                image=np.asarray(Image.open(BytesIO(original)).convert('RGB'))
                metadata=json.loads(Path(frame['files']['metadata']['path']).read_text())
                with np.load(frame['files']['world']['path'],allow_pickle=False) as archive:world=archive['array']
                crop,mapping=crop_rgb(image,metadata,frame['roi_xyxy'])
                stream=BytesIO();Image.fromarray(crop).save(stream,format='PNG')
                cropped=stream.getvalue();(directory/'crop_rgb.png').write_bytes(cropped)
                (directory/'crop_mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
                parent=Entity(**{field.name:frame['current_shell'][field.name] for field in fields(Entity) if field.name in frame['current_shell']})
                camera_xyz=np.asarray(metadata['extrinsic_cam2world'])[:3,3]
                for profile,png in [('full',original),('crop_context50',cropped)]:
                    selected_masks=[]
                    for query_index,prompt in enumerate(plan['queries']):
                        row={'frame':frame['name'],'profile':profile,'query':prompt,'minimum_score':plan['minimum_score'],
                             'input_rgb_sha256':hashlib.sha256(png).hexdigest(),'source_files':frame['files'],'instances':[]}
                        started=time.perf_counter()
                        try:
                            response=rpc.call('sam3.segment_all',kwargs={'image_base64':base64.b64encode(png).decode('ascii'),
                                'text_prompt':prompt,'min_score':plan['minimum_score']},timeout_s=120)
                            for idx,item in enumerate(response.get('instances',[])):
                                decoded=Sam3Client._decode_result(item)
                                if decoded.mask is None:raise ValueError('SAM returned no registered mask')
                                if profile=='crop_context50':points,mask=measured_crop_points(world,decoded.mask,mapping)
                                else:
                                    mask=decoded.mask
                                    if mask.shape!=image.shape[:2]:raise ValueError('SAM full-frame mask shape changed')
                                    valid=np.isfinite(world).all(axis=-1)&(np.abs(world).sum(axis=-1)>1e-6)
                                    points=world[mask&valid]
                                pose,geometry=measured_stove_control_pose(points,parent,camera_xyz)
                                duplicate=any(same_segmented_instance(mask,prior) for prior in selected_masks)
                                if pose is not None and not duplicate:selected_masks.append(mask)
                                stem=f'{profile}_q{query_index}_i{idx}'
                                Image.fromarray(mask.astype(np.uint8)*255).save(directory/(stem+'_full_mask.png'))
                                np.savez_compressed(directory/(stem+'_original_world_points.npz'),array=points)
                                row['instances'].append({'score':decoded.score,'full_mask_bbox':mask_bbox(mask),
                                    'mask_pixels':int(mask.sum()),'original_world_points':len(points),'pose':pose,
                                    'geometry':geometry,'duplicate_accepted_control':duplicate,
                                    'mask':identity(directory/(stem+'_full_mask.png')),
                                    'cloud':identity(directory/(stem+'_original_world_points.npz'))})
                            row['status']='measured'
                        except Exception as error:
                            row.update(status='development_error',error=repr(error))
                        row['wall_s']=time.perf_counter()-started;rows.append(row)
                        ledger.write(json.dumps(row,allow_nan=False)+'\n');ledger.flush()
                        if row['status']=='development_error':raise RuntimeError('preserved offline SAM error; repair this command')
                    (directory/(profile+'_summary.json')).write_text(json.dumps({'accepted_unique_control_geometries':len(selected_masks),
                        'endpoint_state':'unmeasured','directed_features_calibrated':False},indent=2)+'\n')
        counts={profile:sum(any(item['pose'] is not None for item in row['instances']) for row in rows if row['profile']==profile)
                for profile in plan['profiles']}
        (output/'summary.json').write_text(json.dumps({'paired_query_calls':len(rows),'queries_with_accepted_control_geometry':counts,
            'simulator_started':False,'private_labels_opened':False,'qualification_authorized':False},indent=2)+'\n')
    finally:daemon.stop()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--expected-manifest-sha256');parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preflight-only',action='store_true');args=parser.parse_args()
    if not args.output.is_absolute():parser.error('output must be absolute')
    plan,report=preflight(args.manifest,args.expected_manifest_sha256)
    if args.preflight_only:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'passed':True,'frames_checked':12,'paired_query_calls_planned':48,'GPU_services_started':False}))
    else:run(plan,args.output)


if __name__=='__main__':main()
