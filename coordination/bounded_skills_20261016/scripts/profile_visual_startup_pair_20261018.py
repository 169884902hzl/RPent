"""Compare one physical-startup public request and its function profiles."""
import argparse
import hashlib
import json
import pstats
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--jobs', nargs=2, default=['9000_24','9006_24'])
parser.add_argument('--output-name', default='visual_profile_startup_pair_20261018.json')
parser.add_argument('--source-only-changes', default='public legal_after labels, actual-refresh profiler, conservative self-filter broad phase')
args=parser.parse_args()

root=Path('/public/home/sunyihan/rpent_libero_eval')
base=root/'coordination/bounded_skills_20261016'
result=root/'results/bounded_skills/feasibility_20261017'

def canonical(value):
 return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def profile(path):
 stats=pstats.Stats(str(path))
 rows=[]
 for (file,line,name),(cc,nc,tt,ct,callers) in sorted(stats.stats.items(),key=lambda item:item[1][3],reverse=True)[:15]:
  rows.append(dict(file=file,line=line,name=name,primitive_calls=cc,calls=nc,self_s=tt,cumulative_s=ct))
 return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),self_total_s=stats.total_tt,top15=rows)

items=[]
for job in args.jobs:
 directory,=[d for d in (result/('job'+job)).glob('*oracle*') if not d.name.endswith('_legacy')]
 raw=(directory/'choices.jsonl').read_bytes()
 row=json.loads(raw.splitlines()[0])
 req=canonical(row['request']); decision=canonical(row['decision'])
 profiles=[profile(p) for p in sorted(directory.glob('perception_refresh_*.pstats'))]
 items.append(dict(job=job,directory=str(directory),choices_sha256=hashlib.sha256(raw).hexdigest(),
  request_sha256=hashlib.sha256(req).hexdigest(),request_bytes=len(req),
  decision_sha256=hashlib.sha256(decision).hexdigest(),decision=row['decision'],
  candidates=len(row['request']['candidates']),planning=profile(directory/'request_profile.pstats'),
  perception=profiles,physical=json.loads((directory/'first_physical_request.json').read_text())))
 a=json.loads((Path(items[0]['directory'])/'choices.jsonl').read_bytes().splitlines()[0]) if len(items)==2 else None
 if a is not None:
  differences=[key for key in row['request'] if row['request'][key]!=a['request'].get(key)]
report=dict(jobs=items,request_bytes_equal=items[0]['request_sha256']==items[1]['request_sha256'],
 request_changed_fields=differences,decision_bytes_equal=items[0]['decision_sha256']==items[1]['decision_sha256'],
 canonical_serializer='json.dumps(sort_keys=True,separators=(comma,colon),ensure_ascii=False,allow_nan=False).encode(utf8)',
 source_only_changes=args.source_only_changes,
 controls_in_analysis=0,training=False,confirmation=False,pi05=False,
 limitation='Single matched physical startup; profile cumulative times overlap; not episode throughput')
path=base/'reports'/args.output_name
path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(output=str(path),request_bytes_equal=report['request_bytes_equal'],request_changed_fields=differences,decision_bytes_equal=report['decision_bytes_equal'],
 planning_s=[item['planning']['self_total_s'] for item in items],
 perception_s=[[x['self_total_s'] for x in item['perception']] for item in items])))
assert report['request_bytes_equal'] and report['decision_bytes_equal']
