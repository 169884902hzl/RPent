"""Recount registered oracle cohorts, including exact same-source reuse."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


def summarize(root, tag):
    reports = root / 'coordination/bounded_skills_20261016/reports'
    receipt_path = reports / (tag + '_full_submission.json')
    receipt = json.loads(receipt_path.read_text())
    manifest = Path(receipt['manifest']['path'])
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == receipt['manifest']['sha256']
    cases = json.loads(manifest.read_text())['cases']
    entries = [(cases[index], root / 'results/bounded_skills/feasibility_20261017'
        / ('job' + receipt['job'] + '_' + str(index)) / 'episodes.jsonl')
        for index in receipt['indices']]
    for reuse in receipt.get('same_source_state_reuse', []):
        assert reuse['arm'] == 'oracle_k4' and cases[reuse['index']] == reuse['case']
        entries.append((reuse['case'], Path(reuse['record'])))
    identities = {(case['bddl']['sha256'], case['state_sha256']) for case, _ in entries}
    assert len(identities) == len(entries) == receipt['registered_unique_states']
    sys.path.insert(0, receipt['snapshot'])
    from scripts.summarize_bounded_probes import feasibility

    complete, pending, errors, files = [], [], [], []
    for case, path in entries:
        rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        selected = [row for row in rows if row.get('status') == 'physical_result'
                    and row['arm'] == 'oracle_k4']
        assert len(selected) <= 1
        errors.extend(dict(case=case, record=str(path), error=row) for row in rows
            if row.get('status') not in {'physical_result', 'startup_physical'})
        if not selected:
            pending.append(dict(case=case, record=str(path)))
            continue
        row, = selected
        assert row['case'] == case and row['pi05_calls'] == 0 and not row['training']
        complete.append(dict(record=str(path), **row))
        files.append(path)
    # Reuse the source's metric implementation. Legacy arms in reused ledgers
    # remain hashed inputs, but cannot enter the oracle-only denominator.
    metrics = feasibility(files)
    cohorts = [group for group in metrics['summary'] if group['arm'] == 'oracle_k4']
    return dict(source_commit=receipt['source_commit'], snapshot=receipt['snapshot'],
        registered_states=len(entries), completed_states=len(complete),
        success=sum(row['success'] for row in complete),
        registered_by_category=dict(Counter(case['category'] for case, _ in entries)),
        cohorts=cohorts, rows=complete, pending=pending, execution_errors=errors,
        raw_ledgers=metrics['sources'], submission=str(receipt_path),
        submission_sha256=hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        metrics_script_sha256=hashlib.sha256((Path(receipt['snapshot'])
            / 'scripts/summarize_bounded_probes.py').read_bytes()).hexdigest(),
        scope='original-state oracle K4 development; pi0.5 disabled; no unfinished state scored',
        historical_label='box_transfer is alphabet-soup can; box_grab_place is actual cream-cheese box',
        training=False, confirmation=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('/public/home/sunyihan/rpent_libero_eval'))
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    report = summarize(args.root, args.tag)
    output = args.root / 'coordination/bounded_skills_20261016/reports' / (args.tag + '_progress.json')
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('registered_states', 'completed_states', 'success', 'cohorts')}))
