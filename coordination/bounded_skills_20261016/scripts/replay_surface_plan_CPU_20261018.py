# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare thin-surface contact fits on original captured public states."""
# ruff: noqa: E402 -- pin the chosen source and CPU before imports
import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))
from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_offline_labels import load_annotation_state

root = Path('/public/home/sunyihan/rpent_libero_eval')
records = []
for job, anchor in (('9248_8', 'e99'), ('9248_19', 'e35')):
    choices = next((root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*/choices.jsonl'))
    row = json.loads(choices.open().readline())
    ref = row['private_prefix_annotation_state']
    saved = load_annotation_state(ref['path'], ref['sha256'])
    before = saved['adapter'].plans[anchor]
    adapter = PublicPrefixPrediction(copy.deepcopy(saved['adapter']), row['request']).adapter
    adapter.candidate_diagnostics = []
    # The frozen context stores already resolved target depth pixels, not
    # live SAM masks/caches. The returned contact reference uses those same
    # captured public pixels; route checking remains the captured real screen.
    adapter._instance_pixels = lambda key: saved['adapter']._cloud_and_ik(key, contact=True).target.copy()
    started = time.perf_counter()
    after = adapter._surface_contact_plan(adapter.scene.entities[anchor],
        adapter.scene.measurement_clouds[anchor])
    elapsed = time.perf_counter()-started
    records.append({'job': job, 'anchor': anchor, 'state': ref, 'before_plan': before,
        'after_plan': after, 'diagnostics': adapter.candidate_diagnostics,
        'cpu_seconds': elapsed})
report = {'source': str(args.source), 'source_files': {
    name: hashlib.sha256((args.source/name).read_bytes()).hexdigest()
    for name in ('robots/libero/bounded_skills.py', 'rpent/skill_package/schema.json')},
    'records': records, 'physics_steps': 0, 'gpu_used': False, 'training': False,
    'scope': 'matched captured RGB-D and proprioception; full public route screen; not physical effectiveness',
    'contact_reference_source': 'captured resolved screen.target pixels; no live segmentation cache',
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(args.output), 'records': [
    {'job': row['job'], 'cpu_seconds': row['cpu_seconds'],
     'before_normal': row['before_plan']['surface_measurement']['normal_xyz'],
     'after_normal': row['after_plan']['surface_measurement']['normal_xyz'] if row['after_plan'] else None}
    for row in records]}))
