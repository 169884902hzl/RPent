"""Convert only manifest-listed RPent audit/recipe pairs, for evaluation."""
import argparse
import hashlib
import json
from pathlib import Path

from robots.libero.rpent_semantic_cards import convert_recipe
from robots.libero.v5_cards import VERSION, validate_card


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--raw-index-manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    manifest=json.loads(a.raw_index_manifest.read_text())
    if not manifest.get('evaluation_only') or manifest.get('training_allowed') is not False:
        raise ValueError('RPent conversion must be evaluation only')
    a.output.mkdir(parents=True,exist_ok=False)
    results=[]
    for item in manifest['indexes']:
        path=Path(item['path'])
        if sha(path)!=item['sha256']:raise ValueError('RPent raw index changed')
        index=json.loads(path.read_text());audit=None;commands=None;sources=[]
        for descriptor in index['files']:
            name=descriptor['name']
            if not (name.startswith('task-specific/') and (name.endswith('_recipe.jsonl') or name.endswith('.json'))):continue
            file=Path(descriptor['path'])
            if sha(file)!=descriptor['sha256']:raise ValueError('RPent source changed')
            sources.append(descriptor)
            if name.endswith('_recipe.jsonl'):commands=list(map(json.loads,file.read_text().splitlines()))
            else:audit=json.loads(file.read_text())
        episode=item['episode']
        if audit is None or commands is None:
            results.append({'episode':episode,'complete_mapping':False,'reason':'source audit/recipe missing','sources':sources})
            continue
        if audit.get('seed')!=0:raise ValueError('recipe anchor audit is not init0')
        steps,evidence,unmapped=convert_recipe(commands,audit)
        card={'version':VERSION,'origin':'rpent_eval','steps':steps,'evaluation_only':True,
              'training_allowed':False,'complete_mapping':bool(steps) and not unmapped,
              'source_episode':episode,'sources':sources,'conversion_evidence':evidence,'unmapped':unmapped}
        if steps:validate_card(card)
        dest=a.output/(f"{episode['suite']}_t{episode['task']}.json")
        dest.write_text(json.dumps(card,indent=2))
        results.append({'episode':episode,'path':str(dest),'sha256':sha(dest),
                        'source_commands':len(commands),'semantic_steps':len(steps),'mapped_commands':len(evidence),
                        'unmapped_commands':len(unmapped),'complete_mapping':card['complete_mapping']})
    report={'evaluation_only':True,'training_allowed':False,'source_index_sha256':sha(a.raw_index_manifest),
            'files':results,'episodes':len(results),'complete_cards':sum(x['complete_mapping'] for x in results),
            'commands':sum(x.get('source_commands',0) for x in results),
            'mapped_commands':sum(x.get('mapped_commands',0) for x in results),
            'unmapped_commands':sum(x.get('unmapped_commands',0) for x in results),
            'limit':'This explicit development index is not the full75-script/final80 coverage; unverified mappings remain excluded from complete cards'}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='files'}))


if __name__=='__main__':main()
