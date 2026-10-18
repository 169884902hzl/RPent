# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Screen saved rejected SAM door clouds with the existing panel residuals."""
# ruff: noqa: E402 -- choose the immutable source and CPU before imports
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
source = root/'source_bounded_chunk_v3_anchor_recovery_20261018_eee8434'
sys.path.insert(0, str(source))
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from robots.libero.v5_verification import vertical_face


def dominant_panel(points):
    """Use the same 4 mm consensus, 55 percent support and vertical-face test."""
    rng = np.random.default_rng(0)
    sample = points[rng.choice(len(points), min(len(points), 2500), replace=False)]
    pairs = rng.choice(len(sample), (128, 2), replace=True)
    vectors = sample[pairs[:, 1], :2]-sample[pairs[:, 0], :2]
    norms = np.linalg.norm(vectors, axis=1)
    supported = norms > .05
    if not np.any(supported):
        return points[:0], {'reason': 'panel_width_not_measured'}
    normals = np.stack([-vectors[supported, 1], vectors[supported, 0]], axis=1)/norms[supported, None]
    anchors = sample[pairs[supported, 0], :2]
    distances = np.abs(np.einsum('nmi,mi->nm', sample[:, None, :2]-anchors, normals))
    best = int(np.argmax(np.sum(distances <= .004, axis=0)))
    inside = np.abs((points[:, :2]-anchors[best])@normals[best]) <= .004
    panel = points[inside]
    fit = vertical_face(panel)
    evidence = {'points': len(points), 'panel_points': len(panel),
        'fraction': float(inside.mean()), 'plane': fit,
        'geometric_support': bool(inside.mean() >= .55 and fit is not None)}
    return panel, evidence


images = base/'reports/door9475_plane_images'
images.mkdir(exist_ok=True)
records = []
for job, index in (('9475_120', 10), ('9475_140', 14)):
    choices = next((root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*/choices.jsonl'))
    raw = choices.read_bytes().splitlines()[index]
    row = json.loads(raw)
    for parent, detail in row['fixture_measurement_evidence'].items():
        for instance in detail.get('door_measurement', {}).get('instances', []):
            ref = instance.get('candidate_cloud')
            if ref is None or ref['points'] < 60:
                continue
            path = Path(ref['path'])
            assert hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256']
            with np.load(path) as arrays:
                points = arrays[arrays.files[0]]
            panel, fit = dominant_panel(points)
            camera, step = instance['camera'], ref['source_step']
            with np.load(choices.parent/f'{camera}_world_high.npz'/f'{step:02d}.npz') as arrays:
                world = arrays[arrays.files[0]]
            pixels = np.isfinite(world).all(-1)
            mask = np.zeros(pixels.shape, bool)
            if len(panel):
                mask[pixels] = cKDTree(panel).query(world[pixels])[0] < 1e-5
            image = np.array(Image.open(choices.parent/f'{camera}_high.png'/f'{step:02d}.png').convert('RGB'))
            image[mask] = (image[mask].astype(float)*.45+[140., 0., 0.]).astype(np.uint8)
            overlay = images/f'{job}_{index}_{parent}_{camera}_{path.parent.name}.png'
            Image.fromarray(image).save(overlay)
            records.append({'job': job, 'row': index,
                'row_sha256': hashlib.sha256(raw).hexdigest(), 'parent': parent,
                'camera': camera, 'source_step': step, 'candidate_cloud': ref,
                'recorded_reason': instance.get('reason'), 'recorded_plane': instance.get('plane'),
                'screen': fit, 'overlay': {'path': str(overlay),
                    'sha256': hashlib.sha256(overlay.read_bytes()).hexdigest()}})
report = {'records': records, 'source': str(source),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'saved public RGB-D only; geometric plane support does not establish moving-door identity',
    'physics_steps': 0, 'gpu_used': False, 'training': False}
output = base/'reports/microwave9475_plane_consensus_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(output), 'records': [{
    'job': r['job'], 'parent': r['parent'], 'camera': r['camera'],
    'fraction': r['screen'].get('fraction'), 'supported': r['screen'].get('geometric_support'),
    'overlay': r['overlay']['path']} for r in records]}))
