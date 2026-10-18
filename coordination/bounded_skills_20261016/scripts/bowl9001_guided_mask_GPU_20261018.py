"""Inspect full guided masks from saved public prompts, without controls."""
import argparse
import base64
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('--prepare-only', action='store_true')
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
directory = next((root/'results/bounded_skills/feasibility_20261017/job9001_2').glob('*oracle_k4'))
choices = directory/'choices.jsonl'
row = json.loads(choices.read_bytes().splitlines()[2])
queries = [v for v in row['instance_boundary_evidence']['e15']
           if v.get('source') == 'current_measured_instance_interior_point_sam']
assert len(queries) == 2 and {v['camera'] for v in queries} == {'agentview', 'wrist'}
inputs = []
for query in queries:
    camera, step = query['camera'], row['public_geometry_evidence']['bounded_screen_e15_1_scene']['capture_step']
    image = directory/(camera+'_high.png')/(f'{step:02d}.png')
    depth = directory/(camera+'_world_high.npz')/(f'{step:02d}.npz')
    assert image.is_file() and depth.is_file()
    with np.load(depth) as stored:
        world = stored[stored.files[0]]
    assert np.isfinite(world[tuple(query['point_row_col'])]).all()
    inputs.append({'camera': camera, 'point': query['point_row_col'], 'image': str(image),
                   'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(), 'world': str(depth),
                   'world_sha256': hashlib.sha256(depth.read_bytes()).hexdigest(),
                   'bounds': query['prompt_surface_bounds_m']})
if args.prepare_only:
    print(json.dumps({'inputs': inputs, 'private_truth_used': False, 'controls': 0}))
    raise SystemExit(0)

from robots.libero.v5_sam3_server import V5Sam3Facade  # noqa: E402
from rpent.robots.components.sam3_client import Sam3Client  # noqa: E402

output = root/'coordination/bounded_skills_20261016/reports'/('bowl9001_guided_mask_job'+os.environ['SLURM_JOB_ID'])
output.mkdir()
started = time.perf_counter()
sam = V5Sam3Facade(str(root/'assets/sam3/sam3.pt'))
results = []
for query in inputs:
    raw = Path(query['image']).read_bytes()
    reply = sam.segment(image_base64=base64.b64encode(raw).decode(), point=query['point'], min_score=.35)
    decoded = Sam3Client._decode_result(reply)
    record = {'camera': query['camera'], 'query': query, 'found': decoded.found}
    if not decoded.found:
        record['reason'] = decoded.reason
    else:
        mask = decoded.mask
        with np.load(query['world']) as stored:
            world = stored[stored.files[0]]
        lower, upper = query['bounds']
        valid = (np.isfinite(world).all(axis=2)
                 & (world >= lower).all(axis=2) & (world <= upper).all(axis=2))
        path = output/(query['camera']+'_full_mask.npz')
        np.savez_compressed(path, mask=mask)
        record.update(mask=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      score=decoded.score, pixels=int(mask.sum()), clipped_pixels=int((mask & valid).sum()))
    results.append(record)
report = {'choices': str(choices), 'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
          'row': 2, 'results': results, 'controls': 0, 'private_truth_used': False, 'training': False,
          'point_guidance_source': 'original runtime interior point, unchanged',
          'source_commit': os.environ['SOURCE_COMMIT'], 'wall_s': time.perf_counter()-started}
(output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
