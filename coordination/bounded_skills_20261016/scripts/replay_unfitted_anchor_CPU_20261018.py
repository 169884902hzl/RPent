# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Screen new observation approaches on an exact captured public state."""
# ruff: noqa: E402 -- select the pinned source and disable GPUs before imports
import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--job', default='9248_14')
parser.add_argument('--rows', default='3,6,9')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0, str(args.source))
from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_offline_labels import (
    annotate_prefix,
    load_annotation_state,
    request_digest,
)
from robots.libero.bounded_oracle import JUDGE_VERSION, BoundedOracle, NoPublicOption
from rpent.skill_package.contract import validate

choices = next((root/'results/bounded_skills/feasibility_20261017'/('job'+args.job)).glob('*oracle*/choices.jsonl'))
rows = [json.loads(line) for line in choices.open()]
records = []
for index in map(int, args.rows.split(',')):
    started = time.perf_counter()
    row = rows[index]
    ref = row['private_prefix_annotation_state']
    saved = load_annotation_state(ref['path'], ref['sha256'])
    original = row['request']
    old_oracle = BoundedOracle(None, saved['adapter'])
    old_oracle.binding.__dict__.update(copy.deepcopy(saved['binding']))
    before = error = None
    try:
        chosen = old_oracle._choose_one(original, saved['private_status'])
        before = {key: chosen[key] for key in ('id', 'skill', 'parameters')}
    except NoPublicOption as exc:
        error = str(exc)

    # Reconstruct the public screen from the captured scene, preserving
    # target collision checking for these noncontact approaches. No capture,
    # segmentation, simulator state restoration, or control is performed.
    prediction = PublicPrefixPrediction(copy.deepcopy(saved['adapter']), original)
    adapter = prediction.adapter
    added = []
    public_ids = {anchor['id'] for anchor in original['anchors']}
    for entity in adapter.scene.entities.values():
        if adapter.held is not None or not entity.visible or entity.id not in public_ids or entity.id in adapter.plans:
            continue
        for approach in ('above', 'front', 'left', 'right'):
            for path in ('direct', 'over', 'around'):
                candidate = adapter._candidate('move_to', {'anchor_id': entity.id,
                    'approach': approach, 'path': path})
                assert candidate is not None
                added.append(candidate)
    changed = {**original, 'candidates': [*original['candidates'], *added]}
    validate(changed)
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: saved['private_status']), adapter)
    oracle.binding.__dict__.update(copy.deepcopy(saved['binding']))
    decision = oracle.choose(changed)
    positions = copy.deepcopy(oracle.last_labels['positions'])
    # The expanded catalog has its own digest. Never annotate the old
    # request with a different catalog or pass private labels to a model.
    context = {**saved, 'request_sha256': request_digest(changed), 'adapter': adapter}
    labels = annotate_prefix(context, changed, [])
    assert all(labels[field] == positions[0][field] for field in ('legal', 'rule_acceptable', 'selected'))
    detail = []
    for candidate in added:
        route = adapter._route('move_to', candidate['parameters'])
        detail.append({**candidate, 'endpoint': route[-1]})
    selected = [{key: candidate[key] for key in ('id', 'skill', 'parameters')}
        for cid in decision['candidate_ids'] for candidate in changed['candidates'] if candidate['id'] == cid]
    records.append({'index': index, 'context': ref, 'before_selected': before,
        'before_error': error, 'before_request_sha256': request_digest(original),
        'expanded_request_sha256': request_digest(changed),
        'before_candidates': len(original['candidates']), 'after_candidates': len(changed['candidates']),
        'before_json_bytes': len(json.dumps(original).encode()),
        'after_json_bytes': len(json.dumps(changed).encode()),
        'new_candidates': detail, 'selected': selected, 'trace': oracle.private_trace,
        'legal_and_acceptable_mismatches': 0,
        'cpu_seconds': time.perf_counter()-started})
report = {'source': str(args.source), 'judge': JUDGE_VERSION, 'job': args.job,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
    'source_files': {name: hashlib.sha256((args.source/name).read_bytes()).hexdigest()
        for name in ('robots/libero/bounded_skills.py', 'robots/libero/bounded_oracle.py')},
    'records': records, 'physics_steps': 0, 'gpu_used': False, 'training': False,
    'limitation': 'Expanded-catalog diagnostic on saved public geometry; not a new live request or physical outcome.'}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(args.output), 'records': [
    {key: record[key] for key in ('index', 'before_selected', 'before_error',
        'before_candidates', 'after_candidates', 'selected', 'cpu_seconds')}
    for record in records]}))
