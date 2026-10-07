"""Read job4516's explicit temporal ledger and separate private labels."""

import gzip
import json
from pathlib import Path
import subprocess


REMOTE = r'''
from pathlib import Path
import hashlib,json,subprocess
root=Path('/public/home/sunyihan/rpent_libero_eval')
plan_path=root/'results/harness_v5/microwave_wrist_roi_CPU_20261008/r1/close_wrist_roi40.json'
output=root/'results/harness_v5/microwave_wrist_roi_original_20261008/close40'
ledger=output/'episodes.jsonl'
def identity(p):return {'path':str(p),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
plan=json.loads(plan_path.read_text())
if identity(plan_path)['sha256']!='f99a31186a24da14be9a5e1761de9f5a4d37ab3e952cab1a5705cd28660d3c35':
 raise ValueError('registered close_stop40 plan changed')
accounting=subprocess.run(['sacct','-j','4516','--format=JobID,State,ExitCode,Elapsed,NodeList','-P'],capture_output=True,text=True,check=True).stdout
lines=ledger.read_text().splitlines() if ledger.is_file() else []
if not lines:
 print(json.dumps({'job':4516,'status':'no_completed_episode_yet','sacct':accounting,'plan':identity(plan_path)}))
 raise SystemExit(0)
if len(lines)!=1:raise ValueError('one explicit development episode required')
row=json.loads(lines[0]);first=row.get('first_attempt') or {}
if row.get('case')!=plan['cases'][0]:raise ValueError('saved case differs from the registered plan')
public_records=(first.get('verification_measurements') or {}).get('microwave_temporal',[])
inputs=[{'kind':'plan',**identity(plan_path)},{'kind':'episode_ledger',**identity(ledger)}]
contract=output/'physical_startup_contract.json'
if contract.is_file():inputs.append({'kind':'physical_startup_contract',**identity(contract)});contract=json.loads(contract.read_text())
else:contract=None
snapshot=plan['source_snapshot']
relevant=[item for item in snapshot['files'] if item['relative_path'] in (
 'robots/libero/v5_microwave_capture.py','robots/libero/v5_microwave_door_temporal.py',
 'robots/libero/v5_runtime.py','scripts/probe_v5_skill501_original.py')]
for item in relevant:
 actual=identity(item['path'])
 if actual['sha256']!=item['sha256']:raise ValueError('pinned source changed: '+item['path'])
 inputs.append({'kind':'source',**actual,'relative_path':item['relative_path']})
evidence=first.get('contact_evidence') or {}
payload={'version':'microwave4516-wrist-roi-close-records/1-dev','job':4516,'sacct':accounting,
 'manifest':identity(plan_path),'source_snapshot':{'path':snapshot['path'],'commit':snapshot['commit'],'archive':snapshot['archive']},
 'case':row['case'],'status':row.get('status'),'infrastructure_failure':row.get('infrastructure_failure'),
 'wall_s':row.get('wall_s'),'case_wall_s':row.get('case_wall_s'),'contract':contract,
 'server_chunk_execution':row.get('server_chunk_execution'),'receipt':first.get('receipt'),
 'physical_actions':first.get('executed_actions'),'physically_executed':first.get('physically_executed'),
 'public_records':public_records,'public_before':first.get('public_before'),'public_after':first.get('public_after'),
 'motion_evidence':first.get('motion_evidence'),'private_before':first.get('private_before'),
 'private_after':first.get('private_after'),'private_scores':evidence.get('private_fixture_scores',[]),
 'contact_prompts':evidence.get('contact_prompts'),'executed_vla_actions':evidence.get('executed_vla_actions'),
 'inputs':inputs,'training_allowed':False,'qualification':False,'private_labels_control_execution':False}
print(json.dumps(payload))
'''


if __name__ == "__main__":
    run = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "gpu5880-ts", "python3", "-"],
                         input=REMOTE, text=True, capture_output=True, check=True)
    data = json.loads(run.stdout)
    if data["status"] == "no_completed_episode_yet":
        print(json.dumps(data)); raise SystemExit(0)
    path = Path(__file__).resolve().parent / "records.json.gz"
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes(gzip.compress((json.dumps(data, indent=2) + "\n").encode(), mtime=0))
    print(json.dumps({"path": str(path), "job": data["job"], "status": data["status"],
                      "temporal_records": len(data["public_records"]), "private_labels": len(data["private_scores"])}))
