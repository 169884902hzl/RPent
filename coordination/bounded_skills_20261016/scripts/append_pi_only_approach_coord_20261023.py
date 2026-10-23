"""Append evaluated artifacts and the public capability contract to coordination."""
import fcntl
import json
from pathlib import Path
import subprocess

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
RUN=ROOT/'results/bounded_skills/pi_only_and_approach_20261023'
pi=json.loads((RUN/'CPU_pi_only46/manifest.json').read_text())
approach=json.loads((RUN/'CPU_approach30/manifest.json').read_text())
notice=json.loads((ROOT/'coordination/owner_alerts/Codex2/C3_HUMAN_CAPABILITY_LEGAL5_20261023.json').read_text())
report={'owner':'Codex3','evaluation_only':True,'training':False,
    'pi_only46':pi,'approach30':approach,'human_capability':notice,
    'approach_deployment':'not deployed: retained screen rejects all 30 elevated routes, no evidence supporting a production replacement',
    'pending':'v-next-b registration and Claude DAgger list not received; old service not restarted',
    'resource_snapshot':subprocess.check_output(['squeue','-h','-w','node02','-t','RUNNING','-o','%i|%j|%C|%m|%b'],text=True)}
for owner in ('Codex1','Codex2'):
    path=ROOT/'coordination/owner_alerts'/owner/'C3_PI_ONLY_AND_APPROACH_CLOSED_20261023.json'
    with path.open('x') as f:json.dump(report,f,indent=2)
with (RUN/'CPU_delivery.json').open('x') as f:json.dump(report,f,indent=2)
with Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md').open('a') as stream:
    fcntl.flock(stream,fcntl.LOCK_EX)
    stream.write('\n## Codex3 2026-10-23 — pure pi0.5 baseline and approach diagnostics closed\n')
    stream.write(json.dumps(report,ensure_ascii=False)+'\n')
    stream.flush();fcntl.flock(stream,fcntl.LOCK_UN)
print(json.dumps({'delivery':str(RUN/'CPU_delivery.json'),'D2':pi['groups']['d2'],
    'approach':approach['groups'],'human_commit':notice['source_commit']}))
