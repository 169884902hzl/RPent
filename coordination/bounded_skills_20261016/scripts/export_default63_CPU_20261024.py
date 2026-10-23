"""Export three repeats while preserving each registered default's old binding."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys


def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prior-export-manifest',type=Path,required=True)
    p.add_argument('--allow-incomplete',action='store_true')
    a=p.parse_args();plan=json.loads(a.manifest.read_bytes())
    assert plan['source_split']=='train' and plan['requested_repeats']==3
    assert plan['original_binding_preserved'] and not plan['training'] and not plan['confirmation']
    sys.path.insert(0,plan['source'])
    from coordination.bounded_skills_20261016.scripts.export_original_schema6_measured_CPU_20261021 import digest,reference
    prior=json.loads(a.prior_export_manifest.read_bytes())
    helper=module('default63_measured_export',prior['measurement_helper']['path'])
    checked=helper.checked
    assert reference(checked(prior['measurement_helper']))==prior['measurement_helper']
    prompt=module('default63_prompt_evidence',checked(prior['prompt_helper'])).invocation_prompt
    hashes={Path(name).name:sha for sha,name in (line.split(maxsplit=1)
        for line in checked(prior['policy_hashes_source']).read_text().splitlines())}
    policy_revision='pi05-libero-sha256:'+digest(hashes)
    rows=[];pending=[];sources=[]
    for i,job in enumerate(plan['jobs']):
        pointer=a.results/f'closed_{i:03d}.json'
        if not pointer.is_file():pending.append(job['query']);continue
        raw=json.loads(pointer.read_bytes());report=json.loads(checked(raw).read_bytes());sources.append(raw)
        query=json.loads(checked(job['query']).read_bytes())
        assert report['registered_query']==job['query'] and report['old_binding_preserved']
        assert query['split']=='train' and query['training_admission']
        assert not any(query[k] for k in ('PRO','D2','confirmation'))
        row=helper.measured_row(query,report,policy_revision,prompt)
        for branch in row['branches']:
            known=[]
            for trial in branch['trials']:
                if trial['success'] is None:
                    row['unknown_trials'].append({'seed':trial['seed'],'reason':'private_truth_unknown',
                        'evidence':trial['evidence']})
                else:
                    assert type(trial['success']) is bool
                    known.append(trial)
            branch['trials']=known
        row.update(source_split='train',evaluation_only=False,
            training_admission=any(b['trials'] for b in row['branches']),
            training_executed=False,source=raw,registered_query=job['query'],
            requested_repeats=3,old_binding_preserved=True,
            label_merge_scope='exact frozen binding only; supplement this default candidate')
        rows.append(row)
    if not a.allow_incomplete:assert not pending,pending
    a.output.mkdir(parents=True,exist_ok=False)
    data=a.output/'positions.jsonl';data.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    manifest={'version':'measured-subtask-choice/2','data':reference(data),'positions':len(rows),
        'registered_queries':len(plan['jobs']),'pending':pending,'requested_repeats':3,
        'bound_trials':sum(len(b['trials']) for r in rows for b in r['branches']),
        'unknown_trials':sum(len(r['unknown_trials']) for r in rows),
        'by_category':dict(Counter(r['case']['category'] for r in rows)),
        'by_skill':dict(Counter(b['method_family'] for r in rows for b in r['branches'])),
        'old_binding_preserved':True,'raw_sources':sources,'source_manifest':reference(a.manifest),
        'source_queries':plan['source_queries'],'source_revision':plan['source_commit'],
        'libero_config':plan['libero_config'],'excluded_holdout_queries':plan['excluded_holdout_queries'],
        'policy_revision':policy_revision,'policy_hashes_source':prior['policy_hashes_source'],
        'measurement_helper':prior['measurement_helper'],'prompt_helper':prior['prompt_helper'],
        'exporter':reference(Path(__file__)),'source_split':'train','training_executed':False,
        'training_admission':True,'PRO':False,'D2':False,'confirmation':False}
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k!='raw_sources'}))


if __name__=='__main__':main()
