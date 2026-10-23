"""Own a capacity-only service mirror without changing the shared C2 service."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

root=Path('/public/home/sunyihan/rpent_libero_eval')
run=root/'results/bounded_skills/next_b_pi_first_20261023'
c2=Path('/public/home/sunyihan/rd_instruction_20260923/c2_next_b_20261022_2030')
source=c2/'service_source';mirror=run/'capacity256_service_source'
proposal=json.loads((run/'CPU_capacity256_proposal/summary.json').read_text())
old=source/'consumer/robot_decider/bounded_choice/serialization.py'
assert hashlib.sha256(old.read_bytes()).hexdigest()==proposal['source']['sha256']
shutil.copytree(source,mirror)
patched=Path(proposal['proposal']['path']);assert hashlib.sha256(patched.read_bytes()).hexdigest()==proposal['proposal']['sha256']
(mirror/'consumer/robot_decider/bounded_choice/serialization.py').write_bytes(patched.read_bytes())
changes=[]
for original in source.rglob('*'):
 if not original.is_file() or '__pycache__' in str(original):continue
 target=mirror/original.relative_to(source)
 if hashlib.sha256(original.read_bytes()).digest()!=hashlib.sha256(target.read_bytes()).digest():changes.append(str(original.relative_to(source)))
assert changes==['consumer/robot_decider/bounded_choice/serialization.py']
metadata={'base_service_source':str(source),'owned_service_source':str(mirror),'changes':changes,
    'proposal':proposal,'adapter_sha256':'253e09f0de4b833e602dcb2abd4e40a2652782485641fbf3b2bb8477830a8af7',
    'endpoint':'http://node02:18075/v1/bounded-choice','shared_service_modified':False}
(run/'preparation/capacity256_service_source.json').write_text(json.dumps(metadata,indent=2))
text=f'''#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-s6-v7-cap256-service
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=80G
#SBATCH --time=06:00:00
#SBATCH --output={root}/results/slurm-%j.log
set -euo pipefail
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1
export PYTHONPATH={mirror}/deps:{mirror}/consumer:{mirror}/service:{mirror}
exec /public/home/sunyihan/robot_decider/runtime/.venv/bin/python {mirror}/serve_priority_b_lora.py --base /public/home/sunyihan/rd_instruction_20260923/v5_models/qwen3_5_4b_851bf6e8 --adapter {c2}/run_job11615/adapter.pt --rows {c2}/dataset_v1/rows.jsonl.gz --schema {mirror}/canonical6/schema.json --schema7 {c2}/canonical7/schema.json --capability6 {c2}/capability6/schema.json --capability7 {c2}/capability7/schema.json --output {run}/capacity256_service_job${{SLURM_JOB_ID}} --port 18075 --project-current-view
'''
p=run/'preparation/capacity256_service.sbatch';p.write_text(text)
job=subprocess.check_output(['sbatch','--parsable',str(p)],text=True).strip()
(run/'preparation/capacity256_service_submission.json').write_text(json.dumps({'job':job,**metadata},indent=2));print(json.dumps({'job':job,**metadata}))
