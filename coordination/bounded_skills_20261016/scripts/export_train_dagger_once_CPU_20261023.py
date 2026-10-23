"""Export one-repeat train measurements with explicit fresh-context replacements."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys


def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
    return loaded


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--policy-hashes',type=Path,required=True)
    p.add_argument('--measurement-helper',type=Path,required=True)
    p.add_argument('--prompt-helper',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allow-incomplete',action='store_true')
    a=p.parse_args();sys.path.insert(0,str(a.source))
    helper=module('existing_measured_export',a.measurement_helper)
    measured_row,checked=helper.measured_row,helper.checked
    from coordination.bounded_skills_20261016.scripts.export_original_schema6_measured_CPU_20261021 import reference, digest
    invocation_prompt=module('registered_prompt_provenance',a.prompt_helper).invocation_prompt
    plan=json.loads(a.manifest.read_bytes())
    assert plan['training_split_collection'] and not plan['training'] and plan['requested_repeats']==1
    assert not any(plan[k] for k in ('PRO','D2','confirmation'))
    hashes={Path(name).name:sha for sha,name in (line.split(maxsplit=1) for line in a.policy_hashes.read_text().splitlines())}
    assert set(hashes)=={'model.safetensors','metadata.pt'}
    policy_revision='pi05-libero-sha256:'+digest(hashes)
    exported=[];unknown=[];pending=[];replacements=[];raw_closed=[]
    for i,job in enumerate(plan['jobs']):
        pointer=a.results/f'closed_{i:03d}.json'
        if not pointer.is_file():
            pending.append({'source_order':job['source_order'],'query':job['query']})
            continue
        source=json.loads(pointer.read_bytes());report=json.loads(checked(source).read_bytes())
        raw_closed.append(source)
        original=json.loads(checked(job['query']).read_bytes())
        assert original['split']=='train' and original['training_admission']
        if report['status']=='unknown':
            assert not report['candidate_measured'] and not report['training_admission']
            unknown.append({'source_order':job['source_order'],'query_id':original['query_id'],
                'record_id':original['record_id'],'reason':report['reason'],
                'prefix_physically_reached':report['prefix_physically_reached'],
                'raw':source,'training_admission':False})
            continue
        assert report['status']=='physical_result' and report['requested_repeats']==1
        query=json.loads(checked(report['registered_query']).read_bytes())
        assert query['split']=='train' and query['scope_kind']=='registered_original_train_dagger'
        assert query['prefix']==[] and query['binding']['prefix']==[]
        assert not any(query[k] for k in ('PRO','D2','confirmation'))
        query.update(record_aliases=[],source_episode_id=report['case']['name'],requested_valid_repeats=1)
        bound_report={**report,'binding':query['binding'],'query_id':query['query_id']}
        row=measured_row(query,bound_report,policy_revision,invocation_prompt)
        for branch in row['branches']:
            known=[]
            for trial in branch['trials']:
                if trial['success'] is None:
                    row['unknown_trials'].append({'seed':trial['seed'],'reason':'private_truth_unknown',
                        'evidence':trial['evidence']})
                else:
                    assert isinstance(trial['success'],bool)
                    known.append(trial)
            branch['trials']=known
        row.update(training_admission=any(b['trials'] for b in row['branches']),
            evaluation_only=False,source_split='train',source=source,
            original_query=job['query'],requested_repeats=1,
            label_merge_scope='new physically reached context only; explicit replacement, no old-binding backfill',
            replacement_mapping=report['replacement_mapping'],
            prefix_evidence=report['prefix_evidence'],
            one_trial_is_not_three_trial_acceptability_evidence=True)
        exported.append(row)
        replacements.append({'source_order':job['source_order'],**report['replacement_mapping'],
            'original_query':job['query'],'registered_query':report['registered_query'],
            'operation':'replace context only after consumer acknowledges; never silently attach new outcome to old binding'})
    if not a.allow_incomplete:assert not pending,pending
    a.output.mkdir(parents=True,exist_ok=False)
    for name,rows in [('positions',exported),('unknown',unknown),('pending',pending),('replacements',replacements)]:
        (a.output/f'{name}.jsonl').write_text(''.join(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n' for r in rows))
    manifest={'version':'measured-subtask-choice/2','data':reference(a.output/'positions.jsonl'),
        'positions':len(exported),'registered_queries':len(plan['jobs']),'raw_closed':len(raw_closed),
        'bound_trials':sum(len(b['trials']) for r in exported for b in r['branches']),
        'unknown_trials':sum(len(r['unknown_trials']) for r in exported),
        'unreached_or_unavailable_contexts':len(unknown),'pending_queries':len(pending),
        'by_category':dict(Counter(r['case']['category'] for r in exported)),
        'by_skill':dict(Counter(b['method_family'] for r in exported for b in r['branches'])),
        'unknown':reference(a.output/'unknown.jsonl'),'replacements':reference(a.output/'replacements.jsonl'),
        'source_manifest':reference(a.manifest),'source_queries':plan['source_queries'],
        'policy_revision':policy_revision,'policy_hashes':hashes,'policy_hashes_source':reference(a.policy_hashes),
        'raw_sources':raw_closed,'exporter':reference(Path(__file__)),
        'measurement_helper':reference(a.measurement_helper),
        'prompt_helper':reference(a.prompt_helper),
        'training_executed':False,'training_admission':True,'source_split':'train',
        'PRO':False,'D2':False,'confirmation':False,'repeats_each':1,
        'scope':'source-registered next-subgoal outcomes in new actual reached context; no old-context labels',
        'one_trial_is_not_three_trial_acceptability_evidence':True}
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ('raw_sources','policy_hashes')}))


if __name__=='__main__':main()
