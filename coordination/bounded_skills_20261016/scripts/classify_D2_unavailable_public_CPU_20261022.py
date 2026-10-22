from pathlib import Path
from collections import Counter
from types import SimpleNamespace
import argparse,json,pickle,hashlib,sys,os
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.path.insert(0,str(a.source));os.environ['LIBERO_TYPE']='pro'
from robots.libero.v5_oracle_policy import OriginalOraclePolicy
from scripts.probe_bounded_hybrid_d2 import bind_subtask,unbound_vla_candidate
from rpent.skill_package.contract import legal_after
rows=[];audit=json.loads(a.audit.read_bytes());cache={}
for i,t in enumerate(audit['unavailable']):
 ref=t['endpoint'];key=(ref['sha256'],json.dumps(t['subtask'],sort_keys=True),json.dumps(t.get('vla_variant'),sort_keys=True))
 if key not in cache:
  raw=Path(ref['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==ref['sha256'];saved=pickle.loads(raw);del raw
  public=saved['public_runtime'];state=public['adapter'];request=state['latest_request'];legal=set(legal_after(request,[]));calls=[c for c in request['candidates'] if c['skill']=='call_vla'];binding=OriginalOraclePolicy(None);vars(binding).update(public['binding'])
  adapter=SimpleNamespace(scene=SimpleNamespace(**public['scene']),ex=SimpleNamespace(instruction=request['instruction']));source,target=bind_subtask(SimpleNamespace(binding=binding),adapter,t['subtask']);missing=source is None or bool(t['subtask']['target_symbol']) and target is None
  fallback=unbound_vla_candidate(request,request['instruction'],t['subtask']['mode'],preparation=t['vla_variant']['parameters'].get('preparation','in_place'))
  available=[c for c in calls if c['id'] in legal]
  if all(c['skill'] in {'finish','ask_help'} for c in request['candidates']):cause='public_no_progress_termination'
  elif fallback is not None:cause='existing_legal_unbound_fallback_unexpectedly_unavailable'
  elif not any(c['parameters'].get('mode') in {'task','instruction'} for c in available):cause='no_legal_unbound_option_remaining_after_failures'
  elif missing:cause='public_binding_missing_and_no_matching_unbound_option'
  elif t['subtask']['mode'] in {'on','in'} and state.get('held') is None:cause='placement_requires_missing_public_held_identity'
  else:cause='requested_variant_absent_from_current_public_legal_set'
  cache[key]={'classification':cause,'public_binding_missing':bool(missing),'held':state.get('held'),'candidate_count':len(request['candidates']),'legal_call_count':len(available),'legal_unbound_modes':[c['parameters'] for c in available if c['parameters'].get('mode') in {'task','instruction'}],'public_progress':request.get('progress'),'fallback':None if fallback is None else fallback['parameters']}
  del saved,public,state,request
 rows.append({'case':t['case'],'budget':t['recovery_budget'],'subtask':t['subtask']['id'],'seed':t['trial_seed'],'endpoint':ref,**cache[key]})
 if (i+1)%10==0:print(json.dumps({'classified':i+1,'total':len(audit['unavailable'])}),flush=True)
a.output.write_text(json.dumps({'n':len(rows),'counts':dict(Counter(x['classification'] for x in rows)),'rows':rows,'scope':'saved public request and binding only; no planner, simulator, RPC or training'},indent=2)+'\n');print(json.dumps({'counts':dict(Counter(x['classification'] for x in rows)),'output':str(a.output)}))
