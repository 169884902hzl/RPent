"""Measure a tracking prototype on pinned original RGB-D/mask pairs, CPU only."""
import argparse
import hashlib
import importlib.util
import json
import platform
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np


def checked(ref):
    path=Path(ref['path'])
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ref['sha256']:
        raise ValueError(f'registered frame or mask changed: {path}')
    return path


@lru_cache(maxsize=4)
def frame(directory,camera,step):
    base=Path(directory)
    image=cv2.cvtColor(cv2.imread(str(base/(camera+'_high.png')/f'{step:02d}.png')),cv2.COLOR_BGR2RGB)
    with np.load(base/(camera+'_world_high.npz')/f'{step:02d}.npz') as file:
        world=file[file.files[0]]
    return image,world


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--prototype',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    cv2.setNumThreads(1)
    spec=importlib.util.spec_from_file_location('mask_tracking_prototype',args.prototype)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    records=[]
    missing_pairs=[]
    for job in ('9248_0','9544_124','9611_120'):
        choices,=(args.root/f'results/bounded_skills/feasibility_20261017/job{job}').glob('*oracle_k4/choices.jsonl')
        rows=[json.loads(line) for line in choices.open()]
        for before,after in zip(rows,rows[1:]):
            if 'perception_evidence' not in before or 'perception_evidence' not in after:
                missing_pairs.append({'job':job,'before_index':before.get('index'),
                    'after_index':after.get('index'),'reason':'saved_perception_evidence_missing'})
                continue
            old=before['perception_evidence']
            new=after['perception_evidence']
            for anchor in sorted(old.keys()&new.keys()):
                a=old[anchor].get('sam_mask_files',{})
                b=new[anchor].get('sam_mask_files',{})
                for camera in sorted(a.keys()&b.keys()):
                    if b[camera]['source_step']<=a[camera]['source_step']:
                        continue
                    old_file,new_file=checked(a[camera]),checked(b[camera])
                    with np.load(old_file) as stored:previous_mask=stored[stored.files[0]].astype(bool)
                    with np.load(new_file) as stored:current_sam=stored[stored.files[0]].astype(bool)
                    rgb0,world0=frame(str(choices.parent),camera,a[camera]['source_step'])
                    rgb1,world1=frame(str(choices.parent),camera,b[camera]['source_step'])
                    started=time.perf_counter()
                    mask,evidence=module.track_mask(rgb0,rgb1,world0,world1,previous_mask)
                    elapsed=time.perf_counter()-started
                    row=dict(job=job,anchor_id=anchor,camera=camera,
                        old_mask=a[camera],current_sam_mask=b[camera],tracking_s=elapsed,evidence=evidence)
                    if mask is not None:
                        union=(mask|current_sam).sum()
                        current_valid=current_sam&np.isfinite(world1).all(axis=2)
                        row.update(mask_iou_with_current_sam=float((mask&current_sam).sum()/union) if union else None,
                            median_xyz_difference_from_current_sam_m=float(np.linalg.norm(
                                np.median(world1[mask],axis=0)-np.median(world1[current_valid],axis=0)))
                                if current_valid.any() else None,
                            tracked_pixels=int(mask.sum()),current_sam_pixels=int(current_sam.sum()))
                    records.append(row)
    accepted=[row for row in records if row['evidence']['accepted']]
    report=dict(prototype=dict(path=str(args.prototype),sha256=hashlib.sha256(args.prototype.read_bytes()).hexdigest()),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),host=platform.node(),
        paired_masks=len(records),accepted=len(accepted),requires_segmentation=len(records)-len(accepted),
        reasons=dict(Counter(row['evidence']['reason'] for row in records)),records=records,
        missing_saved_frame_pairs=missing_pairs,
        median_tracking_s=float(np.median([r['tracking_s'] for r in records])) if records else None,
        physics_steps=0,sam_calls=0,gpu_used=False,training=False,
        scope='fixed three original saved episodes; every increasing-capture same-identity same-view mask pair',
        limits=['Current SAM is a public comparator, not segmentation or physical ground truth.',
            'This prototype is not enabled in the runtime or registered N1 sources.',
            'Sparse decision captures can span multiple actions; not every VLA block has a reference mask.'])
    with args.output.open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps({key:report[key] for key in ('paired_masks','accepted','requires_segmentation',
        'reasons','median_tracking_s')}),flush=True)


if __name__=='__main__':
    main()
