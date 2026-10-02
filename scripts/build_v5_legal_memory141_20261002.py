"""Extend pinned original oracle cards with original-only skill evidence."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics

from robots.libero.v5_cards import validate_card
from robots.libero.v5_manual import GENERAL_RULES


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--cards',type=Path,required=True);p.add_argument('--expert-summary',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--tokenizer',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    cm=json.loads(a.cards.read_text());expert=json.loads(a.expert_summary.read_text())
    if cm.get('origin')!='original_oracle' or cm.get('RPent_cards_in_training'):
        raise ValueError('legal memory accepts original oracle cards only')
    if not expert['complete_protocol'] or expert['attempted']!=200:raise ValueError('incomplete original expert evidence')
    cardfiles=[]
    for descriptor in cm['files']:
        source=Path(descriptor['path'])
        if digest(source)!=descriptor['sha256']:raise ValueError('card changed')
        card=json.loads(source.read_text());validate_card(card)
        if card['origin']!='original_oracle':raise ValueError('non-original card')
        dest=a.output/'task_cards'/source.name;dest.parent.mkdir(exist_ok=True)
        dest.write_text(json.dumps(card,indent=2))
        cardfiles.append({**descriptor,'path':str(dest),'sha256':digest(dest)})
    skills=defaultdict(Counter);heights=defaultdict(list);sources=[];lessons=Counter()
    for entry in expert['episodes']:
        ep=entry['episode']
        if ep['suite'] not in ('libero_spatial','libero_object','libero_goal','libero_10') or not 0<=ep['seed']<5:
            raise ValueError('memory evidence outside registered original development tasks')
        path=Path(entry['output'])/'choices.jsonl'
        sources.append({'episode':ep,'path':str(path),'sha256':digest(path),'termination':entry['result']['termination_category']})
        lessons[entry['result']['termination_category']]+=1
        for row in map(json.loads,path.read_text().splitlines()):
            receipt=row['receipt'];entities={e['id']:e for e in row['measurements']}
            if receipt.get('tool') not in ('grasp','regrasp_restage'):continue
            obj=entities.get(receipt.get('object'))
            if obj is None:continue
            name=obj['name'];stats=skills[name];stats['attempts']+=1
            stats['visual_verified']+=receipt.get('grasp_verified') is True
            stats['execution_error']+=bool(receipt.get('error'))
            stats['approach/'+receipt.get('approach',receipt.get('mode','unknown'))]+=1
            if receipt.get('grasp_verified') is True and row.get('motion_evidence'):
                target=row['motion_evidence'][0].get('target_xyz')
                if target is not None:heights[name].append(target[2]-obj['upper'][2])
    profiles=[]
    for name,count in sorted(skills.items()):
        profiles.append({'category':name,**dict(count),'visual_success_rate':count['visual_verified']/count['attempts'],
                         'verified_staging_height_median_above_measured_top':statistics.median(heights[name]) if heights[name] else None,
                         'source_scope':'original tasks only; estimates are not PRO-tuned and do not encode scene coordinates'})
    (a.output/'object_skill_cards.json').write_text(json.dumps({'profiles':profiles,'provenance':sources},indent=2))
    rules=[{'trigger':'grasp verification fails','response':'remeasure the same object, select another measured approach or restage','source_count':lessons['grasp_failure_abandonment']},
           {'trigger':'waypoint execution_error','response':'inspect measured obstacle/pose evidence before changing the approach; keep the error receipt','source_count':lessons['skill_execution_error']},
           {'trigger':'required entity missing','response':'query instruction nouns and a second calibrated view; request no unseen pose','source_count':lessons['perception_missing_object']},
           {'trigger':'task not complete','response':'continue within the episode; do not treat execution as success','source_count':lessons['budget_exhausted']}]
    (a.output/'failure_lessons.json').write_text(json.dumps({'rules':rules,'original_terminal_counts':dict(lessons),'source_summary_sha256':digest(a.expert_summary)},indent=2))
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(a.tokenizer,trust_remote_code=True,local_files_only=True)
    tokens=len(tokenizer.encode(GENERAL_RULES,add_special_tokens=False))
    if tokens>300:raise ValueError('general manual exceeds 300 tokens')
    (a.output/'general_rules.txt').write_text(GENERAL_RULES+'\n')
    manifest={'origin':'original_oracle','RPent_cards_in_training':False,'PRO_inputs_used':False,
              'cards':cardfiles,'task_card_count':len(cardfiles),'object_categories':len(profiles),
              'general_rules_tokens':tokens,'general_rules_max_tokens':300,
              'source_card_manifest':str(a.cards),'source_card_manifest_sha256':digest(a.cards),
              'source_expert_summary':str(a.expert_summary),'source_expert_summary_sha256':digest(a.expert_summary),
              'files':{name:{'path':str(a.output/name),'sha256':digest(a.output/name)} for name in ('object_skill_cards.json','failure_lessons.json','general_rules.txt')},
              'scope':'task-type/category skill/failure memory from original tasks; no absolute coordinates in card steps; evidence paths and seeds remain provenance metadata'}
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'task_cards':len(cardfiles),'object_categories':len(profiles),'general_rules_tokens':tokens,'manifest_sha256':digest(a.output/'manifest.json')}))


if __name__=='__main__':main()
