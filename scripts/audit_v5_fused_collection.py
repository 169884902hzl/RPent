"""Audit only declared episode manifests from one original collection ledger."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ledger',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--require-episodes',type=int)
    args=parser.parse_args()
    episodes=list(map(json.loads,args.ledger.read_text().splitlines()))
    if args.require_episodes is not None:
        assert len(episodes)==args.require_episodes
    counts=Counter();questions=Counter();lengths=[];descriptors=[];failures=[]
    for episode in episodes:
        result=episode['result'];identity=episode['episode']
        assert identity['suite'] in ('libero_spatial','libero_object','libero_goal','libero_10')
        assert 10<=identity['seed']<40
        manifest=Path(episode['output_dir'])/'training_manifest.json'
        m=json.loads(manifest.read_text())
        counts.update(m['counts'])
        counts['episodes']+=1;counts['official_success']+=bool(result.get('official_success'))
        counts['explicit_finish']+=bool(result.get('correct_finish'))
        for bucket in ('train','auxiliary'):
            d=m['files'][bucket];path=Path(d['path'])
            assert sha(path)==d['sha256']
            rows=list(map(json.loads,path.read_text().splitlines()));assert len(rows)==d['rows']
            for row in rows:
                assert row['schema_version']=='entities-plan-receipt/3.1'
                assert row['split']=='train' and 10<=row['seed']<40
                assert row['coordinate_quality']['dual_view_fusion']
                assert isinstance(row['perception_measurement_evidence'],dict)
                assert row['prompt_tokens']<=3072 and row['prompt_tokens']>0
                state=row['request']['state']
                assert not any(s in state for s in ('sim_truth','BDDL','obj_','zone_'))
                assert row.get('judge') in ('measured_predicate','physics_branch','plan_oracle','program_termination'),row.get('judge')
                assert all(len(q['criteria'])<=24 for q in row['request']['questions'].values())
                questions[row['question_type']]+=1;lengths.append(row['prompt_tokens'])
                if bucket=='train':
                    criteria=row['request']['questions']['action']['criteria']
                    counts['positive_finish_rows']+=any(c in row['acceptable_actions'] and text=='finish()' for c,text in criteria.items())
            descriptors.append({'episode':identity,'bucket':bucket,**d,'episode_manifest':str(manifest),'episode_manifest_sha256':sha(manifest)})
        if not result.get('official_success'):
            failures.append({'episode':identity,'termination_category':result.get('termination_category'),'error':result.get('error')})
    assert counts['next_skill']>0 and counts['auxiliary']>0
    report={'purpose':'original measured fused partial collection audit; not admission to current frozen training',
            'source_ledger':str(args.ledger),'source_ledger_sha256':sha(args.ledger),
            'files':descriptors,'counts':dict(counts),'question_counts':dict(questions),
            'prompt_p95':sorted(lengths)[math.ceil(len(lengths)*.95)-1],'prompt_max':max(lengths),
            'failures':failures,'request_schema_length_seed_and_provenance_checks':True,
            'PRO_human_sealed_inputs_read':False,'Jev_training_labels_used':False,
            'script_sha256':sha(__file__)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'counts':report['counts'],'questions':report['question_counts'],
                      'p95':report['prompt_p95'],'max':report['prompt_max'],'manifest':str(args.output),'sha256':sha(args.output)}))


if __name__=='__main__':
    main()
