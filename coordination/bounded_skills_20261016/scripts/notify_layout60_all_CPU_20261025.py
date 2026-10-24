from pathlib import Path
import json,hashlib,fcntl,datetime
root=Path('/public/home/sunyihan/rpent_libero_eval');run=root/'results/bounded_skills/option_expansion_20261025';p=run/'CPU_C2_measured60_closed'
x=json.loads((p/'C2_delivery.json').read_text());assert x['positions']==60 and x['attempts']==660 and not x['preview']
protocol=json.loads((p/'protocol_and_raw_attempts.json').read_text())
note={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'subject':'新60训练布局660分支全部闭合交付','delivery':{'path':str(p/'C2_delivery.json'),'sha256':hashlib.sha256((p/'C2_delivery.json').read_bytes()).hexdigest()},'package':str(p),'positions':60,'attempts':660,'request_bound_trials':623,'unknown_context_trials':37,'consumer_statuses':x['consumer_statuses'],'coverage_issue_states':3,'coverage':'binding_missing/insufficient_trials 保留unknown，不编标签、不删除失败','full_task_requested_success':'71/180','full_task_requested_by_category':[{k:g[k] for k in ['category','n','success','known_truth','unknown_truth']} for g in protocol['requested_variant_stats'] if g['requested_variant']=='full_task'],'zero_control_attempts':sum(g['zero_control_attempts'] for g in protocol['requested_variant_stats']),'layout_seeds':[11024000,11024059],'train_only':True,'PRO_D2_confirmation':False,'training_executed':False,'C2_action':'按既有split/alias和实际候选绑定接收；37个不能认证原请求的试次保持unknown；不要将D2结果当历史成功率'}
for owner in ['Codex1','Codex2']:
 (root/'coordination/owner_alerts'/owner/'C3_LAYOUT60_ALL660_CLOSED_20261025.json').write_text(json.dumps(note,ensure_ascii=False,indent=2)+'\n')
with Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md').open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX);f.write('\n## Codex3 新60训练布局：660实测全部闭合\n\n'+json.dumps(note,ensure_ascii=False)+'\n');f.flush();fcntl.flock(f,fcntl.LOCK_UN)
print(json.dumps(note,ensure_ascii=False))
