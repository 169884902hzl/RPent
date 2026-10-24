"""Reuse exact frozen candidate collection for the300 registered train contrasts."""
from pathlib import Path
import hashlib,json,subprocess
r=Path('/public/home/sunyihan/rpent_libero_eval');run=r/'results/bounded_skills/task_ladder_20261025'
queries=Path('/public/home/sunyihan/rd_instruction_20260923/c2_next_d_20261024_0805/singleton_contrasts_v2_12300/C3_TRAIN_SINGLETON_CONTRASTS.jsonl')
assert hashlib.sha256(queries.read_bytes()).hexdigest()=='8096198f2832560c2a1db4235390eb51ddaf13b84a313c8aac3a3aa1bd072d1f'
rows=[json.loads(line) for line in queries.read_text().splitlines()];assert len(rows)==300
assert all(q['service_response_not_applicable'] and q['service_response_sha256'] is None and q['candidate_id']!=q['model_selected_id'] for q in rows)
# The existing producer verifies the selected candidate against the original
# source/request/prefix/outcome; it never requires model-top provenance.
original=(r/'prepare_dagger2_exact_20261025.py')
if not original.exists():raise FileNotFoundError(original)
s=original.read_text().replace('task_ladder_20261025/dagger2_exact','task_ladder_20261025/dagger2_contrasts_exact').replace('/DAgger2_current_HTTP_boardv2_12300/C3_DAGGER_ROUND2_TRAIN.jsonl','/singleton_contrasts_v2_12300/C3_TRAIN_SINGLETON_CONTRASTS.jsonl').replace('len(rows)==577','len(rows)==300').replace("'shards':19","'shards':10").replace('94000000+i*1000','96000000+i*1000')
exec(compile(s,str(original),'exec'),{'__name__':'__main__'})
prep=run/'dagger2_contrasts_exact/preparation';top=run/'dagger2_exact/preparation'
assert (prep/'run_dagger2_exact.py').read_bytes()==(top/'run_dagger2_exact.py').read_bytes()
assert (prep/'evaluate_candidate.py').read_bytes()==(top/'evaluate_candidate.py').read_bytes()
s=(top/'export_dagger2_exact.py').read_text().replace('Codex3 当前HTTP训练候选单次实测闭合分片','Codex3 训练切分确定性对照单次实测闭合分片')
s=s.replace(" row=helper.measured_row(q,report,revision,prompt.invocation_prompt)"," row=helper.measured_row(q,report,revision,prompt.invocation_prompt)\n row.update(collection_kind='deterministic_contrast',selection_provenance=q['selection_provenance'],service_response_not_applicable=True,model_selected_id=q['model_selected_id'])")
(prep/'export_dagger2_exact.py').write_text(s)
# Distinct output basenames also keep Codex2 alert filenames disjoint from top shards.
s=(top/'collect.sbatch').read_text().replace('task_ladder_20261025/dagger2_exact','task_ladder_20261025/dagger2_contrasts_exact').replace('rd-c3-dagger2-exact','rd-c3-dagger2-contrasts').replace('0-18%1','0-9%1').replace('/shard${TASK}','/contrast_shard${TASK}')
# Manifest names remain shard000.json; output and export names use contrast_shard000.
s=s.replace('/preparation/contrast_shard${TASK}.json','/preparation/shard${TASK}.json')
(prep/'collect.sbatch').write_text(s);subprocess.run(['bash','-n',str(prep/'collect.sbatch')],check=True)
# Use the existing CPU saved-candidate auditor, one real input per source revision.
audit=(r/'audit_dagger2_bindings_CPU_20261025.py').read_text().replace('task_ladder_20261025/dagger2_exact','task_ladder_20261025/dagger2_contrasts_exact')
(prep/'audit_bindings.py').write_text(audit)
script=prep/'audit.sbatch';script.write_text(f'''#!/bin/bash
#SBATCH --job-name=rd-c3-contrast-CPU
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --cpus-per-task=4
#SBATCH --mem=20G
#SBATCH --time=00:20:00
#SBATCH --output={prep}/audit.log
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
{r}/.venv/bin/python {prep}/audit_bindings.py
''')
job=subprocess.check_output(['sbatch','--parsable',str(script)],text=True).strip()
(prep/'CPU_submission.json').write_text(json.dumps({'CPU_job':job,'queries':300,'model_selected':False,'bindings_unchanged':True,'training_executed':False})+'\n')
print(json.dumps({'CPU_job':job,'prepared_queries':300,'physical_submitted':False}))
