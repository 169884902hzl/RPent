"""Add omitted original roots and stage-level references to immutable r2 bytes.

This inventory never computes a new truth label. Aggregate/leaf copies are
evidence records, not additional independent physical trials.
"""
from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OLD = ROOT / 'coordination/grasp_truth_registered_v3_history_20261010_r2'
OUT = ROOT / 'coordination/grasp_truth_registered_v3_history_20261010_r4'
BASE = ROOT / 'results/harness_v5'
ORIGINAL = {'libero_spatial', 'libero_object', 'libero_goal', 'libero_10', 'libero_90'}
# Explicit original training/skill roots missed by r2's coarse name expression.
EXTRA = {
    'analytic_pose_trace3_20261009_r1', 'analytic_side_route3_20261009_r1',
    'analytic_side_route3_20261009_r2', 'analytic_side_route3_20261009_r3',
    'cf_alphabet_training29_20261001', 'collection25_shared_smoke1_20261001',
    'collective27_shared_smoke1_20261001', 'butter26_shared_smoke1_20261001',
    'book22_shared_smoke1_20261001', 'clause19_shared_smoke1_20261001',
    'drawer20_shared_smoke1_20261001', 'fixture18_shared_smoke2_20261001',
    'fulltask_20261008_r1', 'fulltask_20261008_r2', 'fused_collection152_retry1_20261002',
    'long35_training114_20261001', 'mug_collection92_smoke_20261001', 'mug_training92_20261001',
    'paired_collection_plain_init10_20261001', 'place191_recovery_20261002',
    'recovery112_smoke11_20261001', 'shortpick29_shared_smoke1_20261001',
    'spatial4_training105_20261001', 'spatial4_training108_20261001',
    'table_training99_smoke_20261001', 'table_training_replay99_20261001',
    'white_mug_physical89_20261001', 'white_mug_physical90_20261001',
    'tabletop24_shared_smoke1_20261001', 'table_center97_physical5_20261001',
    'place_hidden37_shared_smoke2_20261001', 'storage_open67_physical5_20261001',
    'binding7_shared_smoke4_20261001', 'binding9_shared_smoke4_20261001',
    'named_fixture14_shared_smoke2_20261001', 'support12_shared_smoke4_20261001',
    'pixel_surface11_shared_smoke4_20261001', 'relational31_shared_smoke1_20261001',
    'visual_binding6_physical20_20261001', 'visual_categories5_physical4_20261001',
    'interim574_20261007/expert', 'interim574_20261007/expert_cached_collective_20261009_r1',
    'interim574_20261007/cached_support_smoke_20261009_r1',
    'fixture540_measured_handle_selection', 'stove555_live_CPU_20261006',
    'stove564_off_physical_development_CPU_20261006',
    'microwave_verified_selection10_20261009_r1', 'microwave_verified_selection10_20261009_r2',
    'native_stop_replay_20261009_r1', 'native_stop_replay_20261009_r2', 'native_stop_replay_20261009_r3',
}
PRUNE = {'frames','images','videos','media','captures','state','states','observation',
         'observations','assets','preparation','preparation_r2','source','__pycache__',
         '.git','logs','empty_memory','perception'}
NAMES = {'episodes.jsonl','choices.jsonl','trials.jsonl','private_grasp.jsonl',
         'oracle_labels.jsonl','private_diagnostics.jsonl','grasp_truth.jsonl'}
UNSAFE = re.compile(r'(libero_(?:spatial|object|goal|10)_(?:task|swap)_t|(?:^|/)(?:A[1-4]|RULE)[-_]|sealed|max160|liberomax)', re.I)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def capture(path):
    raw = path.read_bytes()
    sha = digest(raw)
    dest = OUT / 'inputs' / (sha + path.suffix)
    if not dest.exists():
        dest.write_bytes(raw)
    return {'path': str(path), 'captured_path': str(dest), 'sha256': sha, 'bytes': len(raw)}


def stages(row):
    result = []
    if isinstance(row.get('first_attempt'), dict):
        result.append(('first_attempt', row['first_attempt']))
    for key in ('setup', 'attempts'):
        if isinstance(row.get(key), list):
            for i, obj in enumerate(row[key]):
                if isinstance(obj, dict) and (obj.get('receipt') or obj.get('private_setup_hold')):
                    result.append((f'{key}/{i}', obj))
    if row.get('receipt') or row.get('private_grasp_phase') or row.get('contact_samples') or row.get('grasp_attempted'):
        result.append(('row', row))
    # Aliases within one physical ledger row are references, not extra stages.
    unique, seen = [], set()
    for key, value in result:
        fingerprint = digest(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append((key, value))
    return unique


OUT.mkdir(exist_ok=False)
(OUT / 'inputs').mkdir()
old_manifest = json.loads((OLD / 'index_manifest.json').read_text())
old_rows = (OLD / 'input_rows.jsonl').read_bytes()
if digest(old_rows) != old_manifest['index_sha256']:
    raise ValueError('r2 index changed')
files = json.loads((OLD / 'input_files.json').read_text())
known_paths = {r['path'] for r in files}
errors, boundary = [], []
for root_name in sorted(EXTRA):
    top = BASE / root_name
    if not top.is_dir():
        boundary.append({'path': str(top), 'status': 'not_present'})
        continue
    boundary.append({'path': str(top), 'status': 'explicit_original_root_added'})
    queue = [top]
    while queue:
        directory = queue.pop()
        if UNSAFE.search(str(directory.relative_to(BASE))):
            boundary.append({'path': str(directory), 'status': 'pro_or_sealed_or_max_excluded_without_read'})
            continue
        entries = list(os.scandir(directory))
        leaf = any(e.name == 'choices.jsonl' for e in entries)
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                if not leaf and entry.name not in PRUNE and not entry.name.startswith(('source_', 'step_')):
                    queue.append(Path(entry.path))
            elif entry.is_file(follow_symlinks=False) and entry.name in NAMES and entry.path not in known_paths:
                try:
                    item = capture(Path(entry.path))
                    item['source_manifests'] = []
                    files.append(item)
                    known_paths.add(entry.path)
                except OSError as exc:
                    errors.append({'path': entry.path, 'error': repr(exc)})
    print(json.dumps({'original_root_scanned': root_name, 'input_files': len(files)}), flush=True)

metadata, records, manifest_presence = {}, [], {}
for i, file in enumerate(files):
    data = Path(file['captured_path']).read_bytes()
    if digest(data) != file['sha256']:
        raise ValueError('captured r2/additional source changed')
    source = Path(file['path'])
    manifests = list(file.get('source_manifests', []))
    for parent in (source.parent, source.parent.parent, source.parent.parent.parent):
        for name in ('run_manifest.json', 'manifest.json', 'config.json'):
            path = parent / name
            if str(path) not in manifest_presence:
                manifest_presence[str(path)] = path.is_file()
            if manifest_presence[str(path)] and str(path) not in {x['path'] for x in manifests}:
                manifests.append({'path': str(path)})
    pins = []
    for entry in manifests:
        path = Path(entry['path'])
        if str(path) not in metadata:
            try:
                value = capture(path)
                if entry.get('sha256') and value['sha256'] != entry['sha256']:
                    value['changed_since_r2_metadata_pin'] = True
                metadata[str(path)] = value
            except OSError as exc:
                errors.append({'path': str(path), 'error': repr(exc)})
                continue
        pins.append(metadata[str(path)])
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
        suite = episode.get('suite', row.get('suite'))
        if suite and suite not in ORIGINAL:
            continue
        for key, stage in stages(row):
            receipt = stage.get('receipt') or (row.get('first_receipt') if key == 'row' else {}) or {}
            phase = stage.get('private_grasp_phase') or {}
            hold = stage.get('private_setup_hold') or {}
            samples = phase.get('samples') or hold.get('samples') or stage.get('contact_samples') or []
            # Several legacy producers store only an integer sample count.
            # A count does not establish a saved contact time sequence.
            sample_count_only = samples if type(samples) is int else None
            if not isinstance(samples, list) or any(not isinstance(s, dict) for s in samples):
                samples = []
            tool = receipt.get('tool') or str(stage.get('selected', '')).split('(')[0]
            if not (samples or tool in ('grasp', 'regrasp_restage', 'vla_subtask', 'vla_task') or case.get('kind') == 'grasp'):
                continue
            reference = phase.get('reference') or hold.get('reference') or stage.get('initial_private_reference') or row.get('support_reference')
            fields = sorted(set().union(*(set(s) for s in samples))) if samples else []
            records.append({'row_key': f'{source.relative_to(ROOT)}:{line_no}:{key}',
                'input_path': str(source), 'captured_path': file['captured_path'], 'input_sha256': file['sha256'],
                'line': line_no, 'stage_key': key, 'raw_row_sha256': digest(line),
                'case_name': case.get('name'), 'episode': episode,
                'state_identity': row.get('registered_state_sha256', case.get('state_sha256')),
                'category': case.get('object_category', receipt.get('object_category')),
                'method': case.get('condition', row.get('condition', receipt.get('grasp_contact_method', receipt.get('grasp_profile')))),
                'skill': tool, 'source_manifests': pins,
                'old_label': stage.get('private_true_sustained_grasp', phase.get('true_sustained_grasp_during_skill', row.get('true_sustained_grasp'))),
                'old_rule': (stage.get('private_hold_truth_v2') or phase.get('all_supports_v2') or {}).get('support_rule', 'legacy_original_record_retained'),
                'saved_fields': fields, 'sample_count': len(samples), 'legacy_sample_count_only': sample_count_only,
                'reference_saved': bool(reference),
                'full_integration_states_saved': bool(samples) and all('integration_state' in s for s in samples),
                'matching_model_evidence_saved': bool(samples) and any((s.get('counterfactual_support_evidence') or {}).get('model_sha256') for s in samples),
                'truth_labels_in_control': False, 'new_labels_not_computed': True})
    if i % 500 == 0:
        print(json.dumps({'files_enriched': i, 'stage_records': len(records)}), flush=True)

payload = ''.join(json.dumps(r, sort_keys=True) + '\n' for r in records).encode()
(OUT / 'input_rows.jsonl').write_bytes(payload)
for name, value in [('input_files.json', files), ('captured_metadata.json', list(metadata.values())),
                    ('supplemental_root_inventory.json', boundary), ('index_errors.json', errors)]:
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n')
summary = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'registration_id': 'grasp_truth_v3_1153_20261009', 'parent_index_sha256': old_manifest['index_sha256'],
    'index_sha256': digest(payload), 'files': len(files), 'stage_records': len(records),
    'captured_metadata_files': len(metadata), 'errors': len(errors),
    'exhaustive_claim': False, 'coverage_review_pending': True, 'index_before_recount': True,
    'new_labels_not_computed': True, 'denominator_unit': 'raw_evidence_stage_not_independent_physical_trial',
    'category_missing': sum(r['category'] is None for r in records),
    'method_missing': sum(r['method'] is None for r in records),
    'state_identity_missing': sum(r['state_identity'] is None for r in records),
    'saved_sample_coverage': dict(Counter(bool(r['sample_count']) for r in records)),
    'no_PRO_MAX_or_sealed_assets_read': True}
(OUT / 'index_manifest.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary), flush=True)
