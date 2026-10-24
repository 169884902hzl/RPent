"""Summarize closed physical panel records without mixing source versions or N modes."""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,hashlib,json,math,statistics

def wilson(s,n):
 if not n:return None
 z=1.959963984540054;p=s/n;c=(p+z*z/(2*n))/(1+z*z/n);r=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
 return [c-r,c+r]

def quantile(values,q):
 if not values:return None
 v=sorted(values);p=(len(v)-1)*q;lo=int(p);return v[lo]+(v[min(lo+1,len(v)-1)]-v[lo])*(p-lo)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();groups=defaultdict(list);seen=set();evidence=[]
 for pointer in sorted((a.board/'results').glob('*/closed_*.json')):
  ref=json.loads(pointer.read_bytes());path=Path(ref['path']);raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==ref['sha256'],path
  for result in json.loads(raw)['results']:
   key=(result['source_commit'],result['panel'],result['category'],result['line']);identity=(*key,result['world_id'])
   assert identity not in seen,identity
   seen.add(identity);groups[key].append(result);evidence.append({'closed_pointer':str(pointer),'result':ref,'world':result['world_id'],'line':result['line'],'complete_initial':result['initial_physics_sha256']})
 rows=[];cases=[]
 for key,results in sorted(groups.items()):
  cycles=[];failures=Counter();sams=[];controls=[];anchor_counts=[];candidate_counts=[];all_stages=defaultdict(list)
  for result in results:
   path=Path(result['choices']['path']);raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==result['choices']['sha256']
   records=[json.loads(x) for x in raw.splitlines()];stages=defaultdict(list)
   for record in records:
    timing=record.get('timing',{});cycles.append(timing.get('wall_s'))
    for k,v in timing.get('four_stage_s',{}).items():stages[k].append(v)
    exclusive=timing.get('main_thread_exclusive_s',{})
    collection=timing.get('main_thread_exclusive_by_root_s',{}).get('collection.failure_history',{})
    stages['failure_history_collection_inclusive'].append(sum(collection.values()))
    collection_execution=sum(v for k,v in collection.items()
        if not k.startswith(('perception.','planning.','private_labels.')))
    stages['execution_without_failure_collection'].append(
        max(0.,timing.get('four_stage_s',{}).get('execution',0.)-collection_execution))
    stages['planning_inclusive_within_candidates_execution'].append(sum(v for k,v in exclusive.items() if k.startswith('planning.')))
    stages['pi_inference'].append(exclusive.get('vla.inference',0.))
    stages['oracle_successor_legal'].append(timing.get('oracle_successor_legal_s',0.))
    request=record['request'];anchor_counts.append(len(request['anchors']));candidate_counts.append(len(request['candidates']))
    sams.append(sum(v for k,v in timing.get('calls',{}).items() if k=='perception.segmentation:call'))
    for receipt in record.get('receipts',[]):
     controls.append(receipt['steps_used'])
     if receipt['outcome']!='success':failures[(receipt['skill'],receipt['phase'],receipt['stop_reason'],receipt['steps_used']==0)]+=1
   for stage,values in stages.items():all_stages[stage].extend(values)
   cases.append({'source':key[0],'panel':key[1],'category':key[2],'line':key[3],'world_id':result['world_id'],'success':result['success'],'decisions':result['decisions'],'wall_s':result['wall_s'],'sim_steps':result['sim_steps'],'complete_initial':result['initial_physics_sha256'],'stages_median_per_cycle_s':{k:statistics.median(v) for k,v in stages.items() if v},'summary_choices':result['choices']})
  cycles=[x for x in cycles if x is not None];s=sum(bool(x['success']) for x in results);n=len(results)
  rows.append({'source':key[0],'panel':key[1],'category':key[2],'line':key[3],'success':s,'n':n,'wilson95':wilson(s,n),'cycle_s_median':statistics.median(cycles) if cycles else None,'cycle_s_p90':quantile(cycles,.9),'episode_s_median':statistics.median([x['wall_s'] for x in results]),'decisions_median':statistics.median([x['decisions'] for x in results]),'sim_steps_median':statistics.median([x['sim_steps'] for x in results]),'SAM_calls_per_cycle_median':statistics.median(sams) if sams else None,'anchor_count_range':[min(anchor_counts),max(anchor_counts)] if anchor_counts else None,'candidate_count_range':[min(candidate_counts),max(candidate_counts)] if candidate_counts else None,'failure_counts':[{'skill':k[0],'phase':k[1],'reason':k[2],'zero_control':k[3],'n':v} for k,v in failures.most_common()]})
  rows[-1]['stages_median_per_cycle_s']={stage:statistics.median(values) for stage,values in all_stages.items() if values}
 a.output.mkdir(parents=True,exist_ok=False)
 (a.output/'summary.json').write_text(json.dumps({'rows':rows,'cases':cases,'evidence':evidence,'latency_scope':'parallel-world worker wall; actual N is in the shard manifest; not N1 latency or GPU throughput','planning_note':'planning breakdown is subset of candidates/execution; do not add as a seventh disjoint stage','collection_note':'failure_history_collection_inclusive overlaps the four original stages; execution_without_failure_collection subtracts only collection time classified as execution; no collection is performed by the PRO model line'},indent=2)+'\n')
 lines=['| 源码 | 面板 | 类别 | 线 | 成功/闭合 | Wilson95% | 决策循环中位s | 整局中位s | 决策中位 |','|---|---|---|---|---:|---:|---:|---:|---:|']
 for x in rows:
  ci=x['wilson95'];lines.append(f"| {x['source'][:8]} | {x['panel']} | {x['category']} | {x['line']} | {x['success']}/{x['n']} | {100*ci[0]:.1f}–{100*ci[1]:.1f}% | {x['cycle_s_median']:.3f} | {x['episode_s_median']:.2f} | {x['decisions_median']:.1f} |")
 (a.output/'table.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'groups':len(rows),'closed_line_episodes':len(cases),'summary':str(a.output/'summary.json')}))

if __name__=='__main__':main()
