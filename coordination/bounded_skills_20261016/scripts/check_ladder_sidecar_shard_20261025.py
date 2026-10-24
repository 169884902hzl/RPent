# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare a completed physical shard's actual choices with service 12318."""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json,sys,urllib.request

p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--shards',type=Path,required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--ack',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.source))
from rpent.skill_package.contract import legal_after
from robots.libero.bounded_async import public_model_request
shard=json.loads(a.shards.read_bytes())[a.index];out=Path(shard['output']);plan=json.loads(Path(shard['manifest']).read_bytes())
reference=plan['model_service']['endpoint'];records=[]
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
files=sorted(out.glob('case*/model/choices.jsonl'))
assert len(files)==5,('expected five completed model episodes',len(files))
for file in files:
 summary=json.loads((file.parent/'summary.json').read_bytes());assert summary['status']=='physical_result'
 local_results=[json.loads(s) for s in (file.parent/'model_responses.jsonl').read_text().splitlines()]
 choices=[json.loads(s) for s in file.read_text().splitlines()]
 assert len(local_results)==len(choices),file
 assert summary['sim_steps']>0,('sidecar shard did not execute any controls',str(file))
 for row,response in list(zip(choices,local_results))[:2]:
  request=row['request'];legal=set(legal_after(request,[]));positions=response['positions'][0]
  assert set(positions['probabilities'])==legal
  body=json.dumps({'skill_request':public_model_request(request),'k':1,'mode':'cached'}).encode()
  with opener.open(urllib.request.Request(reference,data=body,headers={'Content-Type':'application/json'}),timeout=180) as call:
   raw=call.read();remote=json.loads(raw)
  assert response['selected_option_ids']==remote['selected_option_ids'],(file,row['index'])
  assert response['positions'][0]['code']==remote['positions'][0]['code']
  probs=remote['positions'][0]['probabilities'];assert set(probs)==legal
  records.append({'case':file.parent.parent.name,'decision':row['index'],'legal_count':len(legal),
   'source_legal_identical':True,'selected_identical':True,'code_identical':True,
   'probability_max_abs_difference':max(abs(probs[k]-positions['probabilities'][k]) for k in legal),
   'request_sha256':hashlib.sha256(body).hexdigest(),'reference_response_sha256':hashlib.sha256(raw).hexdigest()})
assert records
result={'owner':'Codex3','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'sidecar_switch_ACK':True,'pilot_shard':str(out),'closed_model_episodes':len(files),'checks':records,
 'adapter_sha256':plan['model_service']['adapter_sha256'],'source_tree':plan['source_commit'],
 'C2_action':'同卡分片和选择一致性已通过，请结束12318；后续模型线将随评测作业启动选择器边车。C3不直接修改12318。',
 'protected_jobs_modified':False}
a.ack.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
with Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md').open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX);f.write('\n## Codex3 → Codex2：同卡物理分片通过，切换ACK，请停12318\n\n'+json.dumps(result,ensure_ascii=False)+'\n')
print(json.dumps(result,ensure_ascii=False))
