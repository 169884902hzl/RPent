"""Verify saved controls against the current original-state manifest on CPU."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def state_key(case):
    episode = case['episode']
    return (episode['suite'], episode['task'], episode['seed'],
            case['state_sha256'], case['bddl']['sha256'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path,
        help='Current original220 manifest; compare identities independently of order')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reports = args.root/'coordination/bounded_skills_20261016/reports'
    manifest = (args.manifest or args.root/
        'results/bounded_skills/feasibility_20261017/preparation/original20_manifest_chunk_v3_prefix_checks_20261018.json').resolve(strict=True)
    plan = json.loads(manifest.read_text())
    expected = Counter(state_key(case) for case in plan['cases'])
    registered = {state_key(case): case for case in plan['cases']}
    assert len(expected) == 220 and all(count == 1 for count in expected.values())
    file_checks = {}

    def check_file(source):
        path = Path(source['path'])
        if str(path) not in file_checks:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual == source['sha256'], str(path)
            file_checks[str(path)] = dict(sha256=actual, matched=True)

    controls = {}
    paired = {}
    for name in ('pi05_7528', 'legacy220'):
        report_path = reports/(name+'.json')
        report = json.loads(report_path.read_text())
        rows = report['rows']
        actual = Counter(state_key(row['case']) for row in rows)
        assert actual == expected, name+' state set mismatch'
        raw = []
        for source in report['sources']:
            check_file(source)
            raw.extend(json.loads(line) for line in Path(source['path']).read_text().splitlines())
        physical = [row for row in raw if row.get('status') == 'physical_result']
        assert len(physical) == len(rows) == 220
        by_key = {state_key(row['case']): row for row in physical}
        assert len(by_key) == len(physical)
        for row in rows:
            saved = by_key[state_key(row['case'])]
            for field in ('arm', 'success', 'decisions', 'sim_steps', 'wall_s'):
                assert row[field] == saved[field], (name, row['case']['name'], field)
            assert row['training'] is False
            for source in row.get('source_files', []):
                check_file(source)
        renamed = [dict(state_key=list(state_key(row['case'])),
            saved_name=row['case']['name'], current_name=registered[state_key(row['case'])]['name'],
            saved_category=row['case']['category'], current_category=registered[state_key(row['case'])]['category'])
            for row in rows if any(row['case'][field] != registered[state_key(row['case'])][field]
                for field in ('name', 'category'))]
        groups = {}
        for category in sorted({case['category'] for case in registered.values()}):
            selected = [row for row in rows if registered[state_key(row['case'])]['category'] == category]
            groups[category] = dict(n=len(selected), success=sum(row['success'] for row in selected))
        controls[name] = dict(report=str(report_path),
            report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),
            n=len(rows), success=sum(row['success'] for row in rows),
            identical_state_set=True, raw_fields_matched=True, categories=groups,
            renamed_labels=renamed,
            missing_sim_steps=sum(row.get('sim_steps') is None for row in rows),
            original90_adapter_rows=sum(bool(row.get('original90_diagnostic_admission_adapter')) for row in rows))
        paired[name] = {state_key(row['case']): row['success'] for row in rows}
    pair_counts = Counter((paired['legacy220'][key], paired['pi05_7528'][key]) for key in expected)
    output = dict(time_pacific=datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
        manifest=str(manifest), manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        controls=controls, verified_files=file_checks,
        pairing=dict(both_success=pair_counts[True, True], both_failed=pair_counts[False, False],
            pi05_only_success=pair_counts[False, True], legacy_only_success=pair_counts[True, False]),
        caveats=['pi05 decisions count inference blocks; expert decisions count skill selections.',
            'LIBERO-90 adapter is a diagnostic extension and is reported separately.',
            'Source code, receipt and measurement semantics differ from the new bounded oracle.',
            'Missing historical sim_steps remain null; they are not reconstructed here.'],
        training=False, confirmation=False)
    args.output.write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({key: output[key] for key in ('controls', 'pairing')}, indent=2))


if __name__ == '__main__':
    main()
