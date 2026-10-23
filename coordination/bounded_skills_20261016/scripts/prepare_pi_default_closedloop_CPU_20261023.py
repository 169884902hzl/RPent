"""Use C2's registered, train-calibrated pi-default service on the same46 arms."""
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import urlopen

root=Path('/public/home/sunyihan/rpent_libero_eval')
run=root/'results/bounded_skills/next_b_pi_first_20261023'
c2=Path('/public/home/sunyihan/rd_instruction_20260923/c2_pi_default_20261023_0150')
prep=run/'preparation'
ready=c2/'service_job11721/service_ready.json'
registered=json.loads(ready.read_bytes())
endpoint=registered['endpoint']
with urlopen(endpoint.rsplit('/',2)[0]+'/healthz',timeout=30) as f:health=json.load(f)
assert health['status']=='ok'
assert health['selection_policy']=={'version':'pi-whole-task-margin/1','enabled':True,'delta':2.0}
assert health['adapter_sha256']==registered['adapter_sha256']=='5825fe0f4a29a268483413e6af07fb67be542df6b9477b5e79156749eb4efa26'
assert health['single_code_capacity']==256 and health['max_context_tokens']==32768
package=health['bounded_supported_schemas']['bounded-skills/7']
assert package['legality_version']=='public-request-legal/5'
def ref(path):return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
service={'endpoint':endpoint,'health_url':endpoint.rsplit('/',2)[0]+'/healthz',
    'schema_version':'bounded-skills/7','adapter_sha256':health['adapter_sha256'],
    'schema_sha256':package['schema_sha256'],'contract_sha256':package['contract_sha256'],
    'handoff':ref(ready),'source_registration':ref(c2/'SERVICE_SOURCE_MANIFEST.json'),
    'selection_policy':health['selection_policy'],
    'comparison_caveat':'C2 pi-default uses next-a weights and fixed train-selected delta2; not next-b plus a threshold'}
stages=['model_d2_0','model_d2_1','model_d2_2','model_original6']
commands=[]
for stage in stages:
    parent=prep/f'{stage}_capacity256.json'
    plan=json.loads(parent.read_bytes())
    name=stage.replace('model_','pi_default_')
    plan.update(model_service=service,pi_default_parent_manifest=ref(parent),
        selection_policy_frozen=health['selection_policy'],
        evaluation_only=True,require_human_capability=True)
    path=prep/f'{name}.json'
    with path.open('x') as f:json.dump(plan,f,indent=2)
    config=Path(plan['libero_config']['path']).parent
    commands.append(f'''export SCHEMA6_MANIFEST={path}
export SCHEMA6_OUTPUT={run/name}
export SCHEMA6_LIBERO_CONFIG_PATH={config}
bash {plan['source']}/coordination/bounded_skills_20261016/scripts/run_schema6_stage_20261020.sbatch
''')
source=root/'source_next_b_eval_4718f24e_20261023'
script=prep/'pi_default46.sbatch'
text=f'''#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-pi-default-model46
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=10:00:00
#SBATCH --output={root}/results/slurm-%j.log
set -euo pipefail
export SCHEMA6_CONCURRENCY=8
export SCHEMA6_SOURCE={source}
export SOURCE_COMMIT=4718f24e61851aacd10ee25a0f9818d550b61a53
'''+''.join(commands)
with script.open('x') as f:f.write(text)
job=subprocess.check_output(['sbatch','--parsable','--dependency=afterany:11711',str(script)],text=True).strip()
metadata={'job':job,'script':ref(script),'service':service,'service_health':health,
    'dependency':'afterany11711: use the next evaluation card; existing two oracle workers and training shard not canceled',
    'model_source_tree':'4718f24e61851aacd10ee25a0f9818d550b61a53',
    'same_initial_snapshots_as_pi_and_next_b':True,'human_available':False,
    'recovery_budget':1,'D2':40,'original_arms':6,'training':False,'evaluation_only':True}
with (prep/'pi_default46_submission.json').open('x') as f:json.dump(metadata,f,indent=2)
print(json.dumps({k:v for k,v in metadata.items() if k!='service_health'}))
