# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Validate completed oracle labels against their exact recorded requests."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--job', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))
from rpent.skill_package.contract import LEGALITY_VERSION, selected, validate_labels  # noqa: E402

root = Path('/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/feasibility_20261017')
records, violations = [], []
for shard in sorted(root.glob('job'+args.job+'_*')):
    for ledger in sorted(shard.glob('*/private_oracle_labels.jsonl')):
        raw = ledger.read_bytes()
        choices = ledger.with_name('choices.jsonl')
        choice_raw = choices.read_bytes()
        rows = [json.loads(line) for line in choice_raw.splitlines()]
        labels = [json.loads(line) for line in raw.splitlines()]
        assert len(rows) == len(labels), (str(ledger), len(rows), len(labels))
        for index, (row, label) in enumerate(zip(rows, labels)):
            try:
                validate_labels(row['request'], label)
                selected(row['request'], row['decision'])
                assert [p['selected'] for p in label['positions']] == row['decision']['candidate_ids']
            except (ValueError, AssertionError) as error:
                violations.append({'ledger': str(ledger), 'index': index, 'error': str(error)})
        records.append({'choices': str(choices), 'choices_sha256': hashlib.sha256(choice_raw).hexdigest(),
            'labels': str(ledger), 'labels_sha256': hashlib.sha256(raw).hexdigest(),
            'requests': len(rows), 'positions': sum(len(x['positions']) for x in labels),
            'judges': sorted({p['judge'] for label in labels for p in label['positions']})})
assert records
report = {'job': args.job, 'source': str(args.source), 'legality_version': LEGALITY_VERSION,
    'requests': sum(x['requests'] for x in records), 'positions': sum(x['positions'] for x in records),
    'violations': violations, 'records': records, 'planner_calls': 0, 'controls': 0,
    'training': False, 'old_records_modified': False}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k: report[k] for k in ('job', 'legality_version', 'requests', 'positions', 'violations')}))
assert not violations
