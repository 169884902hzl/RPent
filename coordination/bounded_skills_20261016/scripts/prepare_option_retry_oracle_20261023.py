"""Pin the new forty-case evaluation without changing its cohort or seeds."""
import argparse
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
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    base = root/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'
    revision = json.loads((args.source/'SOURCE_REVISION.json').read_bytes())
    archive = ref(args.archive)
    assert archive['sha256'] == revision['archive_sha256']
    source = revision['commit']
    out = base/('oracle_retry_'+source[:8])/'preparation'
    parent = base/'native_model_09e37883/preparation/oracle_D2_recovery1.json'
    plan = json.loads(parent.read_bytes())
    plan.update(source=str(args.source), source_commit=source, source_archive=archive,
        parent_registration=ref(parent),
        runtime_change='native endpoint accounting; original default full-task budget; '
            'zero-control observation/anchor accounting; least-failed legal VLA retry')
    assert len(plan['jobs']) == 40
    write(out/'D2_recovery1.json', plan)
    for shard in range(2):
        write(out/f'D2_recovery1_shard{shard}.json', dict(plan, jobs=plan['jobs'][shard::2]))
    write(out/'vla_startup.json', dict(plan, jobs=plan['jobs'][:1]))
    smoke_parent = base/'native_model_09e37883/preparation/smoke10.json'
    smoke = json.loads(smoke_parent.read_bytes())
    smoke.update(source=str(args.source), source_commit=source, source_archive=archive,
        parent_registration=ref(smoke_parent))
    write(out/'smoke10.json', smoke)
    phases = [('smoke10', False), ('vla_startup', True)]
    commands = ['#!/usr/bin/env bash', 'set -euo pipefail',
        f'export SCHEMA6_SOURCE="{args.source}"', 'export SCHEMA6_CONCURRENCY=8']
    for name, startup in phases:
        commands.extend([f'export SCHEMA6_MANIFEST="{out/name}.json"',
            f'export SCHEMA6_OUTPUT="{out.parent/name}"',
            f'export SCHEMA6_STARTUP_ONLY={int(startup)}',
            f'bash "{args.source}/coordination/bounded_skills_20261016/scripts/run_schema6_stage_20261020.sbatch"'])
    (out/'run_panels.sbatch').write_text('\n'.join(commands)+'\n')
    print(json.dumps({'output': str(out), 'source': source, 'states': 40,
        'recovery_budget': 1, 'training': False, 'source_archive': archive}))


if __name__ == '__main__':
    main()
