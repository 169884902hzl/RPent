"""Compare old/new measurements on saved RGB-D and contact surface inputs."""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path


def load(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--new-geometry',type=Path,required=True)
    p.add_argument('--new-payload',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    sys.path.insert(0,str(args.source))
    import numpy as np
    from robots.libero.bounded_offline_labels import load_annotation_state
    root=Path('/public/home/sunyihan/rpent_libero_eval')
    oldg=load(args.source/'robots/libero/v5_grasp_geometry.py','old_geometry')
    newg=load(args.new_geometry,'new_geometry')
    oldp=load(args.source/'robots/libero/bounded_payload.py','old_payload')
    newp=load(args.new_payload,'new_payload')
    records=[]
    for job in ('9248_0','9544_124','9611_120'):
        choices,=(root/f'results/bounded_skills/feasibility_20261017/job{job}').glob('*oracle_k4/choices.jsonl')
        row=json.loads(next(choices.open()));ref=row['private_prefix_annotation_state']
        saved=load_annotation_state(ref['path'],ref['sha256']);adapter=saved['adapter']
        key=next(c['parameters']['anchor_id'] for cid in row['decision']['candidate_ids']
            for c in row['request']['candidates'] if c['id']==cid and c['parameters'].get('anchor_id'))
        screen=adapter._cloud_and_ik(key,contact=True)
        source=screen.measured_target_points;world=adapter._cloud_and_ik().measured_scene_points
        arms=[]
        for name,module in (('old',oldp),('new',newp)):
            begin=time.perf_counter();result=module.stationary_surface_registration(source,world,source)
            elapsed=time.perf_counter()-begin;raw=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
            arms.append({'name':name,'wall_s':elapsed,'result':result,'sha256':hashlib.sha256(raw).hexdigest()})
        record={'job':job,'annotation':ref,'registration':arms,
            'registration_bytes_equal':arms[0]['sha256']==arms[1]['sha256'],'plane_fits':[]}
        for camera in ('agentview','wrist'):
            step=max(e['capture_step'] for anchor in row['request']['anchors'] if anchor['id']==key
                for e in anchor['evidence'])
            path=choices.parent/(camera+'_world_high.npz')/f'{step:02d}.npz'
            with np.load(path) as blob: image=blob['array']
            # Exact selected instance pixels, no private object geometry.
            from scipy.spatial import cKDTree
            target=np.asarray(source);flat=image.reshape(-1,3)
            near=((flat>=target.min(0)-1e-6)&(flat<=target.max(0)+1e-6)).all(1)
            mask=np.zeros(len(flat),bool);mask[near]=cKDTree(target).query(flat[near],distance_upper_bound=np.nextafter(1e-6,np.inf))[0]<=1e-6
            mask=mask.reshape(image.shape[:2]);values=[];timings=[]
            for name,module in (('old',oldg),('new',newg)):
                begin=time.perf_counter();result,evidence=module.complete_planar_boundary(image,mask)
                timings.append({'name':name,'wall_s':time.perf_counter()-begin,'evidence':evidence,
                    'mask_sha256':hashlib.sha256(result.tobytes()).hexdigest()});values.append(result)
            record['plane_fits'].append({'camera':camera,'arms':timings,
                'mask_bytes_equal':values[0].tobytes()==values[1].tobytes(),
                'different_pixels':int(np.count_nonzero(values[0]!=values[1]))})
        records.append(record)
        print(json.dumps({'job':job,'registration_equal':record['registration_bytes_equal'],
            'plane_differences':[r['different_pixels'] for r in record['plane_fits']]}),flush=True)
    with args.output.open('x') as stream:
        json.dump({'records':records,'physics_steps':0,'rpc_calls':0,'gpu_used':False,'training':False},stream,indent=2)
    assert all(r['registration_bytes_equal'] and all(v['mask_bytes_equal'] for v in r['plane_fits']) for r in records)


if __name__=='__main__':main()
