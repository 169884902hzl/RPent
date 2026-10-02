# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Index an explicit rerender and its separate recorded-input runtime evidence."""

import argparse
import collections
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import shared_v5r_schema as shared


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(item):
    assert sha(item['path']) == item['sha256']
    n = 0
    with Path(item['path']).open() as handle:
        for line in handle:
            n += 1
            yield json.loads(line)
    assert n == item['rows']


def main():
    p = argparse.ArgumentParser()
    for name in ('rendered-manifest','runtime-manifest','source-manifest','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    rendered = json.loads(a.rendered_manifest.read_text())
    runtime = json.loads(a.runtime_manifest.read_text())
    source = json.loads(a.source_manifest.read_text())
    assert rendered['input_manifest_sha256'] == runtime['input_manifest_sha256'] == sha(a.source_manifest)
    assert rendered['source_hashes'] == runtime['source_hashes']
    a.output.mkdir(parents=True,exist_ok=False)
    coverage, statistics = {}, {}
    contracts, task_rows = set(), {}
    source_ids = collections.defaultdict(set)
    inits = collections.defaultdict(set)
    for descriptor in rendered['files']:
        bucket = descriptor['bucket']
        if bucket not in ('train','validation','unpaired_train','unpaired_validation'):
            continue
        counts = collections.Counter()
        questions = collections.Counter()
        family = collections.Counter()
        variants = collections.Counter()
        finish = collections.Counter()
        tokens, features = [], collections.defaultdict(list)
        for row in rows(descriptor):
            state = row['request']['state']
            assert row['schema_version'] == 'entities-plan-receipt/3.1'
            assert row['prompt_tokens'] <= 3072
            assert 'sim_truth' not in state
            import re
            assert re.search(r'\b(?:obj|zone)_[A-Za-z0-9_]+',state) is None
            split = 'train' if 'train' in bucket else 'validation'
            assert (10 <= row['init_state_index'] < 40) if split == 'train' else (row['init_state_index'] in range(5))
            request_hash = shared.digest(row['request'])
            assert request_hash == row['source_key']['request_hash']
            source_id = (row['format_repair']['runtime_source_file'],row['format_repair']['runtime_source_line'],row['stage'])
            source_ids[bucket].add(source_id)
            inits[split].add((row['suite'],row['task_id'],row['init_state_sha256']))
            counts['rows'] += 1
            questions[row['question_type']] += 1
            family[row['suite']+'/'+str(row['task_id'])] += 1
            variants[row['memory_variant']] += 1
            tokens.append(row['prompt_tokens'])
            criteria = row['request']['questions']['action']['criteria']
            predicates = {'furniture_parts':' part_of=' in state,
                          'candidate_failure_counts':'recent_failures=' in state,
                          'card_line':any(line.startswith('card ') for line in state.splitlines()),
                          'adjust_place':any(text.startswith('adjust_place(') for text in criteria.values()),
                          'card_next':'card_next()' in criteria.values()}
            for name,present in predicates.items():
                if present:features[name].append(request_hash)
            if row['question_type'] == 'next_skill':
                for code,text in criteria.items():
                    if text == 'finish()':
                        finish['positive' if code in row['acceptable_actions'] else
                               'negative' if code in row['evaluated_actions'] else 'unknown'] += 1
                if bucket == 'train':
                    k=(row['suite'],row['task_id'],row['init_state_sha256'],request_hash,
                       row['scene_id'],row['stage'],row['step'])
                    task_rows[k] = row
            contracts.add((row['serialization_version'],row['serializer_sha256']))
        coverage[bucket] = {'features':dict(features),'memory_variants':dict(variants),
                            'source_state_keys':len(source_ids[bucket]),'rows':counts['rows']}
        statistics[bucket] = {'rows':counts['rows'],'by_question':dict(questions),'by_task':dict(family),
                              'memory_variants':dict(variants),'finish_labels':dict(finish),
                              'token_p95':float(np.percentile(tokens,95)) if tokens else None,
                              'token_max':max(tokens) if tokens else None,
                              'over2048':sum(n>2048 for n in tokens),
                              'feature_counts':{k:len(v) for k,v in features.items()},
                              'unique_source_stage_keys':len(source_ids[bucket])}
    assert not inits['train'] & inits['validation']
    runtime_index={}
    for descriptor in runtime['runtime_request_files']:
        for row in rows(descriptor):
            assert row['evidence_kind'] == 'independent_original_measurement_reconstruction'
            runtime_index[(shared.digest(row['request']),row['scene_id'],row['stage'],row['step'])]=row
    selected=random.Random(20261002).sample(sorted(task_rows,key=str),min(200,len(task_rows)))
    checks=[]
    for key in selected:
        row=task_rows[key]
        actual=runtime_index.get((shared.digest(row['request']),row['scene_id'],row['stage'],row['step']))
        match=actual is not None and shared.request_bytes(actual['request'])==shared.request_bytes(row['request'])
        checks.append({'source_key':row['source_key'],'matched_bytes':match,
                       'runtime_evidence_kind':actual['evidence_kind'] if actual else None})
    contract={'sampled':len(checks),'matched':sum(x['matched_bytes'] for x in checks),
              'selection_seed':20261002,'records':checks,
              'scope':'Producer byte comparison only; frozen token/letter contract checker and independent review still required',
              'is_independent_admission':False,'new_physical_run':False}
    (a.output/'request_bytes200.json').write_text(json.dumps(contract,indent=2)+'\n')
    feature_path=a.output/'coverage.json'
    feature_path.write_text(json.dumps({'source_manifest_sha256':sha(a.rendered_manifest),
                                      'memory_variant_metadata_field':'memory_variant','buckets':coverage,
                                      'statistics':statistics},indent=2)+'\n')
    descriptors={item['bucket']:item for item in rendered['files']}
    report={'purpose':'Explicit source delivery for independent review, not training admission',
            'training_files':[descriptors['train']],'validation_files':[descriptors['validation']],
            'runtime_request_files':runtime['runtime_request_files'],
            'source_files':[], 'unpaired_files':[descriptors[k] for k in ('unpaired_train','unpaired_validation')],
            'schema_version':'entities-plan-receipt/3.1','serializer_sha256':shared.STATE_SERIALIZER_SHA,
            'libero_state_serializer_sha256':rendered['source_hashes']['robots/libero/v5_state.py'],
            'libero_serialization_version':next(iter(contracts))[0] if len(contracts)==1 else None,
            'libero_state_contracts':[{'serialization_version':v,'state_serializer_sha256':h} for v,h in sorted(contracts)],
            'rendered_manifest':str(a.rendered_manifest),'rendered_manifest_sha256':sha(a.rendered_manifest),
            'runtime_manifest':str(a.runtime_manifest),'runtime_manifest_sha256':sha(a.runtime_manifest),
            'original_source_manifest':str(a.source_manifest),'original_source_manifest_sha256':sha(a.source_manifest),
            'statistics':statistics,'coverage':{'path':str(feature_path.resolve()),'sha256':sha(feature_path)},
            'longest128':rendered['longest128'],'train_validation_init_overlap':0,
            'runtime_contract200':{'path':str((a.output/'request_bytes200.json').resolve()),'sha256':sha(a.output/'request_bytes200.json')},
            'PRO_inputs_used':False,'RPent_cards_in_training':False,'training_started':False,
            'full_training_admission':False,'may_train':False,'producer_script_sha256':sha(__file__),
            'remaining':rendered['remaining']}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'manifest_sha256':sha(a.output/'manifest.json'),'statistics':statistics,
                      'bytes200_matched':contract['matched'],'bytes200_sampled':contract['sampled']}))


if __name__ == '__main__':
    main()
