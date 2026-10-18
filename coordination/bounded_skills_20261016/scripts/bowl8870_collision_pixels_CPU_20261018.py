"""Locate saved public collision pixels and their same-frame instance masks."""
import hashlib
import json
import os
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree

root=Path('/public/home/sunyihan/rpent_libero_eval')
base=root/'coordination/bounded_skills_20261016'
results=[]
for job, key, skill in (('8870_2', 'e15', 'carry_to'),('8870_3', 'e61', 'lift')):
    directory=next((root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*'))
    raw=(directory/'choices.jsonl').read_bytes()
    rows=[json.loads(l) for l in raw.splitlines()]
    row=rows[2]
    block=next(d for d in row['candidate_screen_diagnostics'] if d.get('skill')==skill)
    hits=block['public_scene_collision_points']
    points=np.unique(np.asarray([p for h in hits.values() for p in h]),axis=0)
    scene=next(v for k,v in row['public_geometry_evidence'].items() if k.endswith('_scene'))
    step=scene['capture_step']
    entry=dict(job=job, row=2, capture_step=step, anchor_id=key, blocked_skill=skill,
        points=points.tolist(), input_choices_sha256=hashlib.sha256(raw).hexdigest(), views=[])
    tiles=[]
    for camera in ('agentview','wrist'):
        path=directory/(camera+'_world_high.npz')/(f'{step:02d}.npz')
        with np.load(path) as f: world=f[f.files[0]]
        ids=np.flatnonzero(np.isfinite(world).all(2))
        distance,near=cKDTree(world.reshape(-1,3)[ids]).query(points)
        ys,xs=np.unravel_index(ids[near],world.shape[:2])
        mask_ref=row['perception_evidence'][key].get('sam_mask_files',{}).get(camera)
        mask=None
        if mask_ref:
            p=Path(mask_ref['path'])
            assert hashlib.sha256(p.read_bytes()).hexdigest()==mask_ref['sha256']
            with np.load(p) as f: mask=f[f.files[0]].astype(bool)
        image=Image.open(directory/(camera+'_high.png')/(f'{step:02d}.png')).convert('RGB')
        rgb=[image.getpixel((int(x),int(y))) for x,y in zip(xs,ys)]
        entry['views'].append(dict(camera=camera, pixels=list(zip(xs.tolist(),ys.tolist())),
            nearest_raw_m=distance.tolist(), rgb=rgb,
            saved_sam_mask_members=[bool(mask[y,x]) for x,y in zip(xs,ys)] if mask is not None else None,
            saved_mask=mask_ref))
        draw=ImageDraw.Draw(image)
        for x,y in zip(xs,ys): draw.ellipse((x-6,y-6,x+6,y+6),outline='red',width=2)
        x,y=int(np.mean(xs)),int(np.mean(ys))
        tile=image.crop((max(0,x-100),max(0,y-100),min(image.width,x+100),min(image.height,y+100))).resize((400,400))
        ImageDraw.Draw(tile).text((10,10),job+' '+camera,fill='red')
        tiles.append(tile)
    grid=Image.new('RGB',(800,400));grid.paste(tiles[0],(0,0));grid.paste(tiles[1],(400,0))
    path=base/'reports'/f'{job}_collision_pixels_CPU_20261018.png'
    grid.save(path)
    entry['annotated_image']=str(path)
    results.append(entry)
report=dict(scope='saved public depth/RGB and same-record SAM pixel audit only',results=results,
    controls=0, fresh_sam_queries=0, GPU_used=False,private_truth_used=False,training=False,confirmation=False)
p=base/'reports/bowl8870_collision_pixels_CPU_20261018.json'
p.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
