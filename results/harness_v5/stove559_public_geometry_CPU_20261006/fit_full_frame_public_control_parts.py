"""Saved original RGB-D disk/raised-handle geometry; endpoints stay unknown."""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import ConvexHull

from inspect_dark_components import local_ref, PRIOR
OUTPUT = Path(__file__).resolve().parent / 'full_frame'


def circle_fit(boundary):
    if len(boundary) < 8: return None
    rng = np.random.default_rng(0)
    best = None
    for indices in rng.integers(0, len(boundary), (600, 3)):
        q = boundary[indices]
        matrix = 2 * (q[1:] - q[0])
        if abs(np.linalg.det(matrix)) < 1e-8: continue
        centre = np.linalg.solve(matrix, (q[1:]**2).sum(axis=1) - (q[0]**2).sum())
        radius = np.linalg.norm(q[0] - centre)
        if not .015 <= radius <= .065:continue
        residual = np.abs(np.linalg.norm(boundary-centre, axis=1)-radius)
        inliers = residual <= .0025
        score = (int(inliers.sum()), -float(np.mean(residual[inliers])))
        if best is None or score > best[0]:best = (score,inliers)
    if best is None or best[0][0] < 8:return None
    selected = boundary[best[1]]
    def solve(points):
        a = np.column_stack([2*points, np.ones(len(points))])
        values = np.linalg.lstsq(a, (points**2).sum(axis=1), rcond=None)[0]
        return values[:2], float(np.sqrt(max(0,values[2]+(values[:2]**2).sum())))
    centre, radius = solve(selected)
    angles = np.sort(np.arctan2(selected[:,1]-centre[1],selected[:,0]-centre[0]) % (2*np.pi))
    gaps = np.diff(np.r_[angles,angles[0]+2*np.pi])
    coverage = float(360-np.degrees(gaps.max()))
    boot = np.array([solve(selected[rng.integers(0,len(selected),len(selected))])[0] for _ in range(100)])
    return {'centre_xy_m':centre.tolist(),'radius_m':radius,'boundary_points':len(boundary),
            'boundary_inliers':len(selected),'inlier_fraction':len(selected)/len(boundary),
            'observed_arc_coverage_deg':coverage,
            'boundary_radial_residual_p90_m':float(np.quantile(np.abs(np.linalg.norm(selected-centre,axis=1)-radius),.9)),
            'bootstrap_centre_sigma_xy_m':np.std(boot,axis=0).tolist(),
            'base_fit_supported':bool(coverage>=180 and len(selected)/len(boundary)>=.6)}


def main():
    report_path = OUTPUT/'dark_components.json'
    reports = json.loads(report_path.read_text())
    plan = json.loads((PRIOR/'offline_crop_sam_manifest.json').read_text())
    by_name = {f['name']:f for f in plan['frames']}
    rows = []
    for record in reports['records']:
        frame = by_name[record['frame']]
        rgb = np.asarray(Image.open(local_ref(frame['files']['rgb'])).convert('RGB'))
        with np.load(local_ref(frame['files']['world']),allow_pickle=False) as archive:world=archive['array']
        shell=frame['current_shell'];lo,hi=np.asarray(shell['lower']),np.asarray(shell['upper'])
        gap=np.maximum(0,np.maximum(lo-world,world-hi))
        valid=np.isfinite(world).all(axis=-1)&(np.abs(world).sum(axis=-1)>1e-6)
        search=valid&(np.linalg.norm(gap,axis=-1)<=.15)
        search &= (world[...,2]>=hi[2]-.015)&(world[...,2]<=hi[2]+.08)
        search &= ~((world[...,:2]>=lo[:2])&(world[...,:2]<=hi[:2])).all(axis=-1)
        roi=np.ones(rgb.shape[:2],bool)
        row={'frame':record['frame'],'camera':record['camera'],'source_step':record['source_step'],'profiles':{},
             'endpoint_state':'unmeasured','fixed_reference_basis':'current measured shell AABB centre, not a detected front edge'}
        for threshold in (40,64,80):
            labels,_=ndimage.label((rgb.max(axis=-1)<=threshold)&search&roi)
            fits=[]
            for component in record['thresholds'][str(threshold)]:
                cloud=np.unique(world[labels==component['label']].astype(float),axis=0)
                if len(cloud)<30:continue
                boundary=cloud[ConvexHull(cloud[:,:2]).vertices,:2]
                base=circle_fit(boundary)
                top_min=float(np.quantile(cloud[:,2],.95)-.004)
                top=cloud[cloud[:,2]>=top_min]
                centre=np.median(top,axis=0)
                _,singular,axes=np.linalg.svd(top-centre,full_matrices=False)
                axis=axes[0,:2];axis=axis/np.linalg.norm(axis)
                normal=axes[-1]
                residual=float(np.quantile(np.abs((top-centre)@normal),.9))
                elongation=float(singular[0]/max(singular[1],1e-12))
                lever={'upper_patch_z_min_m':top_min,'upper_patch_points':len(top),
                    'upper_patch_centre_xyz_m':centre.tolist(),'undirected_axis_xy':axis.tolist(),
                    'axis_angle_deg_mod180':float(np.degrees(np.arctan2(axis[1],axis[0]))%180),
                    'elongation_ratio':elongation,'plane_residual_p90_m':residual,
                    'normal_vertical_cosine':float(abs(normal[2]))}
                directed=False;reason='base_circle_not_supported';angle=None
                if base and base['base_fit_supported']:
                    pivot=np.asarray(base['centre_xy_m']);offset=float((centre[:2]-pivot)@axis)
                    projection=(top[:,:2]-pivot)@axis
                    ends=np.quantile(projection,[.02,.98]);imbalance=float(ends.sum())
                    uncertainty=float(np.linalg.norm(base['bootstrap_centre_sigma_xy_m']))
                    lever.update(pivot_to_upper_patch_signed_axis_offset_m=offset,
                        observed_axis_endpoints_relative_pivot_m=ends.tolist(),
                        observed_endpoint_imbalance_m=imbalance,
                        circle_centre_uncertainty_m=uncertainty)
                    # A covariance axis is unsigned. Require visible shape
                    # asymmetry substantially exceeding measured fit noise.
                    if residual>.004 or elongation<2 or abs(normal[2])<.95:
                        reason='raised_handle_patch_not_planar_and_elongated'
                    elif abs(offset)<max(.005,3*uncertainty) or abs(imbalance)<max(.01,6*uncertainty):
                        reason='raised_handle_polarity_not_measured'
                    elif np.sign(offset)!=np.sign(imbalance):
                        reason='raised_handle_polarity_evidence_disagrees'
                    else:
                        direction=axis*np.sign(offset)
                        reference=(lo[:2]+hi[:2])/2-pivot;reference/=np.linalg.norm(reference)
                        angle=float(np.degrees(np.arctan2(np.cross(reference,direction),reference@direction)))
                        lever.update(directed_axis_xy=direction.tolist(),measured_reference_xy=reference.tolist())
                        directed=True;reason=None
                fits.append({'component':component,'base':base,'lever':lever,
                    'directed_angle_measured':directed,'candidate_signed_angle_deg':angle,'reason':reason})
            row['profiles'][str(threshold)]=fits
        rows.append(row)
    output={'input_dark_report_sha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),
            'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'records':rows,
            'private_labels_opened':False,'GPU_started':False,'simulator_started':False,'runtime_changed':False,
            'calibrated_on_off_endpoints':False,'qualification_authorized':False,
            'caution':'Measured candidate geometry and noise checks only; no independent semantic truth or endpoint calibration'}
    (OUTPUT/'public_control_parts.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps({r['frame']:[{'base':f['base'] and f['base']['base_fit_supported'],'elongation':round(f['lever']['elongation_ratio'],2),
        'offset_m':f['lever'].get('pivot_to_upper_patch_signed_axis_offset_m'),'directed':f['directed_angle_measured'],'reason':f['reason']}
        for f in r['profiles']['64']] for r in rows}))


if __name__=='__main__':main()
