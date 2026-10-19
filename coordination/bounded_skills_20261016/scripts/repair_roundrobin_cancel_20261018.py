"""Restore unstarted tasks using their own submission's pinned identities."""
import hashlib
import json
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
original_path = base/'reports/original20_support_roundrobin_20261018_full_submission.json'
original = json.loads(original_path.read_text())
manifest = Path(original['manifest']['path'])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == original['manifest']['sha256']
plan = json.loads(manifest.read_text())
cancel_path = base/'reports/microwave9248_known_failure_pending_cancel_20261018.json'
cancel = json.loads(cancel_path.read_text())
records = []
for row in cancel['selected']:
    job, index = row['job'].split('_')
    assert job == original['job'] and row['state_before'] == 'PENDING'
    case = plan['cases'][int(index)]
    assert case['name'] != row['case']['name'], 'Re-audit mixed identities rather than assume all mismatched'
    records.append({'original_job': row['job'], 'index': int(index),
        'actual_case': case, 'incorrect_cancellation_label': row['case']['name']})
assert len(records) == 31 and len({r['index'] for r in records}) == 31
tag = 'original20_roundrobin_cancel_repair_20261018'
report = {'scope': 'CPU repair preparation; no GPU submission or physical result',
    'error': 'Cancellation used another manifest index order; actual source uses roundrobin',
    'original_submission': str(original_path), 'cancel_receipt': str(cancel_path),
    'records': records, 'indices': [r['index'] for r in records],
    'expected_case_names': [r['actual_case']['name'] for r in records],
    'original_failures_unchanged': True, 'training': False, 'confirmation': False}
with (base/'reports/roundrobin_cancel_identity_correction_20261018.json').open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
prep = {'source_commit': original['source_commit'], 'snapshot': original['snapshot'],
    'manifest': original['manifest'],
    'preflight': plan.get('preflight'),
    'source_unchanged': True, 'cases_unchanged': True,
    'repair_registration': str(base/'reports/roundrobin_cancel_identity_correction_20261018.json'),
    'physical_validation': 'New same-snapshot launcher startup required before replacement array',
    'training': False, 'confirmation': False}
with (base/'reports'/f'{tag}_preparation.json').open('x') as stream:
    json.dump(prep, stream, indent=2)
    stream.write('\n')
print(json.dumps({'tag': tag, 'source': original['source_commit'], 'n': len(records),
    'indices': ','.join(str(r['index']) for r in records),
    'expected_case_names': ','.join(report['expected_case_names'])}))
