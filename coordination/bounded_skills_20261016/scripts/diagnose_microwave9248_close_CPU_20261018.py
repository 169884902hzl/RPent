# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Inspect original recorded microwave-close binding loss on CPU."""
# ruff: noqa: E402 -- choose immutable source and disable GPU before imports
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
parser = argparse.ArgumentParser()
parser.add_argument('--job', default='9248_6')
parser.add_argument('--source', type=Path,
    default=root/'source_bounded_chunk_v3_support_plane_20261018_ec89f74')
parser.add_argument('--rows', default='0,3,6,9,-1')
args = parser.parse_args()
source = args.source
sys.path.insert(0, str(source))
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.bounded_oracle import BoundedOracle, NoPublicOption

directory = root/'results/bounded_skills/feasibility_20261017'/('job'+args.job)
choices = next(directory.glob('*oracle*/choices.jsonl'))
rows = [json.loads(line) for line in choices.open()]
records = []
for selected_index in map(int, args.rows.split(',')):
    index = selected_index if selected_index >= 0 else len(rows)+selected_index
    row = rows[index]
    ref = row['private_prefix_annotation_state']
    state = load_annotation_state(ref['path'], ref['sha256'])
    adapter = state['adapter']
    oracle = BoundedOracle(None, adapter)
    oracle.binding.__dict__.update(state['binding'])
    binding = {key: {name: sorted(value) if isinstance(value, set) else value
                    for name, value in values.items()}
               for key, values in state['binding'].items() if key in {'_bindings', '_binding_peers'}}
    selected = error = None
    try:
        choice = oracle._choose_one(row['request'], state['private_status'])
        selected = {key: choice[key] for key in ('id', 'skill', 'parameters')}
    except NoPublicOption as exc:
        error = str(exc)
    diagnostics = []
    for record in row.get('candidate_screen_diagnostics', []):
        if record.get('stage') in {'fixture_contact_measurement', 'fixture_contact_plan'}:
            diagnostics.append({key: record.get(key) for key in
                ('stage', 'anchor_id', 'label', 'reason', 'measurement')})
    records.append({'index': index, 'context': ref, 'binding': binding,
        'private_status': state['private_status'], 'active': adapter.active, 'held': adapter.held,
        'plans': list(adapter.plans), 'selected': selected, 'error': error,
        'trace': oracle.private_trace,
        'entities': [{key: getattr(entity, key, None) for key in
            ('id', 'name', 'part_of', 'visible', 'geometry', 'xyz', 'lower', 'upper')}
            for entity in adapter.scene.entities.values()],
        'diagnostics': diagnostics})
report = {'source': str(source), 'job': args.job, 'training': False, 'controls': 0,
          'gpu_used': False, 'records': records,
          'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports'/f'microwave{args.job}_binding_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(output), 'records': [
    {key: record[key] for key in ('index', 'binding', 'plans', 'active', 'selected', 'error', 'trace')}
    for record in records]}))
