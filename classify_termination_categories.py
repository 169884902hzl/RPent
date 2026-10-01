#!/usr/bin/env python3
import argparse,json,hashlib
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
    ap=argparse.ArgumentParser(); ap.add_argument('--manifest',required=True); ap.add_argument('--out',required=True); args=ap.parse_args()
    manifest_path=Path(args.manifest)
    sources=json.loads(manifest_path.read_text())['sources']
    declared={item['path']:item['sha256'] for item in sources}
    ledgers=[Path(item['path']) for item in sources if Path(item['path']).name=='episodes.jsonl']
    if not ledgers: raise ValueError('manifest contains no explicit episode ledger')
    rows=[]; counts=Counter(); by_suite=defaultdict(Counter); by_reason=defaultdict(list)
    for ledger in ledgers:
      data=ledger.read_bytes()
      if hashlib.sha256(data).hexdigest()!=declared[str(ledger)]: raise ValueError(f'source hash mismatch: {ledger}')
      for line in data.decode().splitlines():
        record=json.loads(line); r=record['result']; p=Path(record['output_dir'])/'result.json'
        cp=p.parent/'choices.jsonl'; choices=[]
        if str(cp) not in declared: raise ValueError(f'choice file not declared in manifest: {cp}')
        choice_data=cp.read_bytes()
        if hashlib.sha256(choice_data).hexdigest()!=declared[str(cp)]: raise ValueError(f'source hash mismatch: {cp}')
        choices=[json.loads(line) for line in choice_data.decode().splitlines()]
        cat,detail=classify(r,choices)
        row={'result':str(p),'suite':r.get('suite'),'task':r.get('task'),'seed':r.get('seed'),'status':r.get('status'),'decisions':r.get('decisions'),'official_success':bool(r.get('official_success')),'correct_finish':bool(r.get('correct_finish')),'category':cat,'detail':detail}
        rows.append(row); counts[cat]+=1; by_suite[r.get('suite','unknown')][cat]+=1; by_reason[cat].append(str(p))
    out={'manifest':str(manifest_path),'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),'source_files':sources,'classification_only_original_results_unchanged':True,'physical_success':sum(r['official_success'] for r in rows),'correct_finish':sum(r['correct_finish'] for r in rows),'category_vocabulary':['completion_judgment','no_legal_candidate','perception_missing_object','skill_execution_failure','over_token','budget_exhausted','startup_error'],'count':len(rows),'counts':dict(counts),'by_suite':{k:dict(v) for k,v in sorted(by_suite.items())},'episodes':rows}
    Path(args.out).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'count':len(rows),'counts':dict(counts),'by_suite':{k:dict(v) for k,v in sorted(by_suite.items())}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
