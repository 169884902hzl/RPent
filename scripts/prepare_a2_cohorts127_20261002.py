# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Register three explicit development memory conditions, never training data."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for key in ('cohort','raw-manifest','converted-manifest','budget-manifest','output'):
        p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--source', required=True)
    a=p.parse_args()
    cohort=json.loads(a.cohort.read_text())
    raw=json.loads(a.raw_manifest.read_text())
    converted=json.loads(a.converted_manifest.read_text())
    assert raw['evaluation_only'] and converted['evaluation_only']
    assert not raw['training_allowed'] and not converted['training_allowed']
    raw_index={(x['episode']['suite'],x['episode']['task']):x for x in raw['indexes']}
    cards={(x['suite'],x['task']):x for x in converted['files']}
    assert len(cohort['episodes'])==40 and all(x['seed']==40 for x in cohort['episodes'])
    budget=json.loads(a.budget_manifest.read_text())['budget']
    a.output.mkdir(parents=True,exist_ok=False)
    plans=[]
    for condition in ('N','M','Mc'):
        episodes=[]
        for episode in cohort['episodes']:
            e=copy.deepcopy(episode)
            key=e['suite'],e['task']
            if condition=='M':
                item=raw_index[key]
                assert sha(item['path'])==item['sha256']
                e['rpent_memory_index']=item['path']
            elif condition=='Mc':
                item=cards.get(key)
                e['card_mapping_status']='no_recipe' if item is None else 'no_mappable_steps' if not item['mapped_steps'] else 'partial_mapping' if not item['complete_mapping'] else 'complete_mapping'
                if item is not None and item['mapped_steps']:
                    assert sha(item['path'])==item['sha256']
                    e['card']=item['path']
                    e['card_sha256']=item['sha256']
            episodes.append(e)
        plan={'purpose':'A2-'+condition+' same stock vLLM development40, not final or freeze',
              'libero_type':'pro','budget':budget,'episodes':episodes,
              'model_revision':'e89b16ebf1988b3d6befa7de50abc2d76f26eb09',
              'evaluation_only':True,'training_allowed':False,
              'memory_condition':condition,'source':a.source,
              'partial_recipe_policy':'Use only mapped category steps; preserve missing/unmapped counts, never claim full recipe conversion'}
        path=a.output/(condition+'.json')
        path.write_text(json.dumps(plan,indent=2)+'\n')
        plans.append({'condition':condition,'path':str(path),'sha256':sha(path),'episodes':40,
                      'with_card':sum('card' in x for x in episodes),'no_recipe_or_empty':sum(x.get('card_mapping_status') in ('no_recipe','no_mappable_steps') for x in episodes)})
    report={'plans':plans,'cohort_sha256':sha(a.cohort),'raw_manifest_sha256':sha(a.raw_manifest),
            'converted_manifest_sha256':sha(a.converted_manifest),'budget_manifest_sha256':sha(a.budget_manifest),
            'evaluation_only':True,'training_allowed':False,'generator_sha256':sha(__file__)}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
