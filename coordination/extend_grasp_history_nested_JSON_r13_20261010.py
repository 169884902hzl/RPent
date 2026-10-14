"""Pin nested historical hold windows without deriving new truth labels."""

import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path

from coordination.enrich_grasp_history_metadata_r9_20261010 import ORIGINAL, metadata, stages
from coordination.load_indexed_grasp_evidence_20261010 import canonical_object_sha, resolve_json_pointer
from coordination.merge_grasp_history_json_sidecars_20261010 import evidence_signature, pin


def context_at(document, pointer):
    current, context, references = document, {}, []
    parts = pointer.split('/')[1:] if pointer else []
    for number in range(len(parts) + 1):
        if isinstance(current, dict):
            context.update(current)
            prefix = '/' + '/'.join(parts[:number]) if number else ''
            for key in ('reference', 'initial_private_reference', 'support_reference'):
                if isinstance(current.get(key), dict):
                    references.append((prefix + '/' + key, current[key]))
        if number < len(parts):
            current = resolve_json_pointer(current, '/' + parts[number])
    return context, references[-1] if references else (None, None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--content', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    parent = json.loads((args.parent / 'index_manifest.json').read_text())
    payload = (args.parent / 'input_rows.jsonl').read_bytes()
    if hashlib.sha256(payload).hexdigest() != parent['index_sha256'] or parent['errors']:
        raise ValueError('parent index identity/errors')
    review = json.loads((args.content / 'review.json').read_text())
    if review['errors'] or not review['census_filename_counts_match']:
        raise ValueError('full JSON census must close without errors')
    rows = [json.loads(line) for line in payload.splitlines()]
    files = json.loads((args.parent / 'input_files.json').read_text())
    files_by_path = {item['path']: item for item in files}
    excluded = [json.loads(line) for line in (args.parent / 'scope_excluded_rows.jsonl').read_text().splitlines()]
    identities = {(r['input_path'], r.get('json_pointer', ''), r['stage_key'])
                  for r in rows + excluded if r.get('source_format') == 'json'}
    dispositions, added, skipped = [], 0, Counter()
    for line in (args.content / 'unindexed_objects.jsonl').read_text().splitlines():
        item = json.loads(line)
        captured = Path(item['captured_path']).read_bytes()
        if hashlib.sha256(captured).hexdigest() != item['sha256']:
            raise ValueError('captured nested JSON changed')
        document = json.loads(captured)
        pins = (files_by_path.get(item['path']) or {}).get('source_manifests', [])
        configs = []
        for record in pins:
            body = Path(record['captured_path']).read_bytes()
            if hashlib.sha256(body).hexdigest() != record['sha256']:
                raise ValueError('captured metadata changed')
            value = json.loads(body)
            if isinstance(value, dict):
                configs.append(value)
        count = 0
        for found in item['objects']:
            pointer = found['pointer']
            raw = resolve_json_pointer(document, pointer)
            context, reference = context_at(document, pointer)
            raw_stages = list(stages(raw))
            if isinstance(raw.get('samples'), list):
                # Direct metrology windows may keep their reference in the
                # parent document. Record its exact pointer and object hash.
                raw_stages = [('row', raw)]
            elif not raw_stages:
                # A historical label-only row is retained as missing raw
                # evidence, never promoted to a new measured truth label.
                raw_stages = [('row', raw)]
            if 'episode' not in context and isinstance(context.get('source_episode'), dict):
                context['episode'] = context['source_episode']
            for stage_key, stage in raw_stages:
                identity = (item['path'], pointer, stage_key)
                if identity in identities:
                    skipped['already_indexed_stage'] += 1
                    continue
                identities.add(identity)
                index = {'row_key': item['path'] + ':json' + pointer + ':' + stage_key,
                    'input_path': item['path'], 'captured_path': item['captured_path'],
                    'input_sha256': item['sha256'], 'source_format': 'json',
                    'json_pointer': pointer, 'line': None, 'stage_key': stage_key,
                    'raw_object_sha256': canonical_object_sha(raw),
                    'truth_labels_in_control': False, 'new_labels_not_computed': True}
                index.update(metadata(context, stage, {'source_manifests': pins}, configs))
                if isinstance(stage.get('samples'), list):
                    samples = stage['samples']
                    if any(not isinstance(s, dict) for s in samples):
                        raise ValueError('invalid direct window schema')
                    index.update(evidence_schema='direct_saved_trace_window' if pointer.endswith('/private_grasp_phase') else 'direct_saved_hold_window', sample_count=len(samples),
                        saved_fields=sorted(set().union(*(set(s) for s in samples))) if samples else [],
                        reference_json_pointer=reference[0],
                        reference_object_sha256=canonical_object_sha(reference[1]) if reference[1] else None,
                        reference_saved=bool(reference[1]),
                        full_integration_states_saved=bool(samples) and all('integration_state' in s for s in samples),
                        matching_model_evidence_saved=any((s.get('counterfactual_support_evidence') or {}).get('model_sha256') for s in samples))
                    old = stage.get('truth') or {}
                    if index['old_label'] is None:
                        index['old_label'] = stage.get('true_sustained_grasp_during_skill', old.get('success'))
                    index['old_direct_truth_fields'] = {key: stage.get(key) for key in
                        ('truth', 'truth_v2', 'truth_v3', 'true_sustained_grasp_at_end') if key in stage}
                    signature = canonical_object_sha({'execution_dir': context.get('output_dir') or str(Path(item['path']).parent),
                        'case': context.get('case'), 'samples': samples, 'reference': reference[1],
                        'selected': stage.get('selected'), 'receipt': stage.get('receipt') or context.get('first_receipt')})
                else:
                    signature = evidence_signature(context, stage, index)
                if signature:
                    index['saved_physical_evidence_sha256'] = signature
                if stage_key == 'row' and isinstance(raw.get('first_attempt'), dict) and not index['sample_count']:
                    index['container_alias_of'] = item['path'] + ':json' + pointer + ':first_attempt'
                suite = (index.get('episode') or {}).get('suite')
                if suite and suite not in ORIGINAL:
                    excluded.append({**index, 'scope_disposition': 'explicit_non_original_suite', 'training_allowed': False})
                else:
                    index['scope_disposition'] = 'recorded_original_suite' if suite else 'suite_not_saved_unknown'
                    rows.append(index)
                count += 1
        if count and item['path'] not in files_by_path:
            record = {k:v for k,v in item.items() if k != 'objects'}
            record['source_manifests'] = pins
            files.append(record)
            files_by_path[item['path']] = record
        added += count
        dispositions.append({'path': item['path'], 'sha256': item['sha256'], 'added_stages': count,
                             'object_pointers_reviewed': len(item['objects'])})
    exact, saved = {}, {}
    for row in rows:
        signature = (row.get('raw_row_sha256', row.get('raw_object_sha256')), row['stage_key'])
        canonical = exact.setdefault(signature, row['row_key'])
        row['exact_evidence_alias_of'] = canonical if canonical != row['row_key'] else None
        signature = row.get('saved_physical_evidence_sha256')
        if signature:
            canonical = saved.setdefault(signature, row['row_key'])
            row['saved_physical_evidence_alias_of'] = canonical if canonical != row['row_key'] else None
    if len({r['row_key'] for r in rows + excluded}) != len(rows) + len(excluded):
        raise ValueError('duplicate row identity')
    args.output.mkdir(exist_ok=False, parents=True)
    data = ''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows).encode()
    (args.output / 'input_rows.jsonl').write_bytes(data)
    (args.output / 'scope_excluded_rows.jsonl').write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in excluded))
    for name, value in [('input_files.json', files), ('nested_JSON_dispositions.json', dispositions),
        ('JSON_sidecar_dispositions.json', json.loads((args.parent / 'JSON_sidecar_dispositions.json').read_text())),
        ('captured_metadata.json', json.loads((args.parent / 'captured_metadata.json').read_text()))]:
        (args.output / name).write_text(json.dumps(value, indent=2) + '\n')
    manifest = {**parent, 'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'parent_index': str(args.parent), 'parent_index_sha256': parent['index_sha256'],
        'index_sha256': hashlib.sha256(data).hexdigest(), 'files': len(files), 'stage_records': len(rows),
        'content_review': pin(args.content / 'review.json'), 'added_nested_or_label_only_stages': added,
        'nested_stage_dispositions': dict(skipped), 'direct_saved_window_stages': sum(r.get('evidence_schema') == 'direct_saved_hold_window' for r in rows),
        'explicit_non_original_suite_exclusions': len(excluded),
        'suite_unknown_stages': sum(not (r.get('episode') or {}).get('suite') for r in rows),
        'producer': pin(Path(__file__)), 'producer_dependencies': [pin(Path(metadata.__code__.co_filename)),
            pin(Path(resolve_json_pointer.__code__.co_filename))], 'exhaustive_claim': False,
        'coverage_review_pending': True, 'new_labels_not_computed': True}
    (args.output / 'index_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k:manifest[k] for k in ('files', 'stage_records', 'index_sha256',
        'added_nested_or_label_only_stages', 'direct_saved_window_stages', 'explicit_non_original_suite_exclusions')}, indent=2))


if __name__ == '__main__':
    main()
