"""Extend immutable r4 evidence with omitted original collection roots.

No truth is recomputed. Evidence aliases remain distinct references, never
additional physical trials. PRO/development/MAX roots are excluded explicitly.
"""
from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT/'results/harness_v5'
OLD = ROOT/'coordination/grasp_truth_registered_v3_history_20261010_r4'
OUT = ROOT/'coordination/grasp_truth_registered_v3_history_20261010_r5'
INVENTORY = ROOT/'coordination/grasp_truth_registered_v3_history_20261010_r2/top_inventory.json'
ORIGINAL = {'libero_spatial', 'libero_object', 'libero_goal', 'libero_10', 'libero_90'}
PRUNE = {'frames', 'images', 'videos', 'media', 'captures', 'state', 'states',
         'observation', 'observations', 'assets', 'preparation', 'preparation_r2',
         'source', '__pycache__', '.git', 'logs', 'empty_memory', 'perception'}
LEDGERS = {'episodes.jsonl', 'choices.jsonl', 'trials.jsonl', 'private_grasp.jsonl',
           'oracle_labels.jsonl', 'private_diagnostics.jsonl', 'grasp_truth.jsonl'}
FORBIDDEN = re.compile(r'(?i)(?:libero_(?:spatial|object|goal|10)_(?:task|swap)_t|(?:^|/)(?:A[1-4]|RULE)[-_]|sealed|liberomax|max160)')
ADDITIONAL = re.compile(r'(?i)(?:shared_(?:smoke|step)|shared_20261001|long35_(?:cf|packet|resume)|white_mug_|mug_|^spatial4_|^measured_region|^fixture_front131|^branch_state2|^microwave_saved_cohort|^storage_predicates|^canceled_old_collection|^perception_binding_smoke|^package_(?:probe|saved)|^wrist103_smoke|^libero_binding4|^white_mug_pipeline|^table_center_|^held_sync_)')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stages(row):
    candidates = [('first_attempt', row['first_attempt'])] if isinstance(row.get('first_attempt'), dict) else []
    for key in ('setup', 'attempts'):
        if isinstance(row.get(key), list):
            candidates.extend((f'{key}/{i}', r) for i, r in enumerate(row[key])
                              if isinstance(r, dict) and (r.get('receipt') or r.get('private_setup_hold')))
    if row.get('receipt') or row.get('private_grasp_phase') or row.get('contact_samples') or row.get('grasp_attempted'):
        candidates.append(('row', row))
    seen = set()
    for key, stage in candidates:
        sha = digest(json.dumps(stage, sort_keys=True, separators=(',', ':')).encode())
        if sha not in seen:
            seen.add(sha)
            yield key, stage


parent = json.loads((OLD/'index_manifest.json').read_text())
payload = (OLD/'input_rows.jsonl').read_bytes()
if digest(payload) != parent['index_sha256']:
    raise ValueError('immutable parent index changed')
OUT.mkdir(exist_ok=False)
(OUT/'inputs').mkdir()
files = json.loads((OLD/'input_files.json').read_text())
known_paths = {r['path'] for r in files}
metadata = {r['path']: r for r in json.loads((OLD/'captured_metadata.json').read_text())}
records = [json.loads(line) for line in payload.splitlines()]
inventory = json.loads(INVENTORY.read_text())
errors, added_files, coverage = [], [], []


def capture(path):
    data = path.read_bytes()
    sha = digest(data)
    output = OUT/'inputs'/(sha + path.suffix)
    if not output.exists():
        output.write_bytes(data)
    return {'path': str(path), 'captured_path': str(output), 'sha256': sha, 'bytes': len(data)}


for entry in inventory:
    top = Path(entry['path'])
    if entry['included'] or not ADDITIONAL.search(top.name):
        continue
    coverage.append({'path': str(top), 'scope': 'additional_original_collection_candidate', 'new_ledgers': 0})
    queue = [top]
    while queue:
        directory = queue.pop()
        if FORBIDDEN.search(str(directory.relative_to(BASE))):
            continue
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            errors.append({'path': str(directory), 'error': repr(exc)})
            continue
        leaf = any(e.name == 'choices.jsonl' for e in entries)
        for child in entries:
            if child.is_dir(follow_symlinks=False):
                if not leaf and child.name not in PRUNE and not child.name.startswith(('source_', 'step_')):
                    queue.append(Path(child.path))
            elif child.is_file(follow_symlinks=False) and child.name in LEDGERS and child.path not in known_paths:
                try:
                    item = capture(Path(child.path))
                    files.append(item)
                    added_files.append(item)
                    known_paths.add(child.path)
                    coverage[-1]['new_ledgers'] += 1
                except OSError as exc:
                    errors.append({'path': child.path, 'error': repr(exc)})
    print(json.dumps(coverage[-1]), flush=True)

for item in added_files:
    source = Path(item['path'])
    data = Path(item['captured_path']).read_bytes()
    if digest(data) != item['sha256']:
        raise ValueError('captured ledger changed')
    pins = []
    for parent_path in (source.parent, source.parent.parent, source.parent.parent.parent):
        for name in ('run_manifest.json', 'manifest.json', 'config.json'):
            path = parent_path/name
            if str(path) in metadata:
                pins.append(metadata[str(path)])
            elif path.is_file():
                metadata[str(path)] = capture(path)
                pins.append(metadata[str(path)])
    item['source_manifests'] = pins
    for line_no, line in enumerate(data.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append({'path': str(source), 'line': line_no, 'error': str(exc)})
            continue
        if not isinstance(row, dict):
            continue
        case = row.get('case') if isinstance(row.get('case'), dict) else {}
        episode = case.get('episode') or row.get('episode') or row.get('result') or {}
        if not isinstance(episode, dict):
            episode = {}
        suite = episode.get('suite', row.get('suite'))
        if suite and suite not in ORIGINAL:
            continue
        for stage_key, stage in stages(row):
            receipt = stage.get('receipt') or {}
            phase = stage.get('private_grasp_phase') or {}
            hold = stage.get('private_setup_hold') or {}
            saved = phase.get('samples') or hold.get('samples') or stage.get('contact_samples') or []
            sample_count_only = saved if type(saved) is int else None
            samples = saved if isinstance(saved, list) and all(isinstance(s, dict) for s in saved) else []
            skill = receipt.get('tool') or str(stage.get('selected', '')).split('(')[0]
            if not (samples or skill in ('grasp', 'regrasp_restage', 'vla_subtask', 'vla_task') or case.get('kind') == 'grasp'):
                continue
            reference = phase.get('reference') or hold.get('reference') or stage.get('initial_private_reference') or row.get('support_reference')
            fields = sorted(set().union(*(set(s) for s in samples))) if samples else []
            records.append({'row_key': f'{source.relative_to(ROOT)}:{line_no}:{stage_key}',
                'input_path': str(source), 'captured_path': item['captured_path'],
                'input_sha256': item['sha256'], 'line': line_no, 'stage_key': stage_key,
                'raw_row_sha256': digest(line), 'case_name': case.get('name'), 'episode': episode,
                'state_identity': row.get('registered_state_sha256', case.get('state_sha256')),
                'category': case.get('object_category', receipt.get('object_category')),
                'method': case.get('condition', row.get('condition', receipt.get('grasp_contact_method', receipt.get('grasp_profile')))),
                'skill': skill, 'source_manifests': pins,
                'old_label': stage.get('private_true_sustained_grasp', phase.get('true_sustained_grasp_during_skill', row.get('true_sustained_grasp'))),
                'old_rule': (stage.get('private_hold_truth_v2') or phase.get('all_supports_v2') or {}).get('support_rule', 'legacy_original_record_retained'),
                'saved_fields': fields, 'sample_count': len(samples), 'legacy_sample_count_only': sample_count_only,
                'reference_saved': bool(reference),
                'full_integration_states_saved': bool(samples) and all('integration_state' in s for s in samples),
                'matching_model_evidence_saved': bool(samples) and any((s.get('counterfactual_support_evidence') or {}).get('model_sha256') for s in samples),
                'truth_labels_in_control': False, 'new_labels_not_computed': True})

output = ''.join(json.dumps(r, sort_keys=True)+'\n' for r in records).encode()
(OUT/'input_rows.jsonl').write_bytes(output)
for name, value in [('input_files.json', files), ('captured_metadata.json', list(metadata.values())),
                    ('additional_root_inventory.json', coverage), ('index_errors.json', errors),
                    ('parent_root_inventory.json', inventory)]:
    (OUT/name).write_text(json.dumps(value, indent=2)+'\n')
report = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'registration_id': 'grasp_truth_v3_1153_20261009', 'parent_index_sha256': parent['index_sha256'],
    'parent_manifest_path': str(OLD/'index_manifest.json'), 'index_sha256': digest(output),
    'files': len(files), 'stage_records': len(records), 'added_ledgers': len(added_files),
    'errors': len(errors), 'exhaustive_claim': False, 'coverage_review_pending': True,
    'index_before_recount': True, 'new_labels_not_computed': True,
    'denominator_unit': 'raw_evidence_stage_not_independent_physical_trial',
    'category_missing': sum(r['category'] is None for r in records),
    'method_missing': sum(r['method'] is None for r in records),
    'state_identity_missing': sum(r['state_identity'] is None for r in records),
    'saved_sample_coverage': dict(Counter(bool(r['sample_count']) for r in records)),
    'parent_inputs_retained_by_immutable_reference': True}
(OUT/'index_manifest.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report), flush=True)
