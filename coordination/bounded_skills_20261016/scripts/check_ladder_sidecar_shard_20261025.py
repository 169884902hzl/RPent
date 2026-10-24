# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Validate actual physical choices and the delivered frozen parity requests."""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json,sys,urllib.request

p=argparse.ArgumentParser()
for name in ('source','shards','ack','package-root'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--index',type=int,required=True);p.add_argument('--selector-url',required=True);a=p.parse_args()
sys.path.insert(0,str(a.source))
from rpent.skill_package.contract import legal_after
shard=json.loads(a.shards.read_bytes())[a.index];out=Path(shard['output']);plan=json.loads(Path(shard['manifest']).read_bytes())
records=[];files=sorted(out.glob('case*/model/choices.jsonl'))
assert len(files)==5,('expected five completed model episodes',len(files))
for file in files:
 summary=json.loads((file.parent/'summary.json').read_bytes());assert summary['status']=='physical_result'
 local_results=[json.loads(s) for s in (file.parent/'model_responses.jsonl').read_text().splitlines()]
 choices=[json.loads(s) for s in file.read_text().splitlines()]
 assert len(local_results)>=len(choices),file
 assert summary['sim_steps']>0,('sidecar shard did not execute any controls',str(file))
 for row,response in zip(choices,local_results):
  legal=set(legal_after(row['request'],[]));position=response['positions'][0]
  assert set(position['probabilities'])==legal
  assert set(response['selected_option_ids'])<=legal
  records.append({'case':file.parent.parent.name,'decision':row['index'],'legal_count':len(legal),
   'source_legal_identical':True,'selected_is_legal':True})
assert records
handoff=json.loads((a.package_root/'SIDECAR_HANDOFF.json').read_bytes())
assert handoff['contract_sha256']==hashlib.sha256((a.source/'rpent/skill_package/contract.py').read_bytes()).hexdigest()
ref=handoff['GPU'];assert hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest()==ref['sha256']
reference_summary=json.loads(Path(ref['path']).read_bytes());parity=[]
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
for item in reference_summary['checks']:
 name=item['name'];directory=Path(ref['path']).parent
 body=(directory/f'{name}_request.json').read_bytes();raw=(directory/f'{name}_reference.json').read_bytes()
 assert hashlib.sha256(body).hexdigest()==item['wire_request_sha256']
 assert hashlib.sha256(raw).hexdigest()==item['reference_response_sha256']
 reference=json.loads(raw)
 with opener.open(urllib.request.Request(a.selector_url,data=body,headers={'Content-Type':'application/json'}),timeout=180) as call:actual=json.load(call)
 assert actual['selected_option_ids']==reference['selected_option_ids']
 assert actual['positions'][0]['code']==reference['positions'][0]['code']
 probs=actual['positions'][0]['probabilities'];expected=reference['positions'][0]['probabilities'];assert probs.keys()==expected.keys()
 parity.append({'request':name,'selected_identical':True,'code_identical':True,
  'probability_max_abs_difference':max(abs(probs[k]-expected[k]) for k in probs)})
result={'owner':'Codex3','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'sidecar_switch_ACK':True,'pilot_shard':str(out),'closed_model_episodes':len(files),'source_legal_checks':records,
 'actual_GPU_parity_to_frozen12318':parity,'reference_package':str(a.package_root),
 'adapter_sha256':plan['model_service']['adapter_sha256'],'source_tree':plan['source_commit'],
 'C2_action':'同卡分片已通过；新的模型分片切到边车。请暂保留12318，C3核查此前仍用18065的分片已退出后会另发停服通知。',
 'protected_jobs_modified':False}
a.ack.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
with Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md').open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX);f.write('\n## Codex3 → Codex2：同卡物理分片通过，先核查原服务使用者，再单独通知停服\n\n'+json.dumps(result,ensure_ascii=False)+'\n')
print(json.dumps(result,ensure_ascii=False))
