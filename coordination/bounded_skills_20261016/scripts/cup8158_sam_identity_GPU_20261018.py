"""Diagnose saved original RGB-D identity using existing SAM text/point APIs."""

import base64
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree

from robots.libero.v5_runtime import segmentation_prompt
from robots.libero.v5_sam3_server import V5Sam3Facade
from rpent.robots.components.sam3_client import Sam3Client

root = Path('/public/home/sunyihan/rpent_libero_eval')
directory = next((root/'results/bounded_skills/feasibility_20261017/job8158_60').glob('*oracle*'))
choices = directory/'choices.jsonl'
row = json.loads(choices.read_bytes().splitlines()[16])
key = 'e6'
anchor = next(a for a in row['request']['anchors'] if a['id'] == key)
step = row['public_geometry_evidence']['bounded_screen_e6_1_payload_local']['capture_step']
points = np.unique(np.asarray([d['obstacle_point'] for d in row['candidate_screen_diagnostics']
    if d.get('skill') == 'carry_to' and d.get('obstacle_point')]), axis=0)
output = root/'coordination/bounded_skills_20261016/reports'/('cup8158_sam_identity_GPU_job'+os.environ['SLURM_JOB_ID'])
output.mkdir()
started = time.perf_counter()
sam = V5Sam3Facade(str(root/'assets/sam3/sam3.pt'))
results = []
for camera, evidence in row['perception_evidence'][key]['sam_mask_files'].items():
    with np.load(evidence['path']) as archive:
        original = archive[archive.files[0]].astype(bool)
    with np.load(directory/(camera+'_world_high.npz')/(f'{step:02d}.npz')) as archive:
        world = archive[archive.files[0]]
    valid = np.isfinite(world).all(axis=2)
    image = base64.b64encode((directory/(camera+'_high.png')/(f'{step:02d}.png')).read_bytes()).decode()
    point = list(map(int, np.unravel_index(np.argmax(distance_transform_edt(original & valid)), original.shape)))
    prompts = list(dict.fromkeys([segmentation_prompt(anchor['label']), 'mug', 'cup']))
    replies = []
    for prompt in prompts:
        reply = sam.segment_all(image, prompt, min_score=.35)
        replies.extend(({'text_prompt': prompt}, i, item) for i, item in enumerate(reply.get('instances', [])))
    guided = sam.segment(image_base64=image, point=point, min_score=.35)
    if guided.get('found'):
        replies.append(({'point': point, 'point_source': 'deepest_current_measured_instance_pixel'}, 0, guided))
    for query, index, reply in replies:
        decoded = Sam3Client._decode_result(reply)
        mask = decoded.mask
        surface = world[mask & valid]
        name = camera+'_'+str(len(results))+'.npz'
        np.savez_compressed(output/name, mask=mask)
        results.append({'camera': camera, 'query': query, 'instance_index': index,
            'score': decoded.score, 'mask': str(output/name),
            'sha256': hashlib.sha256((output/name).read_bytes()).hexdigest(),
            'pixels': int(mask.sum()),
            'original_mask_recall': float((mask & original).sum()/max(1, original.sum())),
            'original_mask_precision': float((mask & original).sum()/max(1, mask.sum())),
            'nearest_public_blockers_m': cKDTree(surface).query(points)[0].tolist() if len(surface) else None})
report = {'scope': 'saved original public RGB-D segmentation only; zero controls, no deployed rule',
    'source_commit': os.environ['SOURCE_COMMIT'], 'job': os.environ['SLURM_JOB_ID'],
    'choices': {'path': str(choices), 'sha256': hashlib.sha256(choices.read_bytes()).hexdigest()},
    'row': 16, 'capture_step': step, 'label': anchor['label'],
    'private_truth_used': False, 'training': False, 'public_blockers': points.tolist(),
    'point_guidance_independent_of_blockers': True, 'results': results,
    'wall_s': time.perf_counter()-started}
(output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2), flush=True)
