"""Classify preserved public verifier evidence; never change truth labels."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('summary_dir', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
rows_path = args.summary_dir/'rows.jsonl'
rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
cached = {}
counts = Counter()
details = []
for index in rows:
    path = Path(index['input'])
    if path not in cached:
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != index['input_sha256']:
            raise ValueError('physical ledger changed')
        cached[path] = data.splitlines()
    raw = json.loads(cached[path][index['line']-1])
    stage = raw.get('first_attempt') or {}
    measured = stage.get('verification_measurements') or {}
    pair = measured.get('independent_grasp') or {}
    tracking = measured.get('public_target_tracking') or []
    reason = pair.get('reason', 'no_independent_grasp_verifier_evidence')
    counts[(str(index['public']), reason)] += 1
    detail = {'case': index['case'], 'public': index['public'], 'truth': index['registered_v3'],
              'reason': reason, 'pair_evidence': pair,
              'public_tracking_evidence': tracking, 'failure_reason': index['failure_reason'],
              'record_status': index.get('record_status'), 'input': index['input'], 'line': index['line']}
    details.append(detail)
args.output.mkdir(exist_ok=False, parents=True)
(args.output/'details.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in details))
report = {'input_rows': str(rows_path), 'input_sha256': hashlib.sha256(rows_path.read_bytes()).hexdigest(),
          'n': len(rows), 'public_and_reason_counts': [
              {'public': p, 'reason': r, 'n': n} for (p, r), n in counts.items()],
          'private_labels_not_used_to_select_or_alter_verifier': True}
(args.output/'summary.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
