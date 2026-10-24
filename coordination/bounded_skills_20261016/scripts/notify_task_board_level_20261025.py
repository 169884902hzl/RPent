"""Publish a finished five-trial shard's current board path and SHA."""
from pathlib import Path
import argparse,json,hashlib,fcntl,datetime
p=argparse.ArgumentParser();p.add_argument('--shards',type=Path,required=True);p.add_argument('--index',type=int,required=True);a=p.parse_args()
s=json.loads(a.shards.read_text())[a.index];plan=json.loads(Path(s['manifest']).read_text());root=Path(plan['board_root'])
# NFS shared locks require a readable descriptor; the board writer created it.
with (root/'task_board.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_SH)
 raw=(root/'task_board.jsonl').read_bytes();rows=[json.loads(line) for line in raw.splitlines()]
 keys={j['panel_task_id'] for j in plan['jobs']};selected=[row for row in rows if row['task_key'] in keys]
 sha=hashlib.sha256(raw).hexdigest();versions=root/'board_versions';versions.mkdir(exist_ok=True)
 frozen=versions/(sha+'.jsonl')
 if not frozen.exists():frozen.write_bytes(raw)
 fcntl.flock(lock,fcntl.LOCK_UN)
ref={'path':str(frozen),'sha256':sha,'current_path':str(root/'task_board.jsonl')}
note={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'board':ref,'level_counts':selected,
    'source_commit':plan['source_commit'],'PRO_training':False,'training_executed':False,
    'model_line_pending_is_not_a_failure':True}
with Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md').open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX);f.write('\n## Codex3 任务5次一级计数更新\n\n'+json.dumps(note,ensure_ascii=False)+'\n');f.flush();fcntl.flock(f,fcntl.LOCK_UN)
dest=Path('/public/home/sunyihan/rpent_libero_eval/coordination/owner_alerts/Codex2')
(dest/f'C3_TASK_BOARD_{keys.pop().replace("/","_")}_{datetime.datetime.now().strftime("%Y%m%dT%H%M%S")}.json').write_text(json.dumps(note,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'board':ref,'tasks':len(selected)}))
