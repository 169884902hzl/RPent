"""Unchanged stove559 heuristic on fifty fixed original captures; no labels."""

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import ConvexHull


def load_function(path, name, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('pinned public helper changed')
    tree = ast.parse(data)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {'np': np, 'ConvexHull': ConvexHull}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--packet', type=Path, required=True)
    args = parser.parse_args()
    root, packet = args.root, args.packet
    prior = root / 'results/harness_v5/stove559_public_geometry_CPU_20261006'
    circle = load_function(prior/'fit_full_frame_public_control_parts.py', 'circle_fit',
                           '17892bacf8df3c99f1543fef2795a4ee6557fd941e7f64bd2722019c5db1208b')
    edges_for = load_function(prior/'measure_public_shell_reference.py', 'shell_edges',
                              '5e9c10b481cc290d7aa7d5b22c0bc7c28f67902dda66dda1b7d8895ea61c3cb2')
    manifest = json.loads((packet/'public50_capture_manifest.json').read_text())
    if len(manifest['captures']) != 50 or manifest['success_label_selection']:
        raise ValueError('fixed public capture plan changed')
    checked = {}

    def file(ref):
        path = Path(ref['path'])
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha != ref['sha256'] or not path.is_absolute() or not str(path).startswith(str(root)+'/'):
            raise ValueError('explicit public evidence changed')
        checked[str(path)] = {'path': str(path), 'sha256': sha, 'bytes': len(data)}
        return path

    rows = []
    for capture in manifest['captures']:
        original = capture['data']
        shell = original['current_stove_shell']
        main = original['views']['agentview']
        shell_instances = [instance for query in main['queries'] if query.get('feature_role')=='shell'
                           for instance in query['instances']]
        body_cloud = None
        if len(shell_instances) == 1:
            mask = np.asarray(Image.open(file(shell_instances[0]['mask']))) > 0
            with np.load(file(main['files']['world']), allow_pickle=False) as archive:
                body_world = archive['array']
            valid = np.isfinite(body_world).all(axis=-1) & (np.abs(body_world).sum(axis=-1)>1e-6)
            body_cloud = body_world[mask & valid].astype(float)
        for camera in ('agentview', 'wrist'):
            view = original['views'][camera]
            refs = view['files']
            rgb = np.asarray(Image.open(file(refs['rgb'])).convert('RGB'))
            with np.load(file(refs['world']), allow_pickle=False) as archive:
                world = archive['array']
            file(refs['metadata'])
            if world.shape != (*rgb.shape[:2],3):
                raise ValueError('public RGB-D alignment changed')
            row = {'frame': f"{capture['case']}_{capture['phase']}_{capture['stage']}_{camera}",
                   'case': capture['case'], 'phase': capture['phase'], 'stage': capture['stage'],
                   'camera': camera, 'source_step': capture['source_step'], 'public_files': refs,
                   'profiles': {}, 'endpoint_state': 'unmeasured',
                   'current_same_capture_shell': bool(shell and shell['source_step']==capture['source_step'])}
            if not row['current_same_capture_shell']:
                row.update(status='current_measured_shell_missing')
                rows.append(row)
                continue
            lo, hi = np.asarray(shell['lower']), np.asarray(shell['upper'])
            gap = np.maximum(0,np.maximum(lo-world,world-hi))
            valid = np.isfinite(world).all(axis=-1)&(np.abs(world).sum(axis=-1)>1e-6)
            search = valid&(np.linalg.norm(gap,axis=-1)<=.15)
            search &= (world[...,2]>=hi[2]-.015)&(world[...,2]<=hi[2]+.08)
            search &= ~((world[...,:2]>=lo[:2])&(world[...,:2]<=hi[:2])).all(axis=-1)
            for threshold in (40,64,80):
                labels,count = ndimage.label((rgb.max(axis=-1)<=threshold)&search)
                fits = []
                for number in range(1,count+1):
                    mask = labels == number
                    if mask.sum()<100:
                        continue
                    points = world[mask].astype(float)
                    lower,upper = np.quantile(points,(.02,.98),axis=0)
                    if max(upper-lower)>.13:
                        continue
                    component_gap = np.maximum(0,np.maximum(lo-upper,lower-hi))
                    if np.linalg.norm(component_gap)>.07:
                        continue
                    cloud = np.unique(points,axis=0)
                    fit = {'component_label': number, 'pixels': int(mask.sum()), 'unique_points': len(cloud),
                           'component_shell_gap_m': float(np.linalg.norm(component_gap)),
                           'base': None, 'lever': None, 'candidate_angle_to_measured_shell_edge_deg': None,
                           'directed_angle_measured': False, 'reason': None}
                    try:
                        boundary = cloud[ConvexHull(cloud[:,:2]).vertices,:2]
                        base = circle(boundary)
                        top_min = float(np.quantile(cloud[:,2],.95)-.004)
                        top = cloud[cloud[:,2]>=top_min]
                        centre = np.median(top,axis=0)
                        _,singular,axes = np.linalg.svd(top-centre,full_matrices=False)
                        axis = axes[0,:2]
                        axis = axis/np.linalg.norm(axis)
                        normal = axes[-1]
                        residual = float(np.quantile(np.abs((top-centre)@normal),.9))
                        elongation = float(singular[0]/max(singular[1],1e-12))
                        lever = {'upper_patch_z_min_m': top_min, 'upper_patch_points': len(top),
                                 'upper_patch_centre_xyz_m': centre.tolist(), 'undirected_axis_xy': axis.tolist(),
                                 'elongation_ratio': elongation, 'plane_residual_p90_m': residual,
                                 'normal_vertical_cosine': float(abs(normal[2]))}
                        fit.update(base=base,lever=lever,reason='base_circle_not_supported')
                        if base and base['base_fit_supported']:
                            pivot = np.asarray(base['centre_xy_m'])
                            offset = float((centre[:2]-pivot)@axis)
                            ends = np.quantile((top[:,:2]-pivot)@axis,[.02,.98])
                            imbalance = float(ends.sum())
                            uncertainty = float(np.linalg.norm(base['bootstrap_centre_sigma_xy_m']))
                            lever.update(pivot_to_upper_patch_signed_axis_offset_m=offset,
                                observed_axis_endpoints_relative_pivot_m=ends.tolist(),
                                observed_endpoint_imbalance_m=imbalance,circle_centre_uncertainty_m=uncertainty)
                            if residual>.004 or elongation<2 or abs(normal[2])<.95:
                                fit['reason']='raised_handle_patch_not_planar_and_elongated'
                            elif abs(offset)<max(.005,3*uncertainty) or abs(imbalance)<max(.01,6*uncertainty):
                                fit['reason']='raised_handle_polarity_not_measured'
                            elif np.sign(offset)!=np.sign(imbalance):
                                fit['reason']='raised_handle_polarity_evidence_disagrees'
                            else:
                                direction=axis*np.sign(offset)
                                lever['directed_axis_xy']=direction.tolist()
                                fit.update(directed_angle_measured=True,reason=None)
                                if body_cloud is not None:
                                    edge_candidates=edges_for(body_cloud,pivot)
                                    unique=(len(edge_candidates)==1 or (len(edge_candidates)>1 and
                                            edge_candidates[1]['pivot_distance_m']-edge_candidates[0]['pivot_distance_m']>.01))
                                    fit['public_shell_edge_candidates']=edge_candidates
                                    if unique:
                                        reference=np.asarray(edge_candidates[0]['normal_towards_measured_body_xy'])
                                        fit['candidate_angle_to_measured_shell_edge_deg']=float(np.degrees(np.arctan2(
                                            np.cross(reference,direction),reference@direction)))
                                    else:
                                        fit['reference_reason']='independent_unique_shell_edge_missing'
                                else:
                                    fit['reference_reason']='unique_same_capture_main_shell_mask_missing'
                    except Exception as error:
                        fit.update(reason='public_geometry_unmeasured',error=repr(error))
                    fits.append(fit)
                row['profiles'][str(threshold)] = fits
            row['status']='public_geometry_measured'
            row['candidate_angle_deg']=None
            baseline=row['profiles']['64']
            if len(baseline)==1:
                row['candidate_angle_deg']=baseline[0]['candidate_angle_to_measured_shell_edge_deg']
            pivots=[np.asarray(f['base']['centre_xy_m']) for fits in row['profiles'].values() for f in fits
                    if f['base'] and f['base']['base_fit_supported']]
            row['threshold_centre_spread_m']=float(max(np.linalg.norm(a-b) for a in pivots for b in pivots)) if pivots else None
            rows.append(row)
            print(json.dumps({'frame':row['frame'],'components64':len(baseline),
                              'candidate_angle':row['candidate_angle_deg']}),flush=True)
    existing=json.loads((prior/'geometry_evidence.json').read_text())['records']
    existing_by_name={r['frame']:r for r in existing}
    exact=[]
    for row in rows:
        if row['frame'] in existing_by_name:
            previous=existing_by_name[row['frame']]['candidate_signed_angle_to_measured_edge_deg']
            new=row.get('candidate_angle_deg')
            equal=(new is None and previous is None) or (new is not None and previous is not None and abs(new-previous)<1e-10)
            exact.append({'frame':row['frame'],'old_angle_deg':previous,'new_angle_deg':new,'matches':equal})
    def summary(selected):
        baseline=[r['profiles'].get('64',[]) for r in selected]
        return {'views':len(selected),'current_shell':sum(r['current_same_capture_shell'] for r in selected),
                'unique_component':sum(len(f)==1 for f in baseline),
                'unique_supported_base':sum(len(f)==1 and bool(f[0]['base'] and f[0]['base']['base_fit_supported']) for f in baseline),
                'unique_directed_handle':sum(len(f)==1 and f[0]['directed_angle_measured'] for f in baseline),
                'candidate_angle_to_shell_edge':sum(r.get('candidate_angle_deg') is not None for r in selected),
                'reason_counts':dict(Counter(f['reason'] for fits in baseline for f in fits))}
    result={'records':rows,'total':summary(rows),
            'by_phase_stage_camera':{f'{phase}/{stage}/{camera}':summary([r for r in rows if (r['phase'],r['stage'],r['camera'])==(phase,stage,camera)])
              for phase,stage in [('on','before_contact'),('on','pre_recovery'),('on','post_recovery'),('off','pre_recovery'),('off','post_recovery')]
              for camera in ('agentview','wrist')},
            'known559_reproduction':exact,'private_labels_opened':False,'thresholds_unchanged':True,
            'GPU_started':False,'simulator_started':False,'runtime_changed':False,'endpoint_qualified':False,
            'uncertainty_scope':'Conditional bootstrap excludes model-selection/threshold bias; threshold centre spread reported separately',
            'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (packet/'public50_geometry.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (packet/'public50_geometry_input_manifest.json').write_text(json.dumps({'files':list(checked.values()),
        'explicit_original_public_file_refs_only':True,'private_labels_opened':False},indent=2)+'\n')
    print(json.dumps({'total':result['total'],'known_reproduction_count':len(exact),
                      'known_reproduction_all_match':all(r['matches'] for r in exact)}))


if __name__ == '__main__':
    main()
