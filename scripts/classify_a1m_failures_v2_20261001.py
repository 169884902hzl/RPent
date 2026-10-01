#!/usr/bin/env python3
"""Audit a fixed episode list; read only explicitly named episode artifacts."""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import json
import ast
import argparse
import re

ap=argparse.ArgumentParser()
ap.add_argument('--snapshot',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args()
rows=json.loads(a.snapshot.read_text())
a.output.mkdir(parents=True,exist_ok=True)
reports=[]
for row in rows:
 e=row['episode']; root=Path(row['output_dir'])
 tag=f"{e['suite'].removeprefix('libero_')}_t{e['task']}_s{e['seed']}"
 paths={'cli':root/'cli.log','transcript':root/f'transcript_{tag}.json','states':root/'states.json','command':root/'command.json'}
 log=paths['cli'].read_text()
 call_counts=Counter(re.findall(r'\[tool>\]\s+(\w+)\(',log))
 execution_names={'pi0_pick','pi0_doubled','vla_act','move_to','move_pose','rotate_wrist','execute_action','set_gripper','release','retreat'}
 execution_requests=sum(n for tool,n in call_counts.items() if tool in execution_names)
 trans=json.loads(paths['transcript'].read_text())
 msgs=trans.get('messages',[])
 tools=[m for m in msgs if m.get('role')=='tool']
 assistants=[m for m in msgs if m.get('role')=='assistant']
 last=assistants[-1] if assistants else None
 content=last.get('content','') if last else ''
 text=''.join(p.get('text','') for p in content if isinstance(p,dict)) if isinstance(content,list) else str(content)
 flags=set(); skill_results=[]; errors=[]; memory_reads=0
 for m in tools:
  name=m.get('name',''); content=m.get('content','')
  try:d=json.loads(content) if isinstance(content,str) else content
  except (ValueError,TypeError):d={}
  if not isinstance(d,dict):continue
  if name in ('pi0_pick','pi0_doubled','vla_act'):
   r=d.get('log',{}).get('result',{})
   skill_results.append({'tool':name, 'result':r,'step':d.get('step'), 'terminated':d.get('terminated')})
   if r.get('success') is False:flags.add('pi0_skill_reported_failure')
   if r.get('chunks_used') and r.get('chunks_used')==r.get('max_chunks'):flags.add('pi0_skill_chunk_budget_reached')
  if name=='segment' and d.get('found') is False:flags.add('perception_target_not_found')
  if d.get('error'):
   errors.append({'tool':name,'error':d['error']})
   if name=='read_text_file':flags.add('memory_read_error')
   if name=='back_project':flags.add('invalid_back_project_arguments')
  if name=='read_text_file':memory_reads+=1
 finish=trans.get('finish') or {}
 if row['official_success']:cat='physical_success';layer='success'
 elif 'ModelHTTPError' in log and '400' in log and 'context' in log:
  cat='context_rejected_http400';layer='planning_runtime'
 elif 'model ended turn without a tool call' in log:
  if any(s in text for s in ('<tool_call','</tool_response','<function_calls','<invoke','```')):cat='no_structured_call_markup';layer='planning_interface_unresolved'
  else:cat='no_structured_call_prose';layer='planning_behavior'
 elif finish.get('status')=='success':cat='false_finish';layer='planning_behavior'
 elif finish.get('status')=='failure':cat='finish_failure_after_execution';layer='execution_or_plan_unresolved'
 elif '--planner-timeout-s' in json.loads(paths['command'].read_text()):
  command=json.loads(paths['command'].read_text());budget=float(command[command.index('--planner-timeout-s')+1])
  if not assistants and float(trans.get('elapsed_s',0))>=budget:
   cat='planner_wall_budget_observed';layer='planning_runtime'
   flags.add('timeout_inferred_from_source_elapsed_and_empty_transcript')
  else:cat='unclassified';layer='unresolved'
 else:cat='unclassified';layer='unresolved'
 if cat=='false_finish':flags.add('claimed_success_without_physical_success')
 if cat=='context_rejected_http400':flags.add('explicit_rejection_not_silent_truncation')
 if 'did not' in text and 'cream cheese' in text:flags.add('model_reported_wrong_object_not_independently_verified')
 reports.append({'episode':e,'physical_success':row['official_success'],'primary_terminal':cat,'layer':layer,'secondary_flags':sorted(flags),'pi0_results':skill_results,'tool_errors':errors,'memory_reads':memory_reads,'cli_tool_request_counts':dict(call_counts),'cli_execution_tool_requests':execution_requests,'tool_activity_limit':'CLI records requested tools,not verified physical execution;this survives timeout handlers that discard transcript history.','last_assistant':last,'finish':finish,'output_dir':str(root),'hashes':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()}})
failed=[r for r in reports if not r['physical_success']]
(a.output/'failures.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in failed))
(a.output/'episodes_classified.json').write_text(json.dumps(reports,indent=2,ensure_ascii=False))
summary={'source_snapshot':str(a.snapshot),'source_sha256':hashlib.sha256(a.snapshot.read_bytes()).hexdigest(),'attempted':len(reports),'success':len(reports)-len(failed),'failed':len(failed),'primary_terminal_counts':dict(Counter(r['primary_terminal'] for r in failed)),'secondary_failed_episode_counts':dict(Counter(f for r in failed for f in r['secondary_flags'])),'classification_note':'Wall timeout is inferred when source timeout handling discards assistant history and elapsed reaches explicit command budget; raw CLI and upstream replies remain required evidence. No old scores changed.', 'memory_error_evidence_incomplete':'Only structured tool errors counted; no memory-read success claim inferred from summary metadata.','suites':{s:{'attempted':sum(r['episode']['suite']==s for r in reports),'physical_success':sum(r['physical_success'] for r in reports if r['episode']['suite']==s),'primary_terminal':dict(Counter(r['primary_terminal'] for r in failed if r['episode']['suite']==s))} for s in dict.fromkeys(r['episode']['suite'] for r in reports)}}
(a.output/'classification_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
print(json.dumps(summary,indent=2))
