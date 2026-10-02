# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare explicit original repair conditions; no dev/final episode changes."""

import argparse
import collections
import hashlib
import json
import statistics
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    groups={}
    sources=[]
    for condition in ('baseline','grasp','parts','placement'):
        ledger=a.results/condition/'episodes.jsonl'
        if not ledger.exists():continue
        records=[json.loads(line) for line in ledger.read_text().splitlines()]
        causes=collections.Counter()
        by_class=collections.defaultdict(collections.Counter)
        matrix=collections.Counter()
        details=[]
        wall=[]
        for record in records:
            result=record['result']
            causes[result['termination_category']]+=1
            wall.append(result['wall_s'])
            path=Path(record['output_dir'])/'choices.jsonl'
            sources.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            trace=[json.loads(line) for line in path.read_text().splitlines()]
            for step in trace:
                r=step['receipt']
                if r['tool'] in ('grasp','regrasp_restage'):
                    name=next((e['name'] for e in step['measurements'] if e['id']==r.get('object')), 'unknown')
                    by_class[name]['attempts']+=1
                    by_class[name]['verified']+=bool(r.get('grasp_verified'))
                    by_class[name]['execution_errors']+=bool(r.get('error'))
                evidence=step.get('predicate_verification_evidence') or {}
                truth=evidence.get('physical_placement_predicate')
                if r.get('place_verified') is not None and truth is not None:
                    predicted=bool(r['place_verified'])
                    matrix['tp' if predicted and truth else 'fp' if predicted else 'fn' if truth else 'tn']+=1
                    details.append({'episode':record['episode'],'decision':step['decision'],
                                    'predicted':predicted,'physical_predicate':truth,
                                    'measurements':step.get('verification_measurements'),
                                    'motion_evidence':step.get('motion_evidence')})
            sources.append({'path':str(Path(record['output_dir'])/'result.json'),
                            'sha256':hashlib.sha256((Path(record['output_dir'])/'result.json').read_bytes()).hexdigest()})
        tp,fp,fn=matrix['tp'],matrix['fp'],matrix['fn']
        precision=tp/(tp+fp) if tp+fp else None
        groups[condition]={'attempted':len(records),'planned':6,'complete':len(records)==6,
                           'correct_finish':sum(bool(r['result']['correct_finish']) for r in records),
                           'physical_success':sum(bool(r['result']['official_success']) for r in records),
                           'terminal_counts':dict(causes),'grasp_by_category':dict(by_class),
                           'wall_median_s':statistics.median(wall) if wall else None,
                           'placement_matrix':dict(matrix),'placement_precision':precision,
                           'placement_recall':tp/(tp+fn) if tp+fn else None,
                           'precision_target_observed':precision is not None and precision>=.95,
                           'placement_comparisons':details}
    report={'purpose':'original-only paired repair development; no retention/freeze decision from this small sample',
            'conditions':groups,'sources':sources,'complete':len(groups)==4 and all(g['complete'] for g in groups.values()),
            'retention_requires':'new init41 full40 official success nondecreasing and target failures reduced, then old init40 full40 regression',
            'precision_limit':'Report positive count and recall; six episodes do not establish general precision.'}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:{f:v for f,v in g.items() if f not in ('placement_comparisons','grasp_by_category')}
                      for k,g in groups.items()},indent=2))


if __name__=='__main__':main()
