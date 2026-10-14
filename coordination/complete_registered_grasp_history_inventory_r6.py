"""Enumerate remaining original-output roots and delivered closed ledgers.

This step pins evidence and exclusions, without computing any new truth.
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
OLD = ROOT/'coordination/grasp_truth_registered_v3_history_20261010_r5'
OUT = ROOT/'coordination/grasp_truth_registered_v3_history_20261010_r6'
INVENTORY = ROOT/'coordination/grasp_truth_registered_v3_history_20261010_r2/top_inventory.json'
ORIGINAL = {'libero_spatial', 'libero_object', 'libero_goal', 'libero_10', 'libero_90'}
PRUNE = {'frames', 'images', 'videos', 'media', 'captures', 'state', 'states',
         'observation', 'observations', 'assets', 'preparation', 'preparation_r2',
         'source', '__pycache__', '.git', 'logs', 'empty_memory', 'perception'}
LEDGERS = {'episodes.jsonl', 'choices.jsonl', 'trials.jsonl', 'private_grasp.jsonl',
           'oracle_labels.jsonl', 'private_diagnostics.jsonl', 'grasp_truth.jsonl'}
FORBIDDEN = re.compile(r'(?i)(?:libero_(?:spatial|object|goal|10)_(?:task|swap)_t|(?:^|/)(?:A[1-4]|RULE)[-_]|sealed|liberomax|max160|human102)')
DERIVED = re.compile(r'(?i)(?:_CPU_|^format\d+_rerender|^v6_(?:delivery|rewrite|fragments|negative|raw)|^prediction|^summary|^rootcauses|^confirmation_(?:exclusion|training)|^token_probe|^resource_update|^training_node|^a[124][-_]|^a1[mn]|^d2_a1|^fixed2323)')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def capture(path):
    data = path.read_bytes()
    sha = digest(data)
    output = OUT/'inputs'/(sha + path.suffix)
    if not output.exists():
        output.write_bytes(data)
    return {'path': str(path), 'captured_path': str(output), 'sha256': sha, 'bytes': len(data)}


def stages(row):
    candidates = [('first_attempt', row['first_attempt'])] if isinstance(row.get('first_attempt'), dict) else []
    for key in ('setup', 'attempts'):
        if isinstance(row.get(key), list):
            candidates.extend((f'{key}/{i}', r) for i, r in enumerate(row[key])
                              if isinstance(r, dict) and (r.get('receipt') or r.get('private_setup_hold')))
    if (row.get('receipt') or row.get('first_receipt') or row.get('private_grasp_phase')
            or row.get('contact_samples') or row.get('grasp_attempted')
            or (row.get('case') or {}).get('kind') == 'grasp'):
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
known = {r['path'] for r in files}
metadata = {r['path']: r for r in json.loads((OLD/'captured_metadata.json').read_text())}
records = [json.loads(line) for line in payload.splitlines()]
row_keys = {r['row_key'] for r in records}
inventory = json.loads(INVENTORY.read_text())
coverage, errors, added = [], [], []
for entry in inventory:
    top = Path(entry['path'])
    covered = any(Path(p).is_relative_to(top) for p in known)
    record = {'path': str(top), 'parent_has_ledger': covered, 'new_ledgers': 0}
    if FORBIDDEN.search(top.name) or DERIVED.search(top.name):
        record['disposition'] = 'excluded_PRO_MAX_sealed_or_derived_nonphysical_root'
        coverage.append(record)
        continue
    record['disposition'] = 'enumerated_original_candidate'
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
            elif child.is_file(follow_symlinks=False) and child.name in LEDGERS and child.path not in known:
                item = capture(Path(child.path))
                files.append(item); added.append(item); known.add(child.path)
                record['new_ledgers'] += 1
    coverage.append(record)
    print(json.dumps(record), flush=True)

# Closed immutable copies named in the Codex1 scope are distinct evidence
# aliases, not independent trials and not substitutes for the source ledgers.
closed = ROOT/'artifacts/empty_aperture_public_replay_20261009_r2/closed_ledgers'
if closed.exists():
    for path in sorted(closed.glob('*.jsonl')):
        if str(path) not in known:
            item = capture(path)
            files.append(item); added.append(item); known.add(str(path))
    coverage.append({'path': str(closed), 'disposition': 'delivered_closed_raw_evidence_aliases'})
else:
    errors.append({'path': str(closed), 'error': 'named_scope_closed_ledgers_unavailable'})

for number, item in enumerate(files, 1):
    source = Path(item['path'])
    data = Path(item['captured_path']).read_bytes()
    if digest(data) != item['sha256']:
        raise ValueError('captured ledger changed')
    pins = list(item.get('source_manifests', []))
    for parent_path in (source.parent, source.parent.parent, source.parent.parent.parent):
        for name in ('run_manifest.json', 'manifest.json', 'config.json'):
            path = parent_path/name
            if str(path) in metadata:
                if str(path) not in {r['path'] for r in pins}:pins.append(metadata[str(path)])
            elif path.is_file():
                metadata[str(path)] = capture(path); pins.append(metadata[str(path)])
    item['source_manifests'] = pins
    for line_no, line in enumerate(data.splitlines(), 1):
        if not line.strip():continue
        try:row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append({'path': str(source), 'line': line_no, 'error': str(exc)})
            continue
        if not isinstance(row, dict):continue
        case = row.get('case') if isinstance(row.get('case'), dict) else {}
        episode = case.get('episode') or row.get('episode') or row.get('result') or {}
        if not isinstance(episode, dict):episode = {}
        suite = episode.get('suite', row.get('suite'))
        if suite and suite not in ORIGINAL:continue
        for stage_key, stage in stages(row):
            row_key = f'{source.relative_to(ROOT)}:{line_no}:{stage_key}'
            if row_key in row_keys:continue
            receipt = stage.get('receipt') or (row.get('first_receipt') if stage_key == 'row' else {}) or {}
            phase = stage.get('private_grasp_phase') or {}
            hold = stage.get('private_setup_hold') or {}
            saved = phase.get('samples') or hold.get('samples') or stage.get('contact_samples') or []
            samples = saved if isinstance(saved, list) and all(isinstance(s, dict) for s in saved) else []
            skill = receipt.get('tool') or str(stage.get('selected', '')).split('(')[0]
            if not (samples or skill in ('grasp', 'regrasp_restage', 'vla_subtask', 'vla_task') or case.get('kind') == 'grasp'):continue
            reference = phase.get('reference') or hold.get('reference') or stage.get('initial_private_reference') or row.get('support_reference')
            fields = sorted(set().union(*(set(s) for s in samples))) if samples else []
            records.append({'row_key': row_key,
                'input_path': str(source), 'captured_path': item['captured_path'],
                'input_sha256': item['sha256'], 'line': line_no, 'stage_key': stage_key,
                'raw_row_sha256': digest(line), 'case_name': case.get('name'), 'episode': episode,
                'state_identity': row.get('registered_state_sha256', case.get('state_sha256')),
                'category': case.get('object_category', receipt.get('object_category')),
                'method': case.get('condition', row.get('condition', receipt.get('grasp_contact_method', receipt.get('grasp_profile')))),
                'skill': skill, 'source_manifests': pins,
                'related_transfer_label': row.get('official_subtask_success'),
                'old_label': stage.get('private_true_sustained_grasp', phase.get('true_sustained_grasp_during_skill', row.get('true_sustained_grasp'))),
                'old_rule': (stage.get('private_hold_truth_v2') or phase.get('all_supports_v2') or {}).get('support_rule', 'legacy_original_record_retained'),
                'saved_fields': fields, 'sample_count': len(samples),
                'legacy_sample_count_only': saved if type(saved) is int else None,
                'reference_saved': bool(reference),
                'full_integration_states_saved': bool(samples) and all('integration_state' in s for s in samples),
                'matching_model_evidence_saved': bool(samples) and any((s.get('counterfactual_support_evidence') or {}).get('model_sha256') for s in samples),
                'truth_labels_in_control': False, 'new_labels_not_computed': True})
            row_keys.add(row_key)
    if number % 100 == 0:print(json.dumps({'added_processed': number, 'stage_records': len(records)}), flush=True)

output = ''.join(json.dumps(r, sort_keys=True)+'\n' for r in records).encode()
(OUT/'input_rows.jsonl').write_bytes(output)
for name, value in [('input_files.json', files), ('captured_metadata.json', list(metadata.values())),
                    ('complete_root_dispositions.json', coverage), ('index_errors.json', errors),
                    ('parent_root_inventory.json', inventory)]:
    (OUT/name).write_text(json.dumps(value, indent=2)+'\n')
report = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'registration_id': 'grasp_truth_v3_1153_20261009', 'parent_index_sha256': parent['index_sha256'],
    'parent_manifest_path': str(OLD/'index_manifest.json'), 'index_sha256': digest(output),
    'files': len(files), 'stage_records': len(records), 'added_ledgers': len(added),
    'errors': len(errors), 'exhaustive_claim': False, 'coverage_review_pending': True,
    'enumeration_completed': True, 'index_before_recount': True, 'new_labels_not_computed': True,
    'denominator_unit': 'raw_evidence_stage_not_independent_physical_trial',
    'category_missing': sum(r['category'] is None for r in records),
    'method_missing': sum(r['method'] is None for r in records),
    'state_identity_missing': sum(r['state_identity'] is None for r in records),
    'saved_sample_coverage': dict(Counter(bool(r['sample_count']) for r in records)),
    'parent_inputs_retained_by_immutable_reference': True}
(OUT/'index_manifest.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report), flush=True)
