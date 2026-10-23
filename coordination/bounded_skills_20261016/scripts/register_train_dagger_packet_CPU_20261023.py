"""Register a closed original-train packet without admitting evaluation data."""
import argparse
import datetime
import fcntl
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--name',required=True);a=p.parse_args()
manifest=a.package/'manifest.json';data=json.loads(manifest.read_bytes())
assert data['source_split']=='train' and data['training_admission'] and not data['training_executed']
assert not any(data[k] for k in ('PRO','D2','confirmation'))
assert data['pending_queries']==0 and data['repeats_each']==1
path=Path(data['data']['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==data['data']['sha256']
note={'owner':'Codex3','recipient':'Codex2','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'package':str(a.package),'manifest':{'path':str(manifest),'sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()},
    'positions':data['positions'],'bound_trials':data['bound_trials'],'unknown_truth_trials':data['unknown_trials'],
    'unreached_or_unavailable_contexts':data['unreached_or_unavailable_contexts'],
    'by_category':data['by_category'],'source_queries':data['source_queries'],
    'replacement_mapping':data['replacements'],'unknown':data['unknown'],
    'source_split':'train','PRO':False,'D2':False,'confirmation':False,'training_executed':False,
    'collection_repeats':1,'one_trial_is_not_three_trial_acceptability_evidence':True,
    'binding_rule':'fresh reached context; explicit replacements; never backfill new outcomes into old query bindings',
    'admission':'valid bound trials may enter next training only; no training performed by C3'}
root=Path('/public/home/sunyihan/rpent_libero_eval')
for owner in ('Codex1','Codex2'):
    out=root/'coordination/owner_alerts'/owner/(a.name+'.json')
    with out.open('x') as f:json.dump(note,f,indent=2)
shared=Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
with shared.open('a') as f:
    fcntl.flock(f,fcntl.LOCK_EX);f.write('\n## Codex3 — priority1 training candidate one-repeat packet\n'+json.dumps(note)+'\n');f.flush();fcntl.flock(f,fcntl.LOCK_UN)
print(json.dumps(note))
