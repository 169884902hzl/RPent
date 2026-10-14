"""Merge immutable JSON sidecars and ledger evidence before any truth recount."""

import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path

from coordination.enrich_grasp_history_metadata_r9_20261010 import metadata, stages, selected_stage
from coordination.load_indexed_grasp_evidence_20261010 import canonical_object_sha, load_indexed_row


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def evidence_signature(row, stage, index):
    phase = stage.get('private_grasp_phase') or {}
    hold = stage.get('private_setup_hold') or row.get('sustained_hold') or {}
    samples = phase.get('samples') or hold.get('samples') or stage.get('contact_samples') or []
    reference = phase.get('reference') or hold.get('reference') or stage.get('initial_private_reference') or row.get('support_reference')
    if not samples:
        return None
    # Execution directory prevents identical deterministic trajectories from
    # different physical runs being conflated with copies of one saved run.
    execution = row.get('output_dir') or str(Path(index['input_path']).parent)
    return canonical_object_sha({'execution_dir': execution, 'case': row.get('case'),
        'samples': samples, 'reference': reference, 'selected': stage.get('selected'),
        'receipt': stage.get('receipt') or row.get('first_receipt')})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--sidecars', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.index / 'index_manifest.json').read_text())
    payload = (args.index / 'input_rows.jsonl').read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest['index_sha256']:
        raise ValueError('immutable ledger index changed')
    sidecars = json.loads(args.sidecars.read_text())
    if sidecars['errors'] or manifest['errors']:
        raise ValueError('resolve inventory errors before merging evidence')
    rows = [json.loads(line) for line in payload.splitlines()]
    files = json.loads((args.index / 'input_files.json').read_text())
    by_path = {record['path']: record for record in files}
    metadata_records = json.loads((args.index / 'captured_metadata.json').read_text())
    configurations = {}
    cache, aliases, dispositions = {}, {}, []
    for number, index in enumerate(rows, 1):
        raw = load_indexed_row(index, cache)
        stage = selected_stage(raw, index['stage_key'])
        measured = metadata(raw, stage, by_path[index['input_path']])
        for key in ('sample_count', 'saved_fields', 'reference_saved',
                    'full_integration_states_saved', 'matching_model_evidence_saved'):
            index[key] = measured[key]
        signature = evidence_signature(raw, stage, index)
        if signature:
            canonical = aliases.setdefault(signature, index['row_key'])
            index['saved_physical_evidence_sha256'] = signature
            index['saved_physical_evidence_alias_of'] = canonical if canonical != index['row_key'] else None
        if number % 2000 == 0:
            print(json.dumps({'ledger_stages_reviewed': number, 'total': len(rows)}), flush=True)
    for number, item in enumerate(sidecars['records'], 1):
        path = Path(item['captured_path'])
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('captured JSON sidecar changed')
        value = json.loads(data)
        objects = [('', value)] if isinstance(value, dict) else [('/'+str(i), v) for i, v in enumerate(value)] if isinstance(value, list) else []
        added = 0
        related = by_path.get(str(Path(item['path']).parent / 'choices.jsonl'))
        pins = list((related or {}).get('source_manifests', []))
        configs = []
        for record in pins:
            key = record['captured_path']
            if key not in configurations:
                captured = Path(key).read_bytes()
                if hashlib.sha256(captured).hexdigest() != record['sha256']:
                    raise ValueError('captured source metadata changed')
                configurations[key] = json.loads(captured)
            config = configurations[key]
            if isinstance(config, dict):
                configs.append(config)
        for pointer, raw in objects:
            if not isinstance(raw, dict):
                continue
            for stage_key, stage in stages(raw):
                index = {'row_key': item['path']+':json'+pointer+':'+stage_key,
                    'input_path': item['path'], 'captured_path': item['captured_path'],
                    'input_sha256': item['sha256'], 'source_format': 'json',
                    'json_pointer': pointer, 'line': None, 'stage_key': stage_key,
                    'raw_object_sha256': canonical_object_sha(raw),
                    'truth_labels_in_control': False, 'new_labels_not_computed': True}
                derived = metadata(raw, stage, {'source_manifests': pins}, configs)
                index.update(derived)
                index['raw_container_has_first_attempt'] = stage_key == 'row' and isinstance(raw.get('first_attempt'), dict)
                index['container_without_own_samples'] = index['raw_container_has_first_attempt'] and not index['sample_count']
                if index['container_without_own_samples']:
                    index['container_alias_of'] = item['path']+':json'+pointer+':first_attempt'
                signature = evidence_signature(raw, stage, index)
                if signature:
                    canonical = aliases.setdefault(signature, index['row_key'])
                    index['saved_physical_evidence_sha256'] = signature
                    index['saved_physical_evidence_alias_of'] = canonical if canonical != index['row_key'] else None
                rows.append(index)
                added += 1
        if added and item['path'] not in by_path:
            record = {**item, 'source_manifests': pins}
            files.append(record)
            by_path[item['path']] = record
        dispositions.append({'path': item['path'], 'sha256': item['sha256'],
            'indexed_stages': added, 'disposition': 'captured_raw_stage' if added else 'no_grasp_stage'})
        if number % 500 == 0:
            print(json.dumps({'JSON_documents_reviewed': number, 'total': len(sidecars['records'])}), flush=True)
    if len({row['row_key'] for row in rows}) != len(rows):
        raise ValueError('duplicate evidence row key')
    args.output.mkdir(exist_ok=False, parents=True)
    output = ''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows).encode()
    (args.output / 'input_rows.jsonl').write_bytes(output)
    for name, value in (('input_files.json', files), ('captured_metadata.json', metadata_records),
                        ('JSON_sidecar_dispositions.json', dispositions)):
        (args.output / name).write_text(json.dumps(value, indent=2)+'\n')
    report = {**manifest, 'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'parent_index': str(args.index), 'parent_index_sha256': manifest['index_sha256'],
        'index_sha256': hashlib.sha256(output).hexdigest(), 'files': len(files),
        'stage_records': len(rows), 'source_format_counts': dict(Counter(row.get('source_format', 'jsonl') for row in rows)),
        'sidecar_review': pin(args.sidecars), 'producer': pin(Path(__file__)),
        'producer_dependencies': [pin(Path(metadata.__code__.co_filename)),
                                  pin(Path(load_indexed_row.__code__.co_filename))],
        'saved_physical_evidence_alias_records': sum(bool(row.get('saved_physical_evidence_alias_of')) for row in rows),
        'exhaustive_claim': False, 'coverage_review_pending': True,
        'independent_physical_trial_count_not_inferred': True, 'new_labels_not_computed': True}
    (args.output / 'index_manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
