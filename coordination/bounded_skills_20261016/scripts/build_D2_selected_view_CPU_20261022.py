from pathlib import Path
import sys,json,hashlib,subprocess,argparse
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
R=Path('/public/home/sunyihan/rpent_libero_eval');source=R/'source_D2_option_fallback_a3c7cf43_20261022';sys.path.insert(0,str(source))
from robots.libero.bounded_hybrid_paths import select_complete_path

def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def checked(p):
 v=json.loads(p.read_bytes());f=Path(v['summary']);assert ref(f)['sha256']==v['sha256'];return f,json.loads(f.read_bytes())
replays={}
for f in (a.root/'native_changed_paths6/results').glob('closed_*.json'):
 path,d=checked(f);key=(d['recovery_budget'],d['case']['name']);assert key not in replays;replays[key]=(path,d)
a.output.mkdir(parents=True,exist_ok=False)
missing,changed,rows=[],[],[]
for b in (0,1,2):
 out=a.output/f'D2_recovery{b}';out.mkdir()
 for i in range(40):
  f=a.root/f'D2_recovery{b}/closed_{i:03d}.json'
  if not f.exists():missing.append([b,i]);continue
  path,d=checked(f);selection=select_complete_path(d)
  if selection['reason']=='measured_native_complete_path':
   key=(b,d['case']['name'])
   if key not in replays:
    changed.append({'budget':b,'index':i,'case':d['case']['name'],'parent':ref(path),'selection':selection});continue
   newpath,new=replays[key];assert new['parent_summary']==ref(path);assert new['path_selection']==selection
   assert new['initial_physics_sha256']==new['parent_initial_physics_sha256']
   path,d=newpath,new
  (out/f'closed_{i:03d}.json').write_text(json.dumps({'summary':str(path),'sha256':ref(path)['sha256']},indent=2)+'\n')
  rows.append({'budget':b,'index':i,'case':d['case']['name'],'success':d['actual_full_replay_success'],'path_selection':selection['reason'],'summary':ref(path)})
report={'missing':missing,'new_paths_requiring_replay':changed,'rows':rows,'complete':not missing and not changed,'training':False,'source_commit':'a3c7cf4338f79cb3e11af5eced1d195f8b3f34a1'}
(a.output/'view_registration.json').write_text(json.dumps(report,indent=2)+'\n')
cmd=[str(R/'.venv/bin/python'),str(R/'aggregate_B2_D2_CPU_20261021.py'),'--root',str(a.output),'--a1',str(R/'results/bounded_skills/execution_repairs_20261022/D2_preparation_c6b62442/preparation/A1_M_40_reference.json'),'--output',str(a.output/'aggregate')]
if not report['complete']:cmd.append('--allow-incomplete')
subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
m=json.loads((a.output/'aggregate/manifest.json').read_bytes())
print(json.dumps({'output':str(a.output),'missing':missing,'new_paths':len(changed),'recovery':{k:{f:v[f] for f in ['closed','success','sampled_bound_known','sampled_bound_success','unknown_private_rule_cases']} for k,v in m['recovery'].items()}}))
