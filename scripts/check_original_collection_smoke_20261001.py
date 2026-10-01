"""Require real physical rows and explicit finish before launching the array."""

import argparse
import importlib.util
import json
import re
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--schema', type=Path, required=True)
    args = p.parse_args()
    spec = importlib.util.spec_from_file_location('collector_smoke_schema', args.schema)
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    ledger = [json.loads(x) for x in (args.output / 'episodes.jsonl').read_text().splitlines()]
    assert len(ledger) == 1
    item = ledger[0]
    result = item['result']
    assert result['correct_finish'] and result['official_success'], result
    episode = Path(item['output_dir'])
    manifest = json.loads((episode / 'training_manifest.json').read_text())
    rows = [json.loads(x) for x in Path(manifest['files']['train']['path']).read_text().splitlines()]
    assert len(rows) >= 2, manifest
    for row in rows:
        assert row['schema_version'] == 'entities-plan-receipt/3.1'
        assert row['question_type'] == 'next_skill' and row['judge'] == 'physics_branch'
        assert row['init_state_index'] == 10 and row['split'] == 'train'
        assert row['prompt_tokens'] <= 3072
        assert row['acceptable_actions']
        codes = set(row['request']['questions']['action']['criteria'])
        assert set(row['acceptable_actions']) <= set(row['evaluated_actions']) <= codes
        assert set(row['unknown_actions']) == codes - set(row['evaluated_actions'])
        visible = json.dumps(row['request'])
        assert not re.search(r'\b(?:obj_|zone_)', visible)
        numbered_names = set(re.findall(r'\b[a-z][a-z_]*_\d+\b', visible))
        assert numbered_names <= {'yaw_90'}, numbered_names
        assert row['base_request_sha256'] == shared.digest(row['request'])
    assert any(any('finish()' == row['request']['questions']['action']['criteria'][code]
                   for code in row['acceptable_actions']) for row in rows), 'explicit finish row absent'
    assert manifest['counts']['premature_finish_negative'] > 0
    assert manifest['counts']['auxiliary'] > 0
    check = {'status': 'PASS', 'episodes': 1, 'valid_next_skill_rows': len(rows),
             'counts': manifest['counts'], 'schema': 'entities-plan-receipt/3.1',
             'request_limit': 3072, 'explicit_finish_present': True,
             'development_or_final_init_overlap': 0, 'rows_checked': len(rows)}
    (args.output / 'smoke_check.json').write_text(json.dumps(check, indent=2) + '\n')
    print(json.dumps(check))


if __name__ == '__main__':
    main()
