"""Close a fixed historical inventory using explicit file and pointer coverage."""

import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import shutil

from coordination.enrich_grasp_history_metadata_r9_20261010 import stages
from coordination.load_indexed_grasp_evidence_20261010 import resolve_json_pointer
from coordination.merge_grasp_history_json_sidecars_20261010 import pin


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--content', type=Path, required=True)
    p.add_argument('--named-review', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    manifest = json.loads((a.index / 'index_manifest.json').read_text())
    payload = (a.index / 'input_rows.jsonl').read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest['index_sha256'] or manifest['errors']:
        raise ValueError('index hash or capture errors')
    rows = [json.loads(l) for l in payload.splitlines()]
    exclusions_path = a.index / 'scope_excluded_rows.jsonl'
    excluded = [json.loads(l) for l in exclusions_path.read_text().splitlines()]
    files = json.loads((a.index / 'input_files.json').read_text())
    by_path = {r['path']: r for r in files}
    indexed = {(r['input_path'], r.get('json_pointer', ''), r['stage_key']): r
               for r in rows + excluded if r.get('source_format') == 'json'}
    named = json.loads(a.named_review.read_text())
    if named['input_index_sha256'] != manifest['index_sha256'] or named['named_row_references_missing']:
        raise ValueError('named historical references incomplete')
    review = json.loads((a.content / 'review.json').read_text())
    census_path = Path(manifest['filename_census'])
    census = json.loads(census_path.read_text())
    if (review['errors'] or not review['census_filename_counts_match'] or census['errors']
            or not review['known_JSON_files_reinspected_for_nested_windows']
            or not review['legacy_finger_contact_only_windows_included']):
        raise ValueError('file content scope not fully audited')
    dispositions_path = a.index.parent / 'grasp_truth_registered_v3_history_20261010_r8/remaining_filename_dispositions.json'
    dispositions = json.loads(dispositions_path.read_text())
    if len(dispositions) != len(census['unindexed_jsonl']):
        raise ValueError('JSONL filename dispositions incomplete')
    missing_jsonl = []
    for d in dispositions:
        if d['added_evidence_stages']:
            captured = by_path.get(d['path'])
            if captured is None or captured['sha256'] != d['sha256']:
                missing_jsonl.append(d['path'])
    if missing_jsonl:
        raise ValueError('missing captured JSONL stages: ' + str(missing_jsonl[:5]))
    reviewed_objects, missing_pointers = 0, []
    for line in (a.content / 'unindexed_objects.jsonl').read_text().splitlines():
        document = json.loads(line)
        data = Path(document['captured_path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != document['sha256']:
            raise ValueError('captured JSON content changed')
        value = json.loads(data)
        for obj in document['objects']:
            raw = resolve_json_pointer(value, obj['pointer'])
            selected = [('row', raw)] if isinstance(raw.get('samples'), list) else list(stages(raw)) or [('row', raw)]
            for key, stage in selected:
                record = indexed.get((document['path'], obj['pointer'], key))
                if record is None or record['input_sha256'] != document['sha256']:
                    missing_pointers.append((document['path'], obj['pointer'], key))
                reviewed_objects += 1
    if missing_pointers:
        raise ValueError('unindexed historical JSON objects: ' + str(missing_pointers[:5]))
    inventory_path = Path(census['scope_root_inventory'])
    inventory = json.loads(inventory_path.read_text())
    coverage = {'fixed_inventory': pin(inventory_path), 'root_count': len(inventory),
        'root_dispositions': dict(Counter(str((r.get('included'), r.get('reason'))) for r in inventory)),
        'JSON_content_review': pin(a.content / 'review.json'),
        'JSON_objects_or_stages_reviewed': reviewed_objects, 'missing_JSON_object_stages': [],
        'JSONL_filename_review': pin(census_path), 'JSONL_dispositions': pin(dispositions_path),
        'remaining_JSONL_files_classified': len(dispositions), 'missing_JSONL_captures': [],
        'named_scope_review': pin(a.named_review), 'named_row_references_missing': 0,
        'scope': 'fixed historical original-task grasp evidence inventory; explicit PRO suites excluded; unspecified suites retained as unknown',
        'new_jobs_after_directory_census_not_reclassified_as_historical': True,
        'rows_are_evidence_stages_not_independent_physical_trials': True,
        'new_truth_labels_computed': False, 'producer': pin(Path(__file__))}
    a.output.mkdir(exist_ok=False, parents=True)
    for name in ('input_rows.jsonl', 'scope_excluded_rows.jsonl', 'input_files.json',
                 'JSON_sidecar_dispositions.json', 'nested_JSON_dispositions.json', 'captured_metadata.json'):
        shutil.copyfile(a.index / name, a.output / name)
    (a.output / 'coverage_review.json').write_text(json.dumps(coverage, indent=2) + '\n')
    manifest.update(parent_index=str(a.index), parent_index_sha256=manifest['index_sha256'],
        generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        producer=pin(Path(__file__)), coverage_review=pin(a.output / 'coverage_review.json'),
        source_format_counts=dict(Counter(r.get('source_format', 'jsonl') for r in rows)),
        explicit_non_original_suite_exclusions=len(excluded),
        excluded_suites=dict(Counter((r.get('episode') or {}).get('suite') for r in excluded)),
        suite_unknown_stages=sum(not (r.get('episode') or {}).get('suite') for r in rows),
        exact_evidence_alias_records=sum(bool(r.get('exact_evidence_alias_of')) for r in rows),
        saved_physical_evidence_alias_records=sum(bool(r.get('saved_physical_evidence_alias_of')) for r in rows),
        category_missing=sum(not r.get('category') for r in rows),
        method_missing=sum(not r.get('method') for r in rows),
        state_identity_missing=sum(not r.get('state_identity') for r in rows),
        source_manifest_missing=sum(not r.get('source_manifests') for r in rows),
        scope_exclusions=pin(a.output / 'scope_excluded_rows.jsonl'),
        exhaustive_claim=True, coverage_review_pending=False,
        exhaustive_scope=coverage['scope'], new_labels_not_computed=True)
    (a.output / 'index_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k:manifest[k] for k in ('stage_records', 'files', 'index_sha256',
        'explicit_non_original_suite_exclusions', 'suite_unknown_stages', 'exhaustive_claim')}, indent=2))


if __name__ == '__main__':
    main()
