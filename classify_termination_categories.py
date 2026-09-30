#!/usr/bin/env python3
import argparse,json
from pathlib import Path
from collections import Counter,defaultdict

def classify(result, choices):
    if result.get('status') in ('startup_error','error'):
        err=str(result.get('error','')).lower()
        if 'token' in err or '2048' in err or '3072' in err:
            return 'over_token','exception:'+str(result.get('error'))
        if result.get('status')=='startup_error':
            return 'startup_error',str(result.get('error',''))
        return 'skill_execution_failure',str(result.get('error',''))
    if result.get('official_success') and result.get('correct_finish'):
        return 'completion_judgment','correct_finish'
    rows=choices
    last=rows[-1] if rows else {}
    selected=str(last.get('selected',''))
    receipt=last.get('receipt') or {}
    if result.get('false_finish') or selected.startswith('finish('):
        return 'completion_judgment','false_finish' if not result.get('official_success') else 'finish'
    if selected.startswith('ask_help('):
        ann=last.get('oracle_annotation') or {}
        if ann.get('source_entity') is None or ('target_entity' in ann and ann.get('target_entity') is None):
            return 'perception_missing_object',json.dumps(ann,sort_keys=True)
        return 'no_legal_candidate',json.dumps(ann,sort_keys=True)
    if receipt.get('verification')=='execution_error' or receipt.get('error'):
        return 'skill_execution_failure',str(receipt.get('error',''))
    if result.get('budget_exhausted') or result.get('native_truncated'):
        return 'budget_exhausted','budget/truncated'
    if rows and len(rows)>=1 and result.get('decisions')==1:
        ann=last.get('oracle_annotation') or {}
        if ann and (ann.get('source_entity') is None or ('target_entity' in ann and ann.get('target_entity') is None)):
            return 'perception_missing_object',json.dumps(ann,sort_keys=True)
    if result.get('decisions',0)>0:
        return 'budget_exhausted','decision loop ended without explicit terminal cause'
    return 'skill_execution_failure','no decision trace'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('dirs',nargs='+'); ap.add_argument('--out',required=True); args=ap.parse_args()
    rows=[]; counts=Counter(); by_suite=defaultdict(Counter); by_reason=defaultdict(list)
    for root in map(Path,args.dirs):
      for p in sorted(root.glob('libero_*_t*_s*/result.json')):
        try:r=json.loads(p.read_text())
        except Exception as e: continue
        cp=p.parent/'choices.jsonl'; choices=[]
        if cp.exists():
          for line in cp.read_text().splitlines():
            try: choices.append(json.loads(line))
            except: pass
        cat,detail=classify(r,choices)
        row={'result':str(p),'suite':r.get('suite'),'task':r.get('task'),'seed':r.get('seed'),'status':r.get('status'),'decisions':r.get('decisions'),'category':cat,'detail':detail}
        rows.append(row); counts[cat]+=1; by_suite[r.get('suite','unknown')][cat]+=1; by_reason[cat].append(str(p))
    out={'category_vocabulary':['completion_judgment','no_legal_candidate','perception_missing_object','skill_execution_failure','over_token','budget_exhausted','startup_error'],'count':len(rows),'counts':dict(counts),'by_suite':{k:dict(v) for k,v in sorted(by_suite.items())},'episodes':rows}
    Path(args.out).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'count':len(rows),'counts':dict(counts),'by_suite':{k:dict(v) for k,v in sorted(by_suite.items())}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
