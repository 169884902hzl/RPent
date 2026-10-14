"""Check named historical inputs and evidence aliases without scoring truth."""
import argparse
from collections import Counter, defaultdict
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
parser = argparse.ArgumentParser()
parser.add_argument('--index', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
manifest = json.loads((args.index/'index_manifest.json').read_text())
data = (args.index/'input_rows.jsonl').read_bytes()
if hashlib.sha256(data).hexdigest() != manifest['index_sha256']:
    raise ValueError('immutable inventory identity changed')
rows = [json.loads(line) for line in data.splitlines()]
files = json.loads((args.index/'input_files.json').read_text())
paths = {row['path'] for row in files}
by_input_line, by_case = defaultdict(list), defaultdict(list)
for row in rows:
    if row.get('line') is not None:
        by_input_line[(row['input_path'], row['line'])].append(row['row_key'])
    if row.get('case_name'):
        by_case[row['case_name']].append(row['row_key'])
scopes = []
for name, relative, expected in (
    ('original_first_physical_confirmation400', 'results/harness_v5/grasp_runtime546_monitor_CPU_20261006/four_class_existing_confirmation/first_physical_cases.jsonl', 400),
    ('contact_selection1000', 'artifacts/contact_methods_intermediate_20261009_r14/attempts.jsonl', 1000)):
    path = ROOT/relative
    payload = path.read_bytes()
    records = [json.loads(line) for line in payload.splitlines() if line.strip()]
    if len(records) != expected:
        raise ValueError('named scope source count changed')
    mapped, missing = [], []
    for record in records:
        ref = record.get('input')
        if ref:
            keys = by_input_line[(ref['path'], ref['line'])]
        else:
            keys = by_case[record['case']]
        entry = {'case': record['case'], 'row_keys': keys}
        (mapped if keys else missing).append(entry)
    scopes.append({'name': name, 'path': str(path),
        'sha256': hashlib.sha256(payload).hexdigest(), 'expected': expected,
        'mapped': len(mapped), 'missing': missing, 'mapped_evidence_references': mapped})
for name, relative in (
    ('moka_original300', 'results/harness_v5/grasp493_moka_comparison_20261005'),
    ('safe_subtask400', 'results/harness_v5/skill516_safe_subtask_exploration_20261005')):
    prefix = str(ROOT/relative)+'/'
    selected_files = [f for f in files if f['path'].startswith(prefix)]
    selected_rows = [r for r in rows if r['input_path'].startswith(prefix)]
    scopes.append({'name': name, 'root': prefix, 'raw_ledgers': len(selected_files),
                  'evidence_stages': len(selected_rows),
                  'case_names': len({r['case_name'] for r in selected_rows if r.get('case_name')}),
                  'planned_counts_are_not_result_denominators': True})
exact_aliases, containers = {}, []
for row in rows:
    exact = (row.get('raw_row_sha256', row.get('raw_object_sha256')), row['stage_key'])
    canonical = exact_aliases.setdefault(exact, row['row_key'])
    if row['stage_key'] == 'row' and not row['sample_count'] and row.get('line') is not None:
        others = [r for r in by_input_line[(row['input_path'], row['line'])]
                  if r.endswith(':first_attempt')]
        if others:
            containers.append({'row_key': row['row_key'], 'first_attempt': others})
report = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'input_index_sha256': manifest['index_sha256'], 'input_stage_records': len(rows),
    'row_keys_unique': len({r['row_key'] for r in rows}) == len(rows),
    'named_scopes': scopes,
    'named_row_references_missing': sum(len(scope.get('missing', [])) for scope in scopes),
    'exact_raw_row_stage_signatures': len(exact_aliases),
    'additional_ledger_aliases': len(rows)-len(exact_aliases),
    'container_rows_with_first_attempt_and_no_own_sample_sequence': containers,
    'missing_metadata': {key: sum(not r.get(key) for r in rows)
                         for key in ('category', 'method', 'state_identity', 'source_manifests')},
    'saved_sample_coverage': dict(Counter(bool(r['sample_count']) for r in rows)),
    'new_labels_computed': False, 'qualification_claim': False,
    'exhaustive_review_complete': False,
    'remaining_review': 'root exclusions, all raw ledger filename families and logical-stage aliases'}
args.output.mkdir(parents=True, exist_ok=False)
(args.output/'coverage_review.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('named_scopes','container_rows_with_first_attempt_and_no_own_sample_sequence')}, indent=2))
