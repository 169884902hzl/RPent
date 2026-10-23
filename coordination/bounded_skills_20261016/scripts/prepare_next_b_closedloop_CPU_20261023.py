"""Register next-b on the exact full states used by the pure-policy baseline."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
BASE=ROOT/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'
OLD=ROOT/'results/bounded_skills/pi_only_and_approach_20261023'
RUN=ROOT/'results/bounded_skills/next_b_pi_first_20261023'

def ref(p):
    return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);args=p.parse_args()
source=args.source
handoff_path=Path('/public/home/sunyihan/rd_instruction_20260923/c2_next_b_20261022_2030/C3_SERVICE_HANDOFF_11688.json')
assert ref(handoff_path)['sha256']=='0b7386612b1f09cb617f54566d6ee48cb8fe8f2125f9a9a019c8a77cf03e5204'
handoff=json.loads(handoff_path.read_text())
header=json.loads((BASE/'native_model_09e37883/preparation/model_D2_recovery1.json').read_text())
revision=json.loads((source/'SOURCE_REVISION.json').read_text())['tree']
package=handoff['supported_source_versions']['bounded-skills/7']
assert ref(source/'rpent/skill_package/schema.json')['sha256']==package['schema_sha256']
assert ref(source/'rpent/skill_package/contract.py')['sha256']==package['contract_sha256']
header.update(source=str(source),source_commit=revision,schema_version='bounded-skills/7',
    require_human_capability=True,model_service={'endpoint':handoff['endpoint'],
        'health_url':handoff['endpoint'].replace('/v1/bounded-choice','/healthz'),
        'schema_version':'bounded-skills/7','adapter_sha256':handoff['adapter_sha256'],
        'schema_sha256':package['schema_sha256'],'contract_sha256':package['contract_sha256'],
        'handoff':ref(handoff_path)},initial_snapshot_by_arm={},
    runtime_budget={'sim_steps':10000,'decisions':160,'recovery_budget':1},
    comparison_caveat='legal4 to legal5 and schema6 old-model to measured-anchor schema7; not a weight-only contrast',
    evaluation_only=True,training=False,confirmation=False)
pure=[]
for i in range(4):pure+=json.loads((OLD/f'preparation/pi_only_shard{i}.json').read_text())['jobs']
d2=[];original=[]
for old in pure:
    k=int(old['arm_id'].rsplit('_K',1)[1]) if old['domain']=='original' else 4
    row={'kind':'model','case':old['case'],'k':k,
        'split':'init_holdout' if old['domain']=='original' else 'd2_evaluation'}
    header['initial_snapshot_by_arm'][old['case']['name']+'|'+str(k)]=old['initial_snapshot']
    (d2 if old['domain']=='d2' else original).append(row)
assert len(d2)==40 and len(original)==6
pre=RUN/'preparation';pre.mkdir(parents=True,exist_ok=True)
for label,jobs,config in [*(('model_d2_'+str(i),d2[i::3],ROOT/'runtime_config/config.yaml') for i in range(3)),
        ('model_original6',original,ROOT/'runtime_config_original_20261023/config.yaml')]:
    plan=copy.deepcopy(header);plan['jobs']=jobs;plan['libero_config']=ref(config)
    path=pre/(label+'.json')
    with path.open('x') as stream:json.dump(plan,stream,indent=2)
    text=f'''#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-s6-v7-nextb-{label}
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=12:00:00
#SBATCH --output={ROOT}/results/slurm-%j.log
set -euo pipefail
export SCHEMA6_SOURCE={source}
export SOURCE_COMMIT={revision}
export SCHEMA6_MANIFEST={path}
export SCHEMA6_OUTPUT={RUN}/{label}
export SCHEMA6_LIBERO_CONFIG_PATH={config.parent}
export SCHEMA6_CONCURRENCY=8
exec bash {source}/coordination/bounded_skills_20261016/scripts/run_schema6_stage_20261020.sbatch
'''
    (pre/(label+'.sbatch')).write_text(text)
print(json.dumps({'run':str(RUN),'source_tree':revision,'D2':len(d2),'original':len(original),
    'source_handoff_sha256':ref(handoff_path)['sha256'],'human_available':False}))
