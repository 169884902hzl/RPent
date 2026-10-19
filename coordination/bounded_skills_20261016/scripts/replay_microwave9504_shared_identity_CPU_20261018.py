# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Replay public identity grouping against the original saved request states."""
# ruff: noqa: E402 -- pin the CPU candidate and immutable capture source before imports
import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
parser = argparse.ArgumentParser()
parser.add_argument('--candidate', type=Path, required=True)
args = parser.parse_args()
source = root/'source_bounded_chunk_v3_handle_backing_20261018_31a70c0'
sys.path.insert(0, str(source))
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.v5_fixture_parts import measured_microwave_parent_groups

spec = importlib.util.spec_from_file_location('candidate_fixture_parts', args.candidate)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
choices = next((root/'results/bounded_skills/feasibility_20261017/job9504_120').glob('*oracle*/choices.jsonl'))
rows = [json.loads(line) for line in choices.open()]
records = []
for index in (2, 3, 7, 8, 9, 10):
    row = rows[index]
    ref = row['private_prefix_annotation_state']
    state = load_annotation_state(ref['path'], ref['sha256'])
    adapter = state['adapter']
    step = adapter.ex.toolkit._state.latest_step
    parents = [e for e in adapter.scene.entities.values() if e.name == 'microwave'
               and e.visible and e.id in adapter.scene.measurement_clouds]
    doors = {e.id: row['fixture_measurement_evidence'].get(e.id, {}).get('door_measurement', {})
             for e in parents}
    clouds = {part.part_of: adapter.scene.measurement_clouds[part.id]
        for part in adapter.scene.entities.values() if part.name == 'microwave door'
        and part.visible and part.source_step == step and part.id in adapter.scene.measurement_clouds}
    before, _ = measured_microwave_parent_groups(parents, doors, step)
    after, evidence = candidate.measured_microwave_parent_groups(parents, doors, step, door_clouds=clouds)
    groups = lambda values: [[e.id for e in group] for group in values]
    records.append({'row': index, 'capture_step': step, 'state': ref,
        'before_groups': groups(before), 'after_groups': groups(after), 'evidence': evidence,
        'used_inputs': 'current public measured entity bounds and independently segmented door pixels only'})
    print(json.dumps({k: records[-1][k] for k in ('row', 'capture_step', 'before_groups', 'after_groups', 'evidence')}), flush=True)
output = base/'reports/microwave9504_shared_identity_replay_CPU_20261018.json'
with output.open('x') as stream:
    json.dump({'records': records, 'source': str(source), 'candidate': str(args.candidate),
        'candidate_sha256': hashlib.sha256(args.candidate.read_bytes()).hexdigest(),
        'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'physics_steps': 0, 'gpu_used': False, 'training': False,
        'scope': 'public grouping replay only; no physical endpoint success inferred'}, stream, indent=2)
    stream.write('\n')
