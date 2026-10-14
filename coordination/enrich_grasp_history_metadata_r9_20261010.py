"""Backfill recorded metadata and pin missed ledgers; compute no truth labels."""

from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'coordination/grasp_truth_registered_v3_history_20261010_r6'
AUDIT = ROOT / 'coordination/grasp_history_remaining_files_r8_20261010/review.json'
OUT = ROOT / 'coordination/grasp_truth_registered_v3_history_20261010_r8'
FAILED_CACHE = ROOT / 'coordination/grasp_truth_registered_v3_history_20261010_r7/inputs'
ORIGINAL = {'libero_spatial', 'libero_object', 'libero_goal', 'libero_10', 'libero_90'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stages(row):
    if isinstance(row.get('first_attempt'), dict):
        yield 'first_attempt', row['first_attempt']
    for key in ('setup', 'attempts'):
        for number, value in enumerate(row.get(key) or []):
            if isinstance(value, dict) and (value.get('receipt') or value.get('private_setup_hold')):
                yield f'{key}/{number}', value
    if (row.get('receipt') or row.get('first_receipt') or row.get('private_grasp_phase')
            or row.get('contact_samples') or row.get('grasp_attempted')):
        yield 'row', row


def selected_stage(row, key):
    if key == 'row':
        return row
    if key == 'first_attempt':
        return row.get('first_attempt') or {}
    name, position = key.split('/')
    return row[name][int(position)]


def recorded_category(name):
    if not isinstance(name, str):
        return None
    name = name.lower().replace('_', ' ')
    for category, terms in (('moka pot', ('moka',)), ('frypan', ('frypan', 'frying pan')),
                            ('bowl', ('bowl',)), ('cup', ('mug', 'cup')),
                            ('bottle', ('bottle', 'wine')), ('box', ('box',))):
        if any(term in name for term in terms):
            return category
    return None


def metadata(row, stage, item, configs=()):
    case = row.get('case') if isinstance(row.get('case'), dict) else {}
    receipt = stage.get('receipt') or (row.get('first_receipt') if stage is row else {}) or {}
    episode = case.get('episode') or row.get('episode') or row.get('result') or {}
    if not isinstance(episode, dict):
        episode = {}
    episode = {key: value for key, value in episode.items() if key in ('suite', 'task', 'seed')}
    for config in configs:
        recorded = config.get('episode') or config
        if isinstance(recorded, dict):
            for key in ('suite', 'task', 'seed'):
                if episode.get(key) is None and recorded.get(key) is not None:
                    episode[key] = recorded[key]
    obj = receipt.get('object')
    public_entities = stage.get('public_before') or row.get('measurements') or []
    if isinstance(public_entities, dict):
        public_entities = public_entities.get('entities', [])
    if not isinstance(public_entities, list):
        public_entities = []
    names = {value.get('name') for value in public_entities
             if isinstance(value, dict) and value.get('id') == obj and value.get('name')}
    name = next(iter(names)) if len(names) == 1 else None
    if not name and isinstance(row.get('selected_public_entity'), dict):
        name = row['selected_public_entity'].get('name')
    category = case.get('object_category') or case.get('category') or receipt.get('object_category')
    category_source = 'recorded_case_or_receipt' if category else None
    if not category:
        category = recorded_category(name)
        if category:
            category_source = 'recorded_public_entity_name'
    phase = stage.get('private_grasp_phase') or {}
    hold = stage.get('private_setup_hold') or (row.get('sustained_hold') if stage is row else {}) or {}
    saved = phase.get('samples') or hold.get('samples') or stage.get('contact_samples') or []
    samples = saved if isinstance(saved, list) and all(isinstance(s, dict) for s in saved) else []
    return {'case_name': case.get('name', row.get('case') if isinstance(row.get('case'), str) else None),
            'episode': episode, 'object_name_recorded': name,
            'category': category, 'category_source': category_source,
            'method': case.get('condition', row.get('condition', receipt.get('grasp_contact_method', receipt.get('grasp_profile')))),
            'recorded_skill_mode': {'tool': receipt.get('tool'), 'mode': receipt.get('mode'),
                                    'grasp_profile': receipt.get('grasp_profile')},
            'skill': receipt.get('tool') or str(stage.get('selected', '')).split('(')[0],
            'state_identity': row.get('registered_state_sha256', case.get('state_sha256')),
            'original_episode_key': {k: episode[k] for k in ('suite', 'task', 'seed') if k in episode},
            'stratum': 'registered_layout_perturbation' if case.get('registered_layout_state') or case.get('layout_seed') is not None
                       else 'original_or_unspecified_saved_metadata',
            'source_manifests': item.get('source_manifests', []),
            'old_label': stage.get('private_true_sustained_grasp', phase.get('true_sustained_grasp_during_skill', row.get('true_sustained_grasp'))),
            'old_rule': (stage.get('private_hold_truth_v2') or phase.get('all_supports_v2') or {}).get('support_rule', 'legacy_original_record_retained'),
            'sample_count': len(samples), 'saved_fields': sorted(set().union(*(set(s) for s in samples))) if samples else [],
            'reference_saved': bool(phase.get('reference') or hold.get('reference') or stage.get('initial_private_reference') or row.get('support_reference')),
            'full_integration_states_saved': bool(samples) and all('integration_state' in s for s in samples),
            'matching_model_evidence_saved': bool(samples) and any((s.get('counterfactual_support_evidence') or {}).get('model_sha256') for s in samples)}


def main():
    manifest = json.loads((PARENT / 'index_manifest.json').read_text())
    raw_index = (PARENT / 'input_rows.jsonl').read_bytes()
    if digest(raw_index) != manifest['index_sha256']:
        raise ValueError('immutable parent index changed')
    audit = json.loads(AUDIT.read_text())
    if audit['errors']:
        raise ValueError('resolve filename census errors before producing the complete index')
    OUT.mkdir(exist_ok=False)
    (OUT / 'inputs').mkdir()
    files = json.loads((PARENT / 'input_files.json').read_text())
    manifests = json.loads((PARENT / 'captured_metadata.json').read_text())
    manifest_by_path = {record['path']: record for record in manifests}
    configs_by_ledger = {}
    parsed_manifests = {}
    checked_manifest_paths = set(manifest_by_path)
    by_path = {item['path']: item for item in files}
    rows = [json.loads(line) for line in raw_index.splitlines()]
    row_keys = {row['row_key'] for row in rows}
    dispositions, errors = [], []
    for candidate_number, candidate in enumerate(audit['unindexed_jsonl'], 1):
        source = Path(candidate['path'])
        data = source.read_bytes()
        file_sha = digest(data)
        new = []
        for number, line in enumerate(data.splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError as exc:
                errors.append({'path': str(source), 'line': number, 'error': str(exc)})
                continue
            if not isinstance(row, dict):
                continue
            for key, stage in stages(row):
                receipt = stage.get('receipt') or row.get('first_receipt') or {}
                case = row.get('case') if isinstance(row.get('case'), dict) else {}
                ep = case.get('episode') or row.get('episode') or row.get('result') or {}
                if isinstance(ep, dict) and ep.get('suite') and ep['suite'] not in ORIGINAL:
                    continue
                if not (stage.get('private_grasp_phase') or stage.get('private_setup_hold') or stage.get('contact_samples')
                        or stage.get('grasp_attempted') or receipt.get('tool') in ('grasp', 'regrasp_restage', 'vla_subtask', 'vla_task')):
                    continue
                row_key = f'{source.relative_to(ROOT)}:{number}:{key}'
                if row_key not in row_keys:
                    new.append({'row_key': row_key, 'input_path': str(source), 'input_sha256': file_sha,
                                'line': number, 'stage_key': key, 'raw_row_sha256': digest(line),
                                'truth_labels_in_control': False, 'new_labels_not_computed': True})
                    row_keys.add(row_key)
        if new:
            cached = FAILED_CACHE / (file_sha + '.jsonl')
            captured = cached if cached.is_file() else OUT / 'inputs' / (file_sha + '.jsonl')
            if not captured.exists():
                captured.write_bytes(data)
            item = {'path': str(source), 'captured_path': str(captured), 'sha256': file_sha,
                    'bytes': len(data), 'source_manifests': []}
            files.append(item)
            by_path[str(source)] = item
            for row in new:
                row['captured_path'] = str(captured)
            rows.extend(new)
        dispositions.append({'path': str(source), 'sha256': file_sha, 'bytes': len(data),
                             'added_evidence_stages': len(new),
                             'disposition': 'captured_grasp_evidence' if new else 'no_additional_raw_grasp_stage'})
        if candidate_number % 100 == 0:
            print(json.dumps({'filename_records_processed': candidate_number,
                              'total': len(audit['unindexed_jsonl']), 'stages': len(rows)}), flush=True)
    for item in files:
        pins = list(item.get('source_manifests', []))
        source = Path(item['path'])
        for parent in (source.parent, source.parent.parent, source.parent.parent.parent):
            for filename in ('run_manifest.json', 'manifest.json', 'config.json'):
                path = parent / filename
                if str(path) not in checked_manifest_paths:
                    checked_manifest_paths.add(str(path))
                    if path.is_file():
                        data = path.read_bytes()
                        captured = OUT / 'inputs' / (digest(data) + '.json')
                        if not captured.exists():
                            captured.write_bytes(data)
                        record = {'path': str(path), 'captured_path': str(captured),
                                  'sha256': digest(data), 'bytes': len(data)}
                        manifests.append(record)
                        manifest_by_path[str(path)] = record
                if str(path) in manifest_by_path and str(path) not in {p['path'] for p in pins}:
                    pins.append(manifest_by_path[str(path)])
        # Older indexes store compact path/SHA references here. Resolve each
        # reference to the already captured, hash-matching metadata record.
        resolved = []
        for record in pins:
            full = manifest_by_path.get(record['path'])
            if full is None or full['sha256'] != record['sha256']:
                raise ValueError(f"missing or changed source metadata: {record['path']}")
            resolved.append(full)
        pins = resolved
        item['source_manifests'] = pins
        configs = []
        for record in pins:
            if record['captured_path'] not in parsed_manifests:
                data = Path(record['captured_path']).read_bytes()
                if digest(data) != record['sha256']:
                    raise ValueError('captured source manifest changed')
                parsed_manifests[record['captured_path']] = json.loads(data)
            config = parsed_manifests[record['captured_path']]
            if isinstance(config, dict):
                configs.append(config)
        configs_by_ledger[item['path']] = configs
    last, lines, backfilled = None, [], Counter()
    aliases = {}
    for number, index in enumerate(rows, 1):
        item = by_path[index['input_path']]
        if item['captured_path'] != last:
            payload = Path(item['captured_path']).read_bytes()
            if digest(payload) != item['sha256']:
                raise ValueError('captured input changed')
            lines, last = payload.splitlines(), item['captured_path']
        line = lines[index['line'] - 1]
        if digest(line) != index['raw_row_sha256']:
            raise ValueError('captured raw row changed')
        row = json.loads(line)
        stage = selected_stage(row, index['stage_key'])
        derived = metadata(row, stage, item, configs_by_ledger[item['path']])
        for key, value in derived.items():
            if not index.get(key) and value is not None:
                index[key] = value
                backfilled[key] += 1
        index['raw_container_has_first_attempt'] = index['stage_key'] == 'row' and isinstance(row.get('first_attempt'), dict)
        index['container_without_own_samples'] = index['raw_container_has_first_attempt'] and not index['sample_count']
        index['evidence_alias_signature'] = digest((index['raw_row_sha256'] + ':' + index['stage_key']).encode())
        canonical = aliases.setdefault(index['evidence_alias_signature'], index['row_key'])
        index['exact_evidence_alias_of'] = canonical if canonical != index['row_key'] else None
        if index['stage_key'] == 'row' and isinstance(row.get('first_attempt'), dict):
            child = row['first_attempt']
            same_phase = stage.get('private_grasp_phase') and stage.get('private_grasp_phase') == child.get('private_grasp_phase')
            if same_phase or index['container_without_own_samples']:
                prefix = index['row_key'].rsplit(':', 1)[0]
                index['container_alias_of'] = prefix + ':first_attempt'
        if number % 1000 == 0:
            print(json.dumps({'metadata_rows_processed': number, 'total': len(rows)}), flush=True)
    payload = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()
    (OUT / 'input_rows.jsonl').write_bytes(payload)
    for name, data in [('input_files.json', files), ('captured_metadata.json', manifests),
                       ('remaining_filename_dispositions.json', dispositions),
                       ('index_errors.json', errors), ('backfilled_fields.json', dict(backfilled))]:
        (OUT / name).write_text(json.dumps(data, indent=2) + '\n')
    report = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'registration_id': manifest['registration_id'], 'parent_index': str(PARENT),
              'parent_index_sha256': manifest['index_sha256'], 'index_sha256': digest(payload),
              'files': len(files), 'stage_records': len(rows), 'errors': len(errors),
              'backfilled_fields': dict(backfilled), 'filename_census': str(AUDIT),
              'filename_census_sha256': digest(AUDIT.read_bytes()),
              'category_missing': sum(not row.get('category') for row in rows),
              'object_name_missing': sum(not row.get('object_name_recorded') for row in rows),
              'method_missing': sum(not row.get('method') for row in rows),
              'state_identity_missing': sum(not row.get('state_identity') for row in rows),
              'source_manifest_missing': sum(not row.get('source_manifests') for row in rows),
              'exact_evidence_alias_records': sum(bool(row.get('exact_evidence_alias_of')) for row in rows),
              'container_alias_records': sum(bool(row.get('container_alias_of')) for row in rows),
              'exhaustive_claim': False, 'coverage_review_pending': True,
              'new_labels_not_computed': True, 'index_before_recount': True,
              'metadata_inferred_from_state_hash_or_old_label': False,
              'denominator_unit': 'raw_evidence_stage_not_independent_physical_trial'}
    (OUT / 'index_manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
