"""Pin a bug-only source and replay the two recorded development decisions."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_skill_budget_20261009_r2'
SOURCE = ROOT / 'source_v5_native_stop_guard_20261009_r2'
OUTPUT = ROOT / 'results/harness_v5/native_stop_replay_20261009_r3'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    patch = ROOT / 'coordination/subtask_native_stop_guard_20261009.patch'
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    identity = json.loads((SOURCE / 'source_snapshot.json').read_text())
    assert identity['patch'] == ref(patch) and identity['archive_complete']
    assert ref(Path(identity['archive']['path'])) == identity['archive']
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if (OUTPUT / 'submission.json').exists():
        print((OUTPUT / 'submission.json').read_text())
        return
    original = ROOT / ('results/harness_v5/skill_budget_20261009_r2/A3-N/'
        'job4828/part0/probe/libero_object_swap_t4_s41')
    config, trace = original / 'config.json', original / 'choices.jsonl'
    cfg = json.loads(config.read_text())
    manifest = {'cases': [{'name': 'object_swap_t4_init41_native_stop',
        'config': str(config), 'config_sha256': ref(config)['sha256'],
        'trace': str(trace), 'trace_sha256': ref(trace)['sha256'],
        'prefix_decisions': 2, 'overrides': {}}],
        'choice_package': cfg['choice_package'], 'source_snapshot': identity,
        'scope': 'development bug reproduction only; not a model score or training row',
        'confirmation': False, 'training_allowed': False}
    plan = OUTPUT / 'manifest.json'
    plan.write_text(json.dumps(manifest, indent=2) + '\n')
    driver = ROOT / 'coordination/replay_v5_native_stop_20261009_r2.py'
    launcher = OUTPUT / 'launcher.sbatch'
    launcher.write_text('''#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=100G
#SBATCH --time=01:00:00
#SBATCH --job-name=native-stop-replay
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
export PYTHONPATH="$NATIVE_SOURCE"
export LIBERO_TYPE=pro LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl PYTHONDONTWRITEBYTECODE=1
cd /tmp
"$ROOT/.venv/bin/python" - <<'CHECK'
import hashlib,json,os
from pathlib import Path
from scripts.replay_v5_original_motion import ReplayScorer
from harness_v5_eval import run_episode
p=Path(os.environ['NATIVE_PLAN'])
assert p.is_absolute() and hashlib.sha256(p.read_bytes()).hexdigest()==os.environ['NATIVE_PLAN_SHA']
m=json.loads(p.read_text())
for item in [m['source_snapshot']['archive'],m['source_snapshot']['patch']]:
    assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
for case in m['cases']:
    for kind in ('config','trace'):
        p=Path(case[kind]); assert p.is_absolute() and p.is_file()
        assert hashlib.sha256(p.read_bytes()).hexdigest()==case[kind+'_sha256']
assert Path(m['choice_package']).exists()
print('CPU_preflight=pass')
CHECK
if [[ "${NATIVE_CPU_ONLY:-0}" == 1 ]]; then exit 0; fi
"$ROOT/.venv/bin/python" -u "$NATIVE_DRIVER" --manifest "$NATIVE_PLAN" \\
 --output "$NATIVE_OUTPUT/job${SLURM_JOB_ID}" --shard-index 0
''')
    environment = {'NATIVE_SOURCE': str(SOURCE), 'NATIVE_PLAN': str(plan),
        'NATIVE_PLAN_SHA': ref(plan)['sha256'], 'NATIVE_OUTPUT': str(OUTPUT),
        'NATIVE_DRIVER': str(driver)}
    check = subprocess.run(['bash', str(launcher)],
        env={**os.environ, **environment, 'NATIVE_CPU_ONLY': '1'},
        capture_output=True, text=True)
    (OUTPUT / 'CPU_preflight.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    command = ['sbatch', '--parsable', '--nice=0',
        '--export=ALL,' + ','.join(k+'='+v for k,v in environment.items()), str(launcher)]
    submitted = subprocess.run(command, text=True, capture_output=True, check=True)
    record = {'job': submitted.stdout.strip(), 'environment': environment,
        'manifest': ref(plan), 'launcher': ref(launcher), 'driver': ref(driver),
        'source_snapshot': ref(SOURCE / 'source_snapshot.json'), 'CPU_preflight': 'pass'}
    (OUTPUT / 'submission.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
