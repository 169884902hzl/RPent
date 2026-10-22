from pathlib import Path
from collections import Counter,defaultdict
import argparse,json,hashlib,subprocess,os
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--allow-incomplete',action='store_true');a=p.parse_args();R=Path('/public/home/sunyihan/rpent_libero_eval');export=json.loads((a.root/'preparation/export_plan.json').read_bytes());packets=list(map(Path,export['packets']))
def ref(path):return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
records=[];sources=[];manifests=[];workers=[]
for packet in packets:
 m=packet/('CPU_partial63_export_final/manifest.json' if a.allow_incomplete and packet.name=='measured_packet2' else 'CPU_closed_measured_r1/manifest.json');d=json.loads(m.read_bytes());assert a.allow_incomplete or not d['preview'] and not d['unresolved_cases'];data=Path(d['data']['path']);assert ref(data)==d['data'];sources.append(ref(m));records += [json.loads(l) for l in data.read_text().splitlines()];manifests.append(d)
 workers += [json.loads(f.read_bytes()) for f in (packet/'forks').glob('job*/N8/*/worker_summary.json')]
n=len(records);assert (n>=60 if a.allow_incomplete else n==65) and len({r['record_id'] for r in records})==n;wanted={r['case']['name'] for r in records};workers=[w for w in workers if w['case']['name'] in wanted];assert len(workers)==n
assert len({r['binding']['snapshot_sha256'] for r in records})==n
for record in records:
 samples=[t['sample_id'] for b in record['branches'] for t in b['trials']];assert len(samples)==len(set(samples)), 'duplicate actual invocation label'
assert all(r['source_split']=='train' and r['identity_domain']=='own_original_train_layout' and not r['PRO'] and not r['confirmation'] for r in records)
assert all(m['source_revision']==manifests[0]['source_revision'] and m['policy_hashes']==manifests[0]['policy_hashes'] for m in manifests)
a.output.mkdir(parents=True,exist_ok=False);data=a.output/'positions.jsonl';data.write_bytes(b''.join(json.dumps(r,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()+b'\n' for r in records))
manifest={**manifests[0],'positions':n,'registered_cases':65,'preview':a.allow_incomplete,'unresolved_cases':[r for m in manifests for r in m['unresolved_cases']],'data':ref(data),'by_category':dict(Counter(r['case']['category'] for r in records)),'source_packets':sources,'manifest_scope':'two disjoint complete measured packets; per-row actual state/request binding retained','source_manifests':[m['manifest'] for m in manifests],'label_exporters_per_packet':[m.get('label_exporter') for m in manifests]};manifest.pop('manifest',None);manifest.pop('label_exporter',None);(a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
trials=[t for w in workers for t in w['result']['trials']];assert len(trials)==n*11
invariants=[{'case':w['case']['name'],'same_complete_physics':len({t['initial_physics_sha256'] for t in w['result']['trials']})==1,'same_initial_request':len({t['request_sha256'] for t in w['result']['trials']})==1,'self':sum(t['method']=='self' for t in w['result']['trials']),'vla':sum(t['method']=='call_vla' for t in w['result']['trials'])} for w in workers]
assert all(r['same_complete_physics'] and r['same_initial_request'] and r['self']==2 and r['vla']==9 for r in invariants)
rawgroups=defaultdict(list)
for w in workers:
 for t in w['result']['trials']:
  variant='self' if t['method']=='self' else t['vla_variant']['name'];rawgroups[(w['case']['category'],variant)].append(t)
rawstats=[{'category':c,'requested_variant':v,'n':len(ts),'known_truth':sum(type(t['success']) is bool for t in ts),'unknown_truth':sum(type(t['success']) is not bool for t in ts),'success':sum(t['success'] is True for t in ts),'native_controls':sum(t.get('sim_steps',0) for t in ts),'inference_calls':sum(t.get('vla_inference_calls',0) for t in ts),'zero_control_attempts':sum(not t.get('sim_steps') for t in ts),'reason_counts':dict(Counter(t['reason'] for t in ts))} for (c,v),ts in sorted(rawgroups.items())]
protocol={'states':n,'attempts':n*11,'self_attempts':n*2,'vla_variant_attempts':n*9,'phases':dict(Counter(r['case']['saved_start_phase'] for r in records)),'request_bound_trials':sum(len(b['trials']) for r in records for b in r['branches']),'unknown_context_trials':sum(len(r['unknown_trials']) for r in records),'same_state_request_invariants':invariants,'requested_variant_stats':rawstats,'training':False,'PRO':False,'D2':False,'confirmation':False,'scope':'repeated measured branches, not independent state-generalization rates'}
assert protocol['request_bound_trials']+protocol['unknown_context_trials']==n*11
(a.output/'protocol_and_raw_attempts.json').write_text(json.dumps(protocol,indent=2)+'\n')
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');cmd=[str(R/'.venv/bin/python'),str(R/'validate_B2_measured_C2_CPU_20261021.py'),'--consumer',export['consumer'],'--schema',str(Path(export['source'])/'rpent/skill_package/schema.json'),'--package',str(a.output)]
with (a.output/'consumer_validation.log').open('x') as f:subprocess.run(cmd,check=True,env=env,stdout=f,stderr=subprocess.STDOUT)
intake=json.loads((a.output/'C2_intake_validation.json').read_bytes());delivery={'package':str(a.output),'source_commit':manifest['source_revision'],'positions':n,'attempts':n*11,'preview':a.allow_incomplete,'request_bound_trials':protocol['request_bound_trials'],'unknown_context_trials':protocol['unknown_context_trials'],'consumer_statuses':dict(Counter(r['status'] for r in intake['rows'])),'coverage_issue_states':len(intake['coverage_issues']),'artifacts':{name:ref(a.output/name) for name in ['positions.jsonl','manifest.json','C2_intake_validation.json','metrics.json','protocol_and_raw_attempts.json']},'PRO':False,'D2':False,'confirmation':False,'training_executed':False};(a.output/'C2_delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery))
