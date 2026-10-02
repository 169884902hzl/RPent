# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Generate requests from original recorded inputs, without reading training rows."""

import argparse
import collections
import functools
import hashlib
import json
import random
from pathlib import Path

from robots.libero.v5_collection import wire_request
from robots.libero.v5_state import candidates, prepare_request, serialize, upgrade_controls, Candidate
from scripts.rerender_v5_format118_20261002 import entity, robot_and_axes, revised_receipt, card_at
import shared_v5r_schema as shared


@functools.lru_cache(maxsize=None)
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(item):
    assert sha(item['path']) == item['sha256'], 'declared input changed'
    rows = [json.loads(line) for line in Path(item['path']).read_text().splitlines()]
    if 'rows' in item:
        assert len(rows) == item['rows']
    return rows


def main():
    p = argparse.ArgumentParser()
    for name in ('manifest', 'measurements', 'cards', 'choice-package', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    from transformers import AutoTokenizer
    import sys
    sys.path.insert(0, str(a.choice_package))
    import parallel_schema
    tokenizer = AutoTokenizer.from_pretrained(a.choice_package, local_files_only=True)
    m = json.loads(a.manifest.read_text())
    registry_item = m['original_target_registry']
    assert sha(registry_item['path']) == registry_item['sha256']
    registry = json.loads(Path(registry_item['path']).read_text())
    assert sha(registry['source_episodes']) == registry['source_episodes_sha256']
    registered_episodes = {item['output']: item for item in json.loads(Path(registry['source_episodes']).read_text())}
    configs = {str(Path(item['runtime_config_path']).parent): item for item in registry['episodes']}
    mm = json.loads(a.measurements.read_text())
    assert mm['input_manifest_sha256'] == sha(a.manifest)
    measurements = {}
    for item in mm['files']:
        for record in read_jsonl(item):
            measurements[(record['source_file'], record['source_line'], record['stage'])] = record
    cm = json.loads(a.cards.read_text())
    assert cm['origin'] == 'original_oracle' and cm['RPent_cards_in_training'] is False
    cards = {}
    for item in cm['files']:
        assert sha(item['path']) == item['sha256']
        cards[item['task']] = (json.loads(Path(item['path']).read_text()), item)
    traces = {}
    for item in m['runtime_logs']:
        traces[item['path']] = read_jsonl(item)
    a.output.mkdir(parents=True, exist_ok=False)
    destination = a.output/'runtime_requests.jsonl'
    counts = collections.Counter()
    inputs = []
    with destination.open('x') as output:
        for descriptor in m['source_files']:
            inputs.append(descriptor)
            for source in read_jsonl(descriptor):
                if source['stage'] != 'skill':
                    continue
                path = source['source_file']
                epdir = str(Path(path).parent)
                registered = configs.get(epdir)
                episode = registered_episodes.get(epdir)
                if registered is None or episode is None:
                    counts['missing_registered_runtime_config'] += 1
                    continue
                cfg_path = registered['runtime_config_path']
                assert sha(cfg_path) == registered['runtime_config_sha256']
                cfg = json.loads(Path(cfg_path).read_text())
                if cfg.get('libero_type') != 'standard':
                    raise ValueError('only original LIBERO recorded inputs are allowed')
                trace = traces[path]
                index = source['source_line']-1
                event = trace[index]
                rebuilt = measurements.get((path, source['source_line'], 'decision'))
                if rebuilt is None:
                    counts['missing_measurement_ledger'] += 1
                    continue
                measured = [entity(item) for item in rebuilt['entities']]
                # Original raw log supplies only its historical robot/axes summary.
                # No entity lines, options, state, or labels from the new package are read.
                opening, held, axes = robot_and_axes(event['request']['context'])
                instruction = cfg.get('instruction_override')
                if instruction is None:
                    counts['missing_registered_instruction'] += 1
                    continue
                assert hashlib.sha256(instruction.encode()).hexdigest() == registered['instruction_sha256']
                receipts = [revised_receipt(row,counts,
                                            before=measurements.get((path,i+1,'decision')),
                                            after=measurements.get((path,i+1,'receipt')))
                            for i,row in enumerate(trace[:index])]
                scene = f"original/{cfg['suite']}/t{cfg['task']}/init{cfg['seed']}"
                goal_key = f"{cfg['suite']}/{cfg['task']}"
                if registered.get('counterfactual_spec'):
                    spec_path = Path(registered['counterfactual_spec'])
                    spec = json.loads(spec_path.read_text())
                    suffix = spec['variant_bddl_sha256'][:12]
                    scene += '/cf_'+suffix
                    goal_key += '/cf_'+suffix
                identity = episode['identity']
                for item in identity[3:]:
                    if isinstance(item, str) and item.startswith('replay:'):
                        scene += '/replay_'+item.removeprefix('replay:')
                correct = cards.get(goal_key)
                stale = next((value for key,value in cards.items() if correct and key != goal_key
                              and value[1]['original_scene_sha256'] == correct[1]['original_scene_sha256']
                              and value[0]['steps'] != correct[0]['steps']), None)
                paired = correct is not None and stale is not None
                variants = [('correct',correct),('stale',stale),('none',None)] if paired else [('unpaired_none',None)]
                base_digest = shared.digest(source['request'])
                base = [Candidate.from_text(text) for text in event['candidates']]
                for variant, selected_card in variants:
                    view = card_at(selected_card[0],trace,index,receipts) if selected_card else None
                    rng = random.Random(int(hashlib.sha256((base_digest+variant).encode()).hexdigest()[:16],16))
                    eef = (rebuilt.get('robot_measurement') or {}).get('eef_xyz')
                    options = (candidates(measured,instruction,tuple(eef),held,receipts,rng,card=view,adjust_place=True)
                               if eef is not None else upgrade_controls(base,measured,held,receipts,card=view,adjust_place=True))
                    rng.shuffle(options)
                    state = serialize(instruction,measured,opening,held,receipts,view,axes,
                                      choices=options,failure_counts=True)
                    try:
                        request, tokens = prepare_request(tokenizer,parallel_schema.prepare_prompts,state,options)
                    except ValueError as error:
                        if 'token' not in str(error).lower() and '3072' not in str(error):
                            raise
                        counts['over_token_rejected'] += 1
                        continue
                    wire = wire_request(request)
                    row = {'request':wire,'scene_id':scene,'stage':'skill','step':source['step'],
                           'suite':cfg['suite'],'task_id':cfg['task'],
                           'init_state_sha256':cfg['init_state_sha256'],'memory_variant':variant,
                           'source_key':{'request_hash':shared.digest(wire),'scene':scene,'stage':'skill','step':source['step']},
                           'prompt_tokens':tokens,'evidence_kind':'independent_original_measurement_reconstruction',
                           'evidence_scope':'recorded RGB-D/entities + registered original config + original robot/axes summary; no new training requests or labels read',
                           'runtime_input':{'trace':path,'trace_sha256':source['source_file_sha256'],
                                            'line':source['source_line'],'config':cfg_path,'config_sha256':sha(cfg_path),
                                            'measurement_manifest_sha256':sha(a.measurements)},
                           'physical_runtime_sha256':episode['result']['source_hashes'].get('robots/libero/v5_runtime.py'),
                           'request_generator_sha256':sha(__file__)}
                    output.write(json.dumps(row,ensure_ascii=False)+'\n')
                    counts['requests'] += 1
                    counts['variant_'+variant] += 1
    report = {'runtime_request_files':[{'path':str(destination.resolve()),'sha256':sha(destination),'rows':counts['requests']}],
              'input_manifest_sha256':sha(a.manifest),'measurement_manifest_sha256':sha(a.measurements),
              'card_manifest_sha256':sha(a.cards),'counts':dict(counts),'inputs':inputs,
              'source_hashes':{name:sha(Path(__file__).resolve().parents[1]/name) for name in
                              ['robots/libero/v5_state.py','robots/libero/v5_cards.py','robots/libero/v5_verification.py']},
              'script_sha256':sha(__file__),'PRO_inputs_used':False,'new_training_files_read':False,
              'scope':'Independent recorded-input reconstruction through live candidate/serializer functions; not a new physical runtime evaluation',
              'live_runtime_field_parity_verified':False}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'counts':dict(counts),'manifest_sha256':sha(a.output/'manifest.json')}))


if __name__ == '__main__':
    main()
