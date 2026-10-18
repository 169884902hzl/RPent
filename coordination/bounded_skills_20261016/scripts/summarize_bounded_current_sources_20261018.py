from pathlib import Path
import json,sys
sys.path.insert(0,'/public/home/sunyihan/rpent_libero_eval/source_bounded_cbaa92a_20261017')
from scripts.summarize_bounded_probes import feasibility
root=Path('/public/home/sunyihan/rpent_libero_eval');base=root/'results/bounded_skills/feasibility_20261017'
jobs={'8016_100':'b045b98','8016_60':'b045b98','8010_120':'2d50b76','8010_160':'2d50b76','8020_160':'8c43651','8025_100':'ca4ce83','8025_101':'ca4ce83','8025_102':'ca4ce83','8025_103':'ca4ce83','8028_60':'78c7c46','8030_160':'ddecd79','8035_180':'776e900','8036_160':'2da8248','8037_120':'2970571','8040_180':'7812732','8040_200':'7812732','8043_120':'cbaa92a','8045_180':'2ceec13','8053_200':'a8238d0','8056_181':'627c861',**{f'8046_{i}':'2ceec13' for i in range(181,200)}}
jobs.update({**{f'8061_{i}':'6ddc6a1' for i in range(0,201,20)},'8065_20':'d6c768c','8069_0':'1da79f2','8071_20':'845a720',**{f'8072_{i}':'845a720' for i in (0,40,60,80,100,120,140,160,180,200)}})
jobs.update({f'8075_{i}':'845a720' for i in (120,140,180)})
jobs.update({'8085_120':'730e859',**{f'8087_{i}':'96679ad' for i in range(20)},'8095_20':'96679ad','8095_140':'96679ad'})
jobs.update({'8103_80':'1fde995','8108_2':'11a73af',**{f'8109_{i}':'11a73af' for i in [0,1,*range(3,20)]},'8111_20':'cee33e8',**{f'8112_{i}':'cee33e8' for i in range(21,40)}})
jobs.update({f'8117_{i}':'a961dfd' for i in (80,120,140,160,200)})
jobs.update({'8123_20':'3449b96', **{f'8124_{i}':'3449b96' for i in range(21,40)}})
jobs.update({'8134_22':'9e03b06'})
jobs.update({'8137_22':'7dba5cd', '8141_20':'7dba5cd', '8142_7':'7dba5cd'})
jobs.update({'8144_22':'9368299', **{f'8145_{i}':'9368299' for i in (0,40,60,100,180)}})
jobs.update({f'8147_{i}':'9368299' for i in (20,21,*range(23,40))})
jobs.update({'8156_21':'8e49152','8158_60':'bc160ff',**{f'8159_{i}':'bc160ff' for i in range(60)}})
jobs.update({'8161_100':'cbffa78',**{f'8162_{i}':'cbffa78' for i in (80,120,180,200)},'8163_140':'cbffa78'})
jobs.update({'8170_100':'3d71f44', **{f'8171_{i}':'3d71f44' for i in (80,120,180,200)}})
jobs.update({f'8173_{i}':'3d71f44' for i in range(3,60)})
jobs.update({'8183_100':'9cacb71', **{f'8184_{i}':'9cacb71' for i in (80,120,180,200)}})
jobs.update({f'8192_{i}':'9cacb71' for i in range(101,120)})
rows=[]
for j,source in jobs.items():
 p=base/('job'+j)/'episodes.jsonl'
 if not p.exists():continue
 for line in p.open():
  r=json.loads(line)
  if r.get('status')!='physical_result':continue
  rows.append({'job':j,'source_commit':source,'episodes_file':str(p),**r})
groups={}
for source in sorted(set(r['source_commit'] for r in rows)):
 paths=sorted({Path(r['episodes_file']) for r in rows if r['source_commit']==source})
 groups[source]=feasibility(paths)
report={'cohorts_by_source':groups,'scope':'original-scene development, full physical results only, each source/case reported separately; repeated cases are not independent trials','training':False,'pi05_disabled':True,'rows':rows}
p=root/'coordination/bounded_skills_20261016/reports/oracle_closed_progress_20261018.json';p.write_text(json.dumps(report,indent=2)+'\n')
for r in rows[-8:]:print(r['job'],r['source_commit'],r['case']['category'],r['success'],r['decisions'],r['sim_steps'],round(r['wall_s'],1),r['failure_phase'])
