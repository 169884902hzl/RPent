"""Compare observed flank sampling on two saved public cup measurements."""
# ruff: noqa: E402 -- source and CPU environment are pinned before imports
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root / 'source_bounded_chunk_v3_current_handle_20261019_ede83b18'
sys.path.insert(0, str(source))
import numpy as np

from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.v5_geometric_grasp import _opposition
from robots.libero.v5_grasp_geometry import measured_grasp_regions
from robots.libero.v5_grasp_route import separate_target_points

records = []
for job in ('9248_14', '9544_124'):
    choices = next((root / f'results/bounded_skills/feasibility_20261017/job{job}').glob(
        '*oracle_k4/choices.jsonl'))
    rows = [json.loads(line) for line in choices.read_text().splitlines()]
    row = rows[-2]
    ref = row['private_prefix_annotation_state']
    saved = load_annotation_state(ref['path'], ref['sha256'])
    adapter = saved['adapter']
    anchor, = (a for a in row['request']['anchors'] if a['label'] == 'white yellow mug')
    cloud, _ = separate_target_points(adapter.scene.measurement_clouds[anchor['id']], np.empty((0, 3)))
    region, evidence = measured_grasp_regions(cloud, anchor['label'])
    base_axis = math.atan2(*region['closing_axis_xy'][::-1])
    added = []
    for q in (.2, .4, .6, .8):
        height = np.quantile(cloud[:, 2], q)
        band = cloud[abs(cloud[:, 2] - height) <= .005]
        for angle in np.linspace(0, 2 * math.pi, 24, endpoint=False):
            direction = np.array([math.cos(angle), math.sin(angle)])
            point = band[np.argmax((band[:, :2] - np.median(cloud[:, :2], axis=0)) @ direction)]
            added.append(point)
    arms = []
    for name, seeds in (('existing', region['seeds']), ('measured_band_extrema', added)):
        started = time.perf_counter()
        comparisons = []
        for index, seed in enumerate(seeds):
            for offset in (0., math.pi / 4, -math.pi / 4, math.pi / 2):
                closing = np.array([math.cos(base_axis + offset), math.sin(base_axis + offset), 0.])
                contact, detail = _opposition(region['points'], seed, closing)
                comparisons.append({'seed_index': index, 'seed_xyz_m': np.asarray(seed).tolist(),
                    'closing_axis_xyz': closing.tolist(), 'contact_xyz_m': None if contact is None else contact.tolist(),
                    'accepted': contact is not None, 'detail': detail})
        arms.append({'name': name, 'cpu_seconds': time.perf_counter() - started,
            'counts': dict(Counter('accepted' if r['accepted'] else r['detail']['reason'] for r in comparisons)),
            'comparisons': comparisons})
    records.append({'job': job, 'row': len(rows) - 2, 'anchor': anchor, 'context': ref,
        'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(), 'arms': arms,
        'perception': evidence})
output = root / 'coordination/bounded_skills_20261016/reports/cup_measured_flanks_CPU_20261019.json'
with output.open('x') as stream:
    json.dump({'source': str(source), 'source_commit': 'ede83b18',
        'scope': 'cross-source public-geometry hypothesis only; no physical or runtime change',
        'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'records': records}, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'rows': [{'job': r['job'],
    'arms': [{k: a[k] for k in ('name', 'cpu_seconds', 'counts')} for a in r['arms']]} for r in records]}))
