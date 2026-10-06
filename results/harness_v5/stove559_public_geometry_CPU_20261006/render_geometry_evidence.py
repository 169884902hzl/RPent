"""Display only measured public control/body geometry and paired stability."""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import ConvexHull

from inspect_dark_components import local_ref, PRIOR, OUTPUT


def project(points, metadata, image_size):
    points=np.atleast_2d(points)
    transform=np.asarray(metadata['extrinsic_cam2world'],float)
    intrinsic=np.asarray(metadata['intrinsic_K'],float).copy()
    intrinsic[0]*=image_size[0]/metadata['width'];intrinsic[1]*=image_size[1]/metadata['height']
    camera=(np.column_stack([points,np.ones(len(points))])@np.linalg.inv(transform).T)[:,:3]
    homogeneous=camera@intrinsic.T
    pixels=homogeneous[:,:2]/homogeneous[:,2:]
    return [tuple(map(float,p)) if c[2]>1e-5 and np.isfinite(p).all() else None for p,c in zip(pixels,camera)]


def main():
    plan=json.loads((PRIOR/'offline_crop_sam_manifest.json').read_text())
    frames={f['name']:f for f in plan['frames']}
    parts=json.loads((OUTPUT/'full_frame/public_control_parts.json').read_text())
    edge_report=json.loads((OUTPUT/'public_shell_reference.json').read_text())
    edges={r['capture']:r for r in edge_report['records']}
    selected=json.loads((PRIOR/'selected_public_views_remote.json').read_text())
    original={f'{c["case"]}_{c["phase"]}_{c["stage"]}':c for c in selected['selected_public_views']}
    panels,rows=[],[]
    for record in parts['records']:
        frame=frames[record['frame']];camera=frame['camera'];capture=record['frame'].removesuffix('_'+camera)
        image=Image.open(local_ref(frame['files']['rgb'])).convert('RGB');rgb=np.asarray(image)
        metadata=json.loads(local_ref(frame['files']['metadata']).read_text())
        with np.load(local_ref(frame['files']['world']),allow_pickle=False) as archive:world=archive['array']
        fits=record['profiles']['64'];draw=ImageDraw.Draw(image)
        fixed=edges[capture]['results'][camera]
        row={'frame':record['frame'],'source_step':frame['source_step'],'public_inputs':frame['files'],
             'control_components_RGBmax64':len(fits),'candidate_signed_angle_to_measured_edge_deg':fixed.get('candidate_signed_angle_to_measured_edge_deg'),
             'fixed_reference':fixed,'threshold_stability':{},'endpoint_state':'unmeasured'}
        display=list(frame['roi_xyxy'])
        for profile,variants in record['profiles'].items():
            row['threshold_stability'][profile]=[{'base_supported':bool(v['base'] and v['base']['base_fit_supported']),
                'directed':v['directed_angle_measured'],'angle_to_body_centre_deg':v['candidate_signed_angle_deg'],
                'base_centre_xy':None if v['base'] is None else v['base']['centre_xy_m'],
                'radius_m':None if v['base'] is None else v['base']['radius_m'],'reason':v['reason']} for v in variants]
        if len(fits)==1:
            fit=fits[0];component=fit['component'];box=component['bbox_pixel_xyxy']
            display=[min(display[0],max(0,box[0]-20)),min(display[1],max(0,box[1]-20)),
                     max(display[2],min(image.width,box[2]+20)),max(display[3],min(image.height,box[3]+20))]
            draw.rectangle(box,outline='lime',width=2)
            shell=frame['current_shell'];lo,hi=np.asarray(shell['lower']),np.asarray(shell['upper'])
            gap=np.maximum(0,np.maximum(lo-world,world-hi))
            search=np.isfinite(world).all(axis=-1)&(np.abs(world).sum(axis=-1)>1e-6)&(np.linalg.norm(gap,axis=-1)<=.15)
            search&=(world[...,2]>=hi[2]-.015)&(world[...,2]<=hi[2]+.08)
            search&=~((world[...,:2]>=lo[:2])&(world[...,:2]<=hi[:2])).all(axis=-1)
            labels,_=ndimage.label((rgb.max(axis=-1)<=64)&search)
            cloud=np.unique(world[labels==component['label']].astype(float),axis=0)
            boundary=cloud[ConvexHull(cloud[:,:2]).vertices]
            if fit['base']:
                base=fit['base'];pivot=np.asarray(base['centre_xy_m']);radius=base['radius_m']
                supported=boundary[np.abs(np.linalg.norm(boundary[:,:2]-pivot,axis=1)-radius)<=.0025]
                for pixel in project(supported,metadata,image.size):
                    if pixel:draw.ellipse((pixel[0]-2,pixel[1]-2,pixel[0]+2,pixel[1]+2),fill='cyan')
            lever=fit['lever'];top=cloud[cloud[:,2]>=lever['upper_patch_z_min_m']]
            centre=np.asarray(lever['upper_patch_centre_xyz_m']);axis=np.asarray(lever['undirected_axis_xy'])
            if fit['directed_angle_measured']:axis=np.asarray(lever['directed_axis_xy'])
            along=(top[:,:2]-centre[:2])@axis;ends=np.quantile(along,[.02,.98])
            vertices=np.array([centre+np.r_[axis*ends[0],0],centre+np.r_[axis*ends[1],0]])
            points=project(vertices,metadata,image.size)
            if all(p is not None for p in points):
                draw.line(points,fill='orange',width=4)
                if fit['directed_angle_measured']:
                    end=np.asarray(points[1]);start=np.asarray(points[0]);direction=end-start;direction/=np.linalg.norm(direction)
                    tangent=np.array([-direction[1],direction[0]])
                    draw.polygon([tuple(end),tuple(end-direction*12+tangent*6),tuple(end-direction*12-tangent*6)],fill='orange')
            row['base']=fit['base'];row['lever']=fit['lever']
            capture_original=original[capture];shell_view=capture_original['views']['agentview']
            shell_instances=[i for q in shell_view['queries'] if q['feature_role']=='shell' for i in q['instances']]
            if fixed.get('measured_body_reference') and len(shell_instances)==1:
                mask=np.asarray(Image.open(local_ref(shell_instances[0]['mask'])))>0
                with np.load(local_ref(shell_view['files']['world']),allow_pickle=False) as archive:bodyworld=archive['array']
                bodypoints=bodyworld[mask].astype(float);reference=fixed['measured_body_reference']
                vertices=[]
                for endpoint in (reference['start_xy_m'],reference['end_xy_m']):
                    distance=np.linalg.norm(bodypoints[:,:2]-endpoint,axis=1)
                    nearest=bodypoints[distance<=distance.min()+1e-6]
                    vertices.append(nearest[np.argmax(nearest[:,2])])
                points=project(np.asarray(vertices),metadata,image.size)
                if all(p is not None for p in points):draw.line(points,fill='yellow',width=4)
        crop=image.crop(tuple(display));crop.thumbnail((512,390))
        tile=Image.new('RGB',(512,460),'white');tile.paste(crop,(0,0))
        angle=row['candidate_signed_angle_to_measured_edge_deg'];description='unknown' if angle is None else f'candidate angle {angle:.2f} deg'
        ImageDraw.Draw(tile).multiline_text((5,393),record['frame']+'\n'+description+'; endpoint unmeasured\ncyan=observed base rim; orange=upper patch; yellow=measured shell edge',fill='black',spacing=3)
        panels.append(tile);rows.append(row)
    montage=Image.new('RGB',(1024,460*((len(panels)+1)//2)),'white')
    for i,panel in enumerate(panels):montage.paste(panel,((i%2)*512,(i//2)*460))
    montage.save(OUTPUT/'public_geometry_montage.png')
    paired=[]
    for capture,record in edges.items():
        first,second=[record['results'][c].get('candidate_signed_angle_to_measured_edge_deg') for c in ('agentview','wrist')]
        if first is not None and second is not None:
            difference=abs((first-second+180)%360-180)
            paired.append({'capture':capture,'primary_deg':first,'wrist_deg':second,'absolute_wrapped_difference_deg':difference})
    result={'records':rows,'paired_angles':paired,'views':len(rows),'baseline_geometric_angles':sum(r['candidate_signed_angle_to_measured_edge_deg'] is not None for r in rows),
        'scope':'saved original views only; not semantic truth or qualification','private_labels_opened':False,'GPU_started':False,
        'simulator_started':False,'runtime_changed':False,'on_off_endpoints_calibrated':False,
        'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUTPUT/'geometry_evidence.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'baseline_geometric_angles':result['baseline_geometric_angles'],'paired_angles':paired}))


if __name__=='__main__':main()
