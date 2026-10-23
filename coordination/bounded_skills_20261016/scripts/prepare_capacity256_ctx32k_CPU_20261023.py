"""Own a context-limit-only service revision after a retained 17,577-token error."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

root=Path('/public/home/sunyihan/rpent_libero_eval');run=root/'results/bounded_skills/next_b_pi_first_20261023'
old=run/'capacity256_service_source';source=run/'capacity256_ctx32k_service_source'
base=Path('/public/home/sunyihan/rd_instruction_20260923/v5_models/qwen3_5_4b_851bf6e8/config.json')
assert json.loads(base.read_text())['text_config']['max_position_embeddings']>=32768
shutil.copytree(old,source)
p=source/'serve_priority_b_lora.py';before=p.read_text();after=before.replace('16384','32768');assert before!=after;p.write_text(after)
changes=[]
for path in old.rglob('*'):
 if not path.is_file() or '__pycache__' in str(path):continue
 target=source/path.relative_to(old)
 if hashlib.sha256(path.read_bytes()).digest()!=hashlib.sha256(target.read_bytes()).digest():changes.append(str(path.relative_to(old)))
assert changes==['serve_priority_b_lora.py']
script=(run/'preparation/capacity256_service.sbatch').read_text().replace('rd-c3-s6-v7-cap256-service','rd-c3-s6-v7-cap256-ctx32k')
script=script.replace(str(old),str(source)).replace('/capacity256_service_job','/capacity256_ctx32k_service_job').replace('--port 18075','--port 18076')
out=run/'preparation/capacity256_ctx32k_service.sbatch';out.write_text(script)
job=subprocess.check_output(['sbatch','--parsable',str(out)],text=True).strip()
metadata={'job':job,'source':str(source),'previous_owned_service':11709,'shared_C2_service_modified':False,
 'endpoint':'http://node02:18076/v1/bounded-choice','max_context_tokens':32768,
 'base_model_max_position_embeddings':262144,'only_service_script_changes_vs_capacity256':changes,
 'service_script_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
 'adapter_sha256':'253e09f0de4b833e602dcb2abd4e40a2652782485641fbf3b2bb8477830a8af7'}
(run/'preparation/capacity256_ctx32k_service_submission.json').write_text(json.dumps(metadata,indent=2));print(json.dumps(metadata))
