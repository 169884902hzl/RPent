"""Publish explicit replacements for missing private metrology, without new trials."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    a = p.parse_args()
    root = a.root
    base = root/'results/bounded_skills/next_b_pi_first_20261023/train_dagger_once_priority1'
    source = root/'source_pi_first_origin_f6ce1d46_20261023'

    def run(shard):
        plan_path = base/'preparation'/('pilot32_catalog_r3.json' if shard == 0 else f'bulk_shard{shard:03d}.json')
        plan = json.loads(plan_path.read_text())
        helpers = json.loads((base/'preparation/bulk_shard001.json').read_text())
        for key in ('measurement_helper', 'prompt_helper', 'registration_entry'):
            plan.setdefault(key, helpers[key])
        output = base/'CPU_support_completed_r4'/f'shard{shard:03d}'
        output.parent.mkdir(exist_ok=True)
        if not (output/'manifest.json').exists():
            with (output.parent/f'shard{shard:03d}.log').open('w') as stream:
                subprocess.run([sys.executable, str(root/'repair_train_support_CPU_20261023.py'),
                    '--root', str(root), '--shard', str(shard), '--output', str(output)],
                    check=True, stdout=stream, stderr=subprocess.STDOUT)
        completion = json.loads((output/'manifest.json').read_text())
        assert not completion['partial_probe']
        if not completion['corrected_trials']:
            return
        assert len(list(output.glob('closed_*.json'))) == len(plan['jobs'])
        for row in completion['rows']:
            original_choices = Path(row['old_trial']['path']).parent/'choices.jsonl'
            retained_choices = Path(row['corrected_trial']['path']).parent/'choices.jsonl'
            if not retained_choices.exists():
                retained_choices.symlink_to(original_choices)
            assert ref(retained_choices)['sha256'] == ref(original_choices)['sha256']
        old = (base/'CPU_pilot32_closed/manifest.json' if shard == 0 else
            next((base/'exports').glob(f'shard{shard:03d}_job*/manifest.json')))
        export = base/'exports'/f'shard{shard:03d}_support_completed_r4'
        if not (export/'manifest.json').exists():
            subprocess.run([sys.executable, plan['measurement_exporter']['path'], '--source', str(source),
                '--manifest', str(plan_path), '--results', str(output),
                '--policy-hashes', str(root/'results/bounded_skills/execution_repairs_20261022/qualified90_9716b68c/preparation/registered_pi05_hashes.sha256'),
                '--measurement-helper', plan['measurement_helper']['path'],
                '--prompt-helper', plan['prompt_helper']['path'], '--output', str(export)], check=True,
                stdout=subprocess.DEVNULL)
        path = export/'manifest.json'
        value = json.loads(path.read_text())
        old_value = json.loads(old.read_text())
        assert value['raw_closed'] == old_value['raw_closed']
        assert value['bound_trials'] >= old_value['bound_trials']
        assert value['positions'] == old_value['positions']
        value.update(supersedes_packet=ref(old), private_support_completion=ref(output/'manifest.json'),
            merge_rule='replace old packet; same policy trials with missing private interventions completed; never concatenate as new repeats')
        path.write_text(json.dumps(value, indent=2)+'\n')
        notice = f'C3_DAGGER_ONCE_shard{shard:03d}_SUPPORT_COMPLETED_R4_20261023'
        if not (root/'coordination/owner_alerts/Codex2'/f'{notice}.json').exists():
            subprocess.run([sys.executable, plan['registration_entry']['path'], '--package', str(export),
                '--name', notice], check=True, stdout=subprocess.DEVNULL)
        print(json.dumps({'shard': shard, 'corrected_trials': completion['corrected_trials'],
            'old_known': old_value['bound_trials'], 'new_known': value['bound_trials'],
            'unknown_remaining': value['unknown_trials'], 'package': ref(path)}), flush=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, range(7)))


if __name__ == '__main__':
    main()
