"""Register twelve complete-state pairs for the joint A1 intervention."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    base = root/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'
    parent = base/'factor6c1de614/preparation/factors12.json'
    plan = json.loads(parent.read_bytes())
    calls_path = base/'A1_CPU_evidence/A1_12_actual_calls.json'
    calls = {r['case']: r['physical_commands'] for r in json.loads(calls_path.read_bytes())}
    pan_path = base/'A1_pan_alignment_r2/preparation/factor.json'
    pan = json.loads(pan_path.read_bytes())['jobs'][0]
    revision = json.loads((args.source/'SOURCE_REVISION.json').read_bytes())
    pro_config = root/'runtime_config/config.yaml'
    original_config = root/'runtime_config_original_20261023/config.yaml'
    plan.update(source=str(args.source), source_commit=revision['commit'], combination_arm=True,
        libero_config=ref(pro_config),
        parent_registration=ref(parent), evaluation_only=True, training=False, confirmation=False,
        A1_calls=ref(calls_path), corrected_pan_registration=ref(pan_path),
        historical_helper_commit='432e4ec8',
        intervention='preposition + recorded local prompt + scripted transport until next policy call; continue transport after policy failure; no A1 coordinates in runtime or training')
    for index, old in enumerate(plan['jobs']):
        row = copy.deepcopy(pan if old['case']['name'] == pan['case']['name'] else old)
        row['kind'] = 'a1_preparation'
        row['a1_physical_commands'] = calls[row['case']['name']]
        row['a1_pi_ordinal'] = row['a1_pi']['A1_ordinal']
        matched = next(c for c in row['a1_physical_commands'] if c['ordinal'] == row['a1_pi_ordinal'])
        assert matched['tool'] == row['a1_pi']['tool']
        assert matched['parameters'] == row['a1_pi']['parameters']
        row['budget']['max_controls'] = 120
        row['budget_scope'] = 'same 24 five-control blocks in both arms; scripts count toward unchanged 10000-step environment budget'
        plan['jobs'][index] = row
    assert len(plan['jobs']) == 12
    out = base/('A1_joint_'+revision['commit'][:8])/'preparation'
    write(out/'pairs12.json', plan)
    write(out/'startup.json', dict(plan, jobs=plan['jobs'][:1]))
    smoke = json.loads((base/'native_model_7f87b8ef/preparation/smoke10.json').read_bytes())
    smoke.update(source=str(args.source), source_commit=revision['commit'], libero_config=ref(original_config))
    write(out/'smoke10.json', smoke)
    commands = ['#!/usr/bin/env bash', 'set -euo pipefail',
        f'export SCHEMA6_SOURCE="{args.source}"', 'export SCHEMA6_CONCURRENCY=8']
    for name, startup in [('smoke10', False), ('startup', True), ('pairs12', False)]:
        config = original_config if name == 'smoke10' else pro_config
        commands.extend([f'export SCHEMA6_LIBERO_CONFIG_PATH="{config.parent}"',
            f'export SCHEMA6_MANIFEST="{out/name}.json"',
            f'export SCHEMA6_OUTPUT="{out.parent/name}"',
            f'export SCHEMA6_STARTUP_ONLY={int(startup)}',
            f'bash "{args.source}/coordination/bounded_skills_20261016/scripts/run_schema6_stage_20261020.sbatch"'])
    (out/'run_pairs.sbatch').write_text('\n'.join(commands)+'\n')
    print(json.dumps({'output': str(out), 'states': 12, 'arms': 2, 'repeats': 3,
        'attempts': 72, 'source': revision['commit'], 'training': False}))


if __name__ == '__main__':
    main()
