"""Add newly captured sidecars and exclude explicitly non-original suites."""

import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path

from coordination.enrich_grasp_history_metadata_r9_20261010 import ORIGINAL, metadata, stages
from coordination.load_indexed_grasp_evidence_20261010 import canonical_object_sha
from coordination.merge_grasp_history_json_sidecars_20261010 import evidence_signature, pin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--sidecars', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.parent / 'index_manifest.json').read_text())
    payload = (args.parent / 'input_rows.jsonl').read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest['index_sha256']:
        raise ValueError('parent index changed')
    review = json.loads(args.sidecars.read_text())
    if review['errors'] or manifest['errors']:
        raise ValueError('unresolved capture errors')
    rows = [json.loads(line) for line in payload.splitlines()]
    files = json.loads((args.parent / 'input_files.json').read_text())
    by_path = {item['path']: item for item in files}
    dispositions = json.loads((args.parent / 'JSON_sidecar_dispositions.json').read_text())
    processed = {item['path'] for item in dispositions}
    excluded = []
    configurations = {}
    for item in review['records']:
        if item['path'] in processed:
            continue
        data = Path(item['captured_path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('new captured sidecar changed')
        value = json.loads(data)
        objects = [('', value)] if isinstance(value, dict) else [('/' + str(i), v) for i, v in enumerate(value)] if isinstance(value, list) else []
        pins = (by_path.get(str(Path(item['path']).parent / 'choices.jsonl')) or {}).get('source_manifests', [])
        configs = []
        for record in pins:
            key = record['captured_path']
            if key not in configurations:
                captured = Path(key).read_bytes()
                if hashlib.sha256(captured).hexdigest() != record['sha256']:
                    raise ValueError('captured metadata changed')
                configurations[key] = json.loads(captured)
            if isinstance(configurations[key], dict):
                configs.append(configurations[key])
        count = 0
        for pointer, raw in objects:
            if not isinstance(raw, dict):
                continue
            for stage_key, stage in stages(raw):
                index = {'row_key': item['path'] + ':json' + pointer + ':' + stage_key,
                    'input_path': item['path'], 'captured_path': item['captured_path'],
                    'input_sha256': item['sha256'], 'source_format': 'json',
                    'json_pointer': pointer, 'line': None, 'stage_key': stage_key,
                    'raw_object_sha256': canonical_object_sha(raw),
                    'truth_labels_in_control': False, 'new_labels_not_computed': True}
                index.update(metadata(raw, stage, {'source_manifests': pins}, configs))
                if stage_key == 'row' and isinstance(raw.get('first_attempt'), dict) and not index['sample_count']:
                    index['container_alias_of'] = item['path'] + ':json' + pointer + ':first_attempt'
                signature = evidence_signature(raw, stage, index)
                if signature:
                    index['saved_physical_evidence_sha256'] = signature
                rows.append(index)
                count += 1
        if count and item['path'] not in by_path:
            files.append({**item, 'source_manifests': pins})
            by_path[item['path']] = files[-1]
        dispositions.append({'path': item['path'], 'sha256': item['sha256'],
            'indexed_stages': count, 'disposition': 'captured_raw_stage' if count else 'no_grasp_stage'})
    retained = []
    for row in rows:
        suite = (row.get('episode') or {}).get('suite')
        if suite and suite not in ORIGINAL:
            excluded.append({**row, 'scope_disposition': 'explicit_non_original_suite',
                             'training_allowed': False, 'new_labels_not_computed': True})
        else:
            row['scope_disposition'] = 'recorded_original_suite' if suite else 'suite_not_saved_unknown'
            retained.append(row)
    aliases, saved = {}, {}
    for row in retained:
        signature = (row.get('raw_row_sha256', row.get('raw_object_sha256')), row['stage_key'])
        canonical = aliases.setdefault(signature, row['row_key'])
        row['exact_evidence_alias_of'] = canonical if canonical != row['row_key'] else None
        signature = row.get('saved_physical_evidence_sha256')
        if signature:
            canonical = saved.setdefault(signature, row['row_key'])
            row['saved_physical_evidence_alias_of'] = canonical if canonical != row['row_key'] else None
    if len({row['row_key'] for row in retained}) != len(retained):
        raise ValueError('duplicate raw stage key')
    args.output.mkdir(parents=True, exist_ok=False)
    data = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in retained).encode()
    (args.output / 'input_rows.jsonl').write_bytes(data)
    (args.output / 'scope_excluded_rows.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in excluded))
    for name, value in [('input_files.json', files), ('JSON_sidecar_dispositions.json', dispositions),
                        ('captured_metadata.json', json.loads((args.parent / 'captured_metadata.json').read_text()))]:
        (args.output / name).write_text(json.dumps(value, indent=2) + '\n')
    report = {**manifest, 'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'parent_index': str(args.parent), 'parent_index_sha256': manifest['index_sha256'],
        'index_sha256': hashlib.sha256(data).hexdigest(), 'stage_records': len(retained), 'files': len(files),
        'source_format_counts': dict(Counter(row.get('source_format', 'jsonl') for row in retained)),
        'explicit_non_original_suite_exclusions': len(excluded),
        'excluded_suites': dict(Counter((row.get('episode') or {})['suite'] for row in excluded)),
        'suite_unknown_stages': sum(not (row.get('episode') or {}).get('suite') for row in retained),
        'scope_exclusions': pin(args.output / 'scope_excluded_rows.jsonl'),
        'sidecar_review': pin(args.sidecars), 'producer': pin(Path(__file__)),
        'category_missing': sum(not row.get('category') for row in retained),
        'method_missing': sum(not row.get('method') for row in retained),
        'state_identity_missing': sum(not row.get('state_identity') for row in retained),
        'source_manifest_missing': sum(not row.get('source_manifests') for row in retained),
        'exact_evidence_alias_records': sum(bool(row.get('exact_evidence_alias_of')) for row in retained),
        'saved_physical_evidence_alias_records': sum(bool(row.get('saved_physical_evidence_alias_of')) for row in retained),
        'exhaustive_claim': False, 'coverage_review_pending': True, 'new_labels_not_computed': True}
    (args.output / 'index_manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:report[k] for k in ('stage_records', 'files', 'index_sha256',
        'explicit_non_original_suite_exclusions', 'excluded_suites', 'suite_unknown_stages')}, indent=2))


if __name__ == '__main__':
    main()
