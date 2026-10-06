"""Measure a fixed shell edge from existing SAM/depth; never endpoint labels."""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import ConvexHull

from inspect_dark_components import local_ref, PRIOR, OUTPUT


def shell_edges(cloud, pivot):
    xy=np.unique(cloud[:,:2],axis=0)
    boundary=xy[ConvexHull(xy).vertices]
    centre=np.median(cloud,axis=0)[:2]
    edges=[]
    for index,start in enumerate(boundary):
        end=boundary[(index+1)%len(boundary)];vector=end-start;length=np.linalg.norm(vector)
        if length<.06:continue
        tangent=vector/length;normal=np.array([-tangent[1],tangent[0]])
        midpoint=(start+end)/2
        if normal@(centre-midpoint)<0:normal=-normal
        along=float((pivot-start)@tangent)
        if not -.01<=along<=length+.01:continue
        distance=abs(float((pivot-start)@normal))
        edges.append({'start_xy_m':start.tolist(),'end_xy_m':end.tolist(),'length_m':float(length),
            'normal_towards_measured_body_xy':normal.tolist(),'pivot_distance_m':distance,
            'pivot_projected_segment_fraction':along/length})
    edges.sort(key=lambda edge:edge['pivot_distance_m'])
    return edges


def main():
    selected_path=PRIOR/'selected_public_views_remote.json'
    selected=json.loads(selected_path.read_text())
    parts_path=OUTPUT/'full_frame/public_control_parts.json'
    parts=json.loads(parts_path.read_text());by_name={f['frame']:f for f in parts['records']}
    records=[]
    for capture in selected['selected_public_views']:
        view=capture['views']['agentview']
        instances=[i for q in view['queries'] if q['feature_role']=='shell' for i in q['instances']]
        if len(instances)!=1:continue
        mask_ref=instances[0]['mask'];mask=np.asarray(Image.open(local_ref(mask_ref)))>0
        with np.load(local_ref(view['files']['world']),allow_pickle=False) as archive:world=archive['array']
        valid=np.isfinite(world).all(axis=-1)&(np.abs(world).sum(axis=-1)>1e-6)
        cloud=world[mask&valid].astype(float)
        capture_key=f'{capture["case"]}_{capture["phase"]}_{capture["stage"]}'
        row={'capture':capture_key,'source_step':capture['source_step'],
             'shell_mask':mask_ref,'shell_world':view['files']['world'],'results':{}}
        for camera in ('agentview','wrist'):
            frame=by_name[capture_key+'_'+camera]
            fits=frame['profiles']['64']
            if len(fits)!=1 or not fits[0]['base'] or not fits[0]['base']['base_fit_supported']:
                row['results'][camera]={'reason':'unique_supported_public_control_base_missing'};continue
            fit=fits[0];pivot=np.asarray(fit['base']['centre_xy_m']);edges=shell_edges(cloud,pivot)
            result={'fixed_edge_candidates':edges,'same_capture':frame['source_step']==capture['source_step'],
                    'independent_public_shell_edge_measured':len(edges)==1 or (len(edges)>1 and edges[1]['pivot_distance_m']-edges[0]['pivot_distance_m']>.01),
                    'endpoint_state':'unmeasured'}
            if result['independent_public_shell_edge_measured'] and fit['directed_angle_measured']:
                reference=np.asarray(edges[0]['normal_towards_measured_body_xy']);direction=np.asarray(fit['lever']['directed_axis_xy'])
                result.update(candidate_signed_angle_to_measured_edge_deg=float(np.degrees(np.arctan2(np.cross(reference,direction),reference@direction))),
                    measured_body_reference=edges[0],directed_axis_xy=direction.tolist())
            else:result['reason']='fixed_edge_or_directed_lever_not_measured'
            row['results'][camera]=result
        records.append(row)
    report={'selected_public_views_sha256':hashlib.sha256(selected_path.read_bytes()).hexdigest(),
            'public_parts_sha256':hashlib.sha256(parts_path.read_bytes()).hexdigest(),
            'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'records':records,
            'private_labels_opened':False,'GPU_started':False,'simulator_started':False,'runtime_changed':False,
            'calibrated_on_off_endpoints':False,'qualification_authorized':False}
    (OUTPUT/'public_shell_reference.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({r['capture']:{c:{k:v for k,v in a.items() if k!='fixed_edge_candidates'} for c,a in r['results'].items()} for r in records}))


if __name__=='__main__':main()
