"""Prepare the registered PRO40--44 measurement line; do not submit GPUs."""
from pathlib import Path
import hashlib
import json
import subprocess

r = Path('/public/home/sunyihan/rpent_libero_eval')
run = r / 'results/bounded_skills/task_ladder_20261025'
reg = json.loads((run / 'feedback_checkpoint_fix_source.json').read_bytes())
src = Path(reg['remote_source'])
board = run / 'panels5_feedback_checkpoint_r3'
shards = board / 'preparation/pro_measurement_shards.json'
pkg = Path('/public/home/sunyihan/rd_instruction_20260923/c2_next_e_20261024_1300/sidecar_legal8')
config = json.loads((pkg / 'SIDECAR_CONFIG.json').read_bytes())
out = run / 'PRO5_sidecar_preparation'
out.mkdir()
worlds = []
for shard in json.loads(shards.read_bytes()):
    plan = json.loads(Path(shard['manifest']).read_bytes())
    assert plan['source_commit'] == reg['tree']
    assert plan['budget'] == {'decisions': 40, 'sim_steps': 10000, 'wall_s': 7200}
    assert plan['vla_budget']['blocks'] == 104 and plan['vla_budget']['max_controls'] == 520
    for job in plan['jobs']:
        episode = job['case']['episode']
        assert job['panel'] == 'pro_measurement' and episode['seed'] in range(40, 45)
        assert set(job['lines']) == {'oracle', 'model', 'pi'}
        worlds.append(job['world_id'])
assert len(worlds) == len(set(worlds)) == 200
script = f'''#!/bin/bash
#SBATCH --job-name=rd-c3-PRO5-sidecar
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=120G
#SBATCH --time=24:00:00
#SBATCH --array=0-39%1
#SBATCH --output={out}/shard_%A_%a.log
set -euo pipefail
test -f {run}/sidecar_pilot_verified.json
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl PYTHONPATH={src}
export PI05_CHECKPOINT_PATH={r}/assets/pi05 SAM3_CHECKPOINT_PATH={r}/assets/sam3/sam3.pt
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
{config['interpreter']} {pkg}/source/with_selector_sidecar.py --package-root {pkg} --output {out}/selector_${{SLURM_ARRAY_TASK_ID}} -- \\
  {r}/.venv/bin/python {r}/run_ladder_selector_shard_20261025.py --source {src} --shards {shards} --index "${{SLURM_ARRAY_TASK_ID}}" --selector-url '{{SELECTOR_ENDPOINT}}'
'''
p = out / 'run.sbatch'
p.write_text(script)
subprocess.run(['bash', '-n', str(p)], check=True)
record = {'source_tree': reg['tree'], 'board_root': str(board), 'worlds': 200,
    'seeds': [40, 41, 42, 43, 44], 'lines': ['oracle', 'model', 'pi'],
    'script': str(p), 'script_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
    'submitted': False, 'training': False,
    'submission_resource_rule': 'after pilot exit: existing12385 throttle2 + PRO throttle1 <=3 GPU; '
        'after either array completes the other may use up to3; reserve C2 one-card quota',
    'model': 'original A, exact delivered legal8 sidecar; no new weights'}
(out / 'registration.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
