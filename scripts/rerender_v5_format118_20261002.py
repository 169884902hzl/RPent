# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Re-render an explicit package, preserving physics labels and exposing gaps."""

import argparse
import ast
import collections
import copy
import hashlib
import json
import random
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from robots.libero.v5_cards import card_view, resolve_card, advance_card
from robots.libero.v5_state import Candidate, Entity, candidates as live_candidates, serialize, upgrade_controls
from robots.libero.v5_termination import classify_v2
from robots.libero.v5_verification import strict_place_verified, measured_articulation
import shared_v5r_schema as shared


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records(descriptor):
    path = Path(descriptor["path"])
    if sha(path) != descriptor["sha256"]:
        raise ValueError(f"changed declared input: {path}")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != descriptor["rows"]:
        raise ValueError("declared row count differs")
    return rows


def entity(record):
    fields = Entity.__dataclass_fields__
    return Entity(**{k: tuple(v) if k in ("xyz", "lower", "upper") else v
                     for k,v in record.items() if k in fields})


def legacy_fixture_overrides(evaluated, entities, instruction):
    """Find old branches whose executed drawer differed from the candidate.

    The legacy executor substituted the first named drawer in the instruction
    even for a selected, specific drawer. Its physical result does not label
    that specific candidate under the corrected execution semantics.
    """
    match = re.search(r"\b(top|upper|middle|bottom|lower) drawer\b", instruction,
                      flags=re.IGNORECASE)
    if match is None:
        return set()
    normalize = {"upper": "top", "lower": "bottom"}
    actual = normalize.get(match[1].lower(), match[1].lower())
    names = {e.id: e.name for e in entities}
    overridden = set()
    for text in evaluated:
        action = Candidate.from_text(text)
        if action.tool != "articulate":
            continue
        selected = re.search(r"\b(top|upper|middle|bottom|lower) drawer\b",
                             names.get(action.object, ""), flags=re.IGNORECASE)
        if selected and normalize.get(selected[1].lower(), selected[1].lower()) != actual:
            overridden.add(text)
    return overridden


def robot_and_axes(context):
    line = next(line for line in context.splitlines() if line.startswith("robot "))
    match = re.fullmatch(r"robot gripper_opening=([\d.]+) held=(e\d+|none)", line)
    if match is None:
        raise ValueError("unrecognized measured robot line")
    axis = next((line for line in context.splitlines() if line.startswith("rel frame=")), None)
    axes = None
    if axis:
        parsed = re.search(r"right_world=(\[[^]]+\]) front_world=(\[[^]]+\])", axis)
        axes = tuple(tuple(ast.literal_eval(parsed[i])) for i in (1,2))
    return float(match[1]), None if match[2] == "none" else match[2], axes


def revised_receipt(record, counts, *, before=None, after=None):
    receipt = copy.deepcopy(record["receipt"])
    if receipt.get("tool") == "articulate" and before is not None and before.get("fixture_front_geometry_v1"):
        if receipt.get("error"):
            return receipt
        first=next((entity(e) for e in before["entities"] if e['id']==receipt.get('object')),None)
        second=next((entity(e) for e in (after or {}).get("entities",[]) if e['id']==receipt.get('object')),None)
        axis=before.get('fixture_front_axes',{}).get((first.part_of or first.id) if first else None)
        if first is None:
            verified,evidence=None,{'reason':'recorded_part_not_visible_in_rebuilt_geometry'}
        else:
            verified,evidence=measured_articulation(first,second,receipt.get('mode'),axis)
        receipt.update(articulate_verified=verified,verification='unverified' if verified is None else 'verified' if verified else 'failed',
                       verification_rule='measured_fixture_motion/2-dev',**evidence)
        counts['articulate_receipt_recomputed']+=1
        return receipt
    if receipt.get("tool") not in ("place", "adjust_place"):
        return receipt
    evidence = record.get("verification_measurements") or {}
    if not evidence or evidence.get("kind") != "placement":
        counts["place_receipt_missing_two_frame_evidence"] += 1
        if not receipt.get("error"):
            receipt.update(place_verified=None, verification="unverified",
                           verification_rule="strict_place/1-dev", measurement_gap="two_frame_evidence_missing")
        return receipt
    first = entity(evidence["first"]) if evidence["first"] else None
    second = entity(evidence["second"]) if evidence["second"] else None
    verified = strict_place_verified(first, second, entity(evidence["target"]), evidence["opening"],
                                     evidence["eef_xyz"], evidence["interval_s"], relation=evidence["relation"])
    receipt.update(place_verified=verified, verification="verified" if verified else "failed",
                   verification_rule="strict_place/1-dev")
    counts["place_receipt_recomputed"] += 1
    return receipt


def card_at(card, trace, index, revised_receipts):
    pointer = 0
    for receipt_index, record in enumerate(trace[:index]):
        view = card_view(card, pointer)
        if view is None:
            break
        entities = [entity(e) for e in record["measurements"]]
        _, held, _ = robot_and_axes(record["request"]["context"])
        resolved = resolve_card(view, entities, held)
        if advance_card(view, Candidate.from_text(record["selected"]), revised_receipts[receipt_index], resolved):
            pointer += 1
    return card_view(card, pointer)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--cards", type=Path, required=True)
    p.add_argument("--choice-package", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--measurements",type=Path)
    p.add_argument("--mask-legacy-fixture-overrides", action="store_true",
                   help="Mask labels from old instruction-overridden drawer branches; keep their raw evidence")
    a = p.parse_args()
    from transformers import AutoTokenizer
    sys.path.insert(0, str(a.choice_package))
    import parallel_schema
    tokenizer = AutoTokenizer.from_pretrained(a.choice_package, local_files_only=True)
    m = json.loads(a.manifest.read_text())
    registry_descriptor=m['original_target_registry']
    assert sha(registry_descriptor['path'])==registry_descriptor['sha256']
    registry=json.loads(Path(registry_descriptor['path']).read_text())
    assert sha(registry['source_episodes'])==registry['source_episodes_sha256']
    result_index={r['output']:r['result'] for r in json.loads(Path(registry['source_episodes']).read_text())}
    cm = json.loads(a.cards.read_text())
    if cm["origin"] != "original_oracle" or cm["RPent_cards_in_training"]:
        raise ValueError("training must not read RPent cards")
    cards = {}
    for descriptor in cm["files"]:
        if sha(descriptor["path"]) != descriptor["sha256"]:
            raise ValueError("card changed")
        cards[descriptor["task"]] = (json.loads(Path(descriptor["path"]).read_text()), descriptor)
    measurements = {}
    calibrated_front=False
    if a.measurements:
        mm=json.loads(a.measurements.read_text())
        calibrated_front=mm.get('fixture_front_geometry_v1',False)
        if mm['input_manifest_sha256'] != sha(a.manifest):
            raise ValueError('measurement ledger belongs to another source manifest')
        for descriptor in mm['files']:
            if sha(descriptor['path'])!=descriptor['sha256']:
                raise ValueError('measurement ledger changed')
            for line in Path(descriptor['path']).open():
                item=json.loads(line)
                measurements[(item['source_file'],item['source_line'],item['stage'])]=item
    sources = collections.defaultdict(list)
    for descriptor in m["source_files"]:
        for source in records(descriptor):
            sources[shared.digest(source["request"])].append(source)
    declared_logs = {item["path"]:item for item in m["runtime_logs"]}
    traces = {}
    a.output.mkdir(parents=True, exist_ok=False)
    handles = {name:(a.output/(name+'.jsonl')).open('x') for name in
               ('train','validation','unpaired_train','unpaired_validation','excluded','request_replay')}
    counts = collections.Counter()
    variants = collections.Counter()
    by_task = collections.defaultdict(collections.Counter)
    tokens = []
    longest = []
    for split, descriptors in (('train',m['files']),('validation',m['validation_files'])):
        for descriptor in descriptors:
            for line_no, old in enumerate(records(descriptor),1):
                counts['input_'+split] += 1
                if old['schema_version'] != 'entities-plan-receipt/3.1' or old['domain'] != 'libero':
                    raise ValueError('unexpected input contract')
                init=old['init_state_index']
                if (split=='train' and not 10<=init<40) or (split=='validation' and init not in range(5)):
                    raise ValueError('training/development/final isolation violation')
                candidates=[s for s in sources[old['base_request_sha256']]
                            if s['stage']==old['stage'] and s['step']==old['step']]
                candidates={ (s['source_file'],s['source_line']):s for s in candidates }
                if len(candidates)!=1:
                    counts['missing_or_ambiguous_runtime_source']+=1
                    handles['excluded'].write(json.dumps({'file':descriptor['path'],'line':line_no,'reason':'runtime_source_ambiguous_or_missing'})+'\n')
                    continue
                source=next(iter(candidates.values()))
                path=source['source_file']
                if path not in traces:
                    traces[path]=records(declared_logs[path])
                trace=traces[path]
                index=source['source_line']-1
                event=trace[index]
                post=old['stage']=='receipt'
                measured=event.get('post_measurements') if post else event['measurements']
                if measured is None and post and index+1<len(trace):
                    measured=trace[index+1]['measurements']
                if measured is None:
                    counts['missing_post_measurements']+=1
                    continue
                entities=[entity(e) for e in measured]
                rebuilt=measurements.get((path,source['source_line'],'receipt' if post else 'decision'))
                if rebuilt:
                    entities=[entity(e) for e in rebuilt['entities']]
                    counts['depth_rebuilt_rows']+=1
                    counts['depth_missing_parent_frames']+=len(rebuilt['missing'])
                opening,held,axes=robot_and_axes(source['request']['state'])
                instruction=json.loads(old['request']['state'].splitlines()[0].removeprefix('instruction '))
                receipts=[revised_receipt(r, counts,
                                         before=measurements.get((path,i+1,'decision')),
                                         after=measurements.get((path,i+1,'receipt')))
                          for i,r in enumerate(trace[:index+int(post)])]
                base=[Candidate.from_text(text) for text in event['candidates']]
                task=f"{old['suite']}/{old['task_id']}"
                goal_key=task + ('/cf_'+old['scene_id'].split('/cf_',1)[1] if '/cf_' in old['scene_id'] else '')
                correct=cards.get(goal_key)
                stale=next((v for k,v in cards.items() if correct and k!=goal_key and
                            v[1]['original_scene_sha256']==correct[1]['original_scene_sha256'] and
                            v[0]['steps']!=correct[0]['steps']),None)
                paired=correct is not None and stale is not None
                if not paired:
                    counts['missing_correct_or_same_scene_stale_card']+=1
                options=[('correct',correct),('stale',stale),('none',None)] if paired else [('unpaired_none',None)]
                if any(e.visible and e.name in ('cabinet','stove','microwave') and not e.part_of
                       and not any(part.part_of==e.id for part in entities) for e in entities):
                    counts['historical_fixture_point_cloud_not_rerendered']+=1
                rendered_rows = []
                rejected_variants = []
                for variant,selected_card in options:
                    view=card_at(selected_card[0],trace,index+int(post),receipts) if selected_card else None
                    rng=random.Random(int(hashlib.sha256((old['base_request_sha256']+variant).encode()).hexdigest()[:16],16))
                    eef=(rebuilt.get('robot_measurement') or {}).get('eef_xyz') if rebuilt else None
                    if eef is not None:
                        upgraded=live_candidates(entities,instruction,tuple(eef),held,receipts,rng,
                                                 card=view,adjust_place=True)
                    else:
                        upgraded=upgrade_controls(base,entities,held,receipts,card=view,adjust_place=True)
                    rng.shuffle(upgraded)
                    state=serialize(instruction,entities,opening,held,receipts,view,axes,
                                    choices=upgraded,failure_counts=True)
                    if re.search(r'\b(?:obj|zone)_[A-Za-z0-9_]+|sim_truth',state):
                        raise ValueError('internal identifier/provenance in model-visible state')
                    row=copy.deepcopy(old)
                    row['request']['state']=state
                    if old['question_type']=='next_skill':
                        old_options=old['request']['questions']['action']['criteria']
                        accepted={old_options[c] for c in old['acceptable_actions']}
                        evaluated={old_options[c] for c in old['evaluated_actions']}
                        new_options={f'C{i}':c.text() for i,c in enumerate(upgraded)}
                        row['request']['questions']['action']['criteria']=new_options
                        accepted = set(accepted)
                        evaluated = set(evaluated)
                        if a.mask_legacy_fixture_overrides:
                            overridden = legacy_fixture_overrides(evaluated, entities, instruction)
                            counts['legacy_fixture_positive_labels_masked'] += len(overridden & accepted)
                            counts['legacy_fixture_negative_labels_masked'] += len(overridden - accepted)
                            if overridden:
                                row['legacy_fixture_target_masks'] = {
                                    'actions': sorted(overridden),
                                    'previously_acceptable': sorted(overridden & accepted),
                                    'reason': 'legacy executor performed the instruction drawer instead of the selected part',
                                    'effective_label': 'unknown',
                                }
                                accepted -= overridden
                                evaluated -= overridden
                        resolved = resolve_card(view, entities, held) if view else None
                        equivalences = []
                        if resolved is not None and resolved.text() in evaluated:
                            evaluated.add('card_next()')
                            if resolved.text() in accepted:
                                accepted.add('card_next()')
                            equivalences.append({'candidate':'card_next()',
                                                 'resolved_candidate':resolved.text(),
                                                 'acceptable':resolved.text() in accepted,
                                                 'basis':'unique measured category binding to the identical evaluated skill',
                                                 'source_base_request_sha256':old['base_request_sha256'],
                                                 'original_label_evidence':old['label_evidence']})
                        row['acceptable_actions']=[c for c,text in new_options.items() if text in accepted]
                        row['evaluated_actions']=[c for c,text in new_options.items() if text in evaluated]
                        row['unknown_actions']=[c for c in new_options if c not in row['evaluated_actions']]
                        row['label_equivalences']=equivalences
                        if not row['acceptable_actions']:
                            counts['excluded_lost_acceptable_action']+=1
                            rejected_variants.append({'variant':variant, 'reason':'lost_acceptable_action',
                                                      'original_accepted_skills':sorted(accepted),
                                                      'rendered_candidates':new_options})
                            continue
                    elif old['question_type']=='action_outcome' and post:
                        recent=receipts[-1]
                        label='failed' if recent.get('verification') in ('failed','execution_error') else 'verified' if recent.get('verification')=='verified' else 'unverified'
                        row['target']={code:float(name==label) for code,name in row['option_names'].items()}
                        row['acceptable_actions']=[code for code,value in row['target'].items() if value]
                        row['label_evidence']={'kind':'evaluated_physical_branch','executed_receipt':recent,
                                               'original_evidence':old['label_evidence']}
                    elif old['question_type']=='failure_reason':
                        from harness_v5_eval import TERMINATION_CATEGORIES
                        result=result_index.get(str(Path(path).parent))
                        last=Candidate.from_text(trace[-1]['selected'])
                        classified=classify_v2(result,SimpleNamespace(tool=last.tool),[r['receipt'] for r in trace]) if result else None
                        label=classified[0] if classified else result['termination_category'] if result else old['label_evidence']['termination_category']
                        if result is None:counts['termination_label_without_declared_result']+=1
                        criteria={f'C{i}':name.replace('_',' ') for i,name in enumerate(TERMINATION_CATEGORIES)}
                        row['request']['questions']['action']['criteria']=criteria
                        row['option_names']={f'C{i}':name for i,name in enumerate(TERMINATION_CATEGORIES)}
                        row['target']={code:float(name==label) for code,name in row['option_names'].items()}
                        row['acceptable_actions']=[code for code,value in row['target'].items() if value]
                        row['evaluated_actions']=list(criteria)
                        row['unknown_actions']=[]
                        row['label_evidence']={'kind':'programmatic_receipt_reason','termination_category':label,
                                               'episode_index_sha256':registry['source_episodes_sha256'],
                                               'reclassification_applied':bool(result),'original_evidence':old['label_evidence']}
                    row.update(serialization_version='316753ea+libero_format131/1-dev' if calibrated_front else '316753ea+libero_format128/1-dev',
                               serializer_sha256=sha(Path(__file__).resolve().parents[1]/'robots/libero/v5_state.py'),
                               renderer_sha256=sha(__file__),
                               memory_variant=variant, format_repair={'source_request_sha256':shared.digest(old['request']),
                               'runtime_source_file':path,'runtime_source_line':source['source_line'],
                               'new_candidates_not_executed':'unknown unless uniquely equivalent to an evaluated physical skill',
                               'old_physics_labels':'replay only; not a new physical branch',
                               'furniture_gap':'historical per-instance point clouds unavailable; no parts invented',
                               'card_sha256':selected_card[1]['sha256'] if selected_card else None})
                    if rebuilt:
                        row['format_repair'].update(measurement_evidence=rebuilt['evidence'],
                                                    measurement_gaps=rebuilt['missing'],
                                                    candidate_generator='same live_candidates from recorded measurements/proprioception',
                                                    proprioception_source=rebuilt['robot_source'])
                        row['format_repair']['furniture_gap']=rebuilt['missing']
                    base_request=copy.deepcopy(source['request'])
                    base_request['state']=state
                    base_request['questions']['action']['criteria']={f'C{i}':c.text() for i,c in enumerate(upgraded)}
                    row['base_request_sha256']=shared.digest(base_request)
                    row['source_key']={'request_hash':shared.digest(row['request']),'scene':row['scene_id'],'stage':row['stage'],'step':row['step']}
                    try:
                        _,prepared=shared.prepare_example(row,tokenizer,parallel_schema,limit=3072)
                    except ValueError as error:
                        if 'token' not in str(error).lower() and '3072' not in str(error):
                            raise
                        counts['over_token_rejected']+=1
                        rejected_variants.append({'variant':variant, 'reason':'over_token', 'error':str(error)})
                        continue
                    row['prompt_tokens']=len(prepared.full_ids[0])
                    assert row['prompt_tokens']<=3072
                    rendered_rows.append(row)
                if rejected_variants:
                    exclusion = {'file':descriptor['path'],'line':line_no,'split':split,
                                 'scene_id':old['scene_id'],'stage':old['stage'],'step':old['step'],
                                 'question_type':old['question_type'],
                                 'reason':'incomplete_card_triplet' if paired else 'unpaired_variant_rejected',
                                 'rejected_variants':rejected_variants,
                                 'withheld_variants':[r['memory_variant'] for r in rendered_rows],
                                 'withheld_request_hashes':[r['source_key']['request_hash'] for r in rendered_rows]}
                    handles['excluded'].write(json.dumps(exclusion,ensure_ascii=False)+'\n')
                    counts['excluded_incomplete_card_triplets' if paired else 'excluded_unpaired_rows']+=1
                    counts['excluded_incomplete_card_triplet_rows']+=len(rendered_rows) if paired else 0
                    continue
                if paired:
                    assert {r['memory_variant'] for r in rendered_rows} == {'correct','stale','none'}
                    assert len(rendered_rows) == 3
                    counts['retained_complete_card_triplets']+=1
                output=split if paired else 'unpaired_'+split
                for row in rendered_rows:
                    variant=row['memory_variant']
                    handles[output].write(json.dumps(row,ensure_ascii=False)+'\n')
                    counts['card_next_evaluated_equivalence']+=bool(row.get('label_equivalences'))
                    variants[split+'/'+variant]+=1
                    by_task[task][split+'/'+variant]+=1
                    tokens.append(row['prompt_tokens'])
                    longest.append((row['prompt_tokens'],row['source_key']['request_hash'],row['request']))
                    if len(longest)>256:
                        longest=sorted(longest,key=lambda x:x[0],reverse=True)[:128]
                    handles['request_replay'].write(json.dumps({'request':row['request'],'source_key':row['source_key'],
                                                              'evidence_kind':'reconstructed_request_only',
                                                              'format_renderer_sha256':sha(__file__)})+'\n')
    for handle in handles.values():handle.close()
    lengths=sorted(longest,key=lambda x:x[0],reverse=True)[:128]
    (a.output/'longest128.jsonl').write_text(''.join(json.dumps({'prompt_tokens':n,'request_hash':h,'request':r})+'\n' for n,h,r in lengths))
    output_files=[]
    for name,handle in handles.items():
        path=Path(handle.name)
        output_files.append({'bucket':name,'path':str(path.resolve()),'sha256':sha(path),'rows':sum(1 for _ in path.open())})
    report={'purpose':'versioned full input rerender with explicit unpaired/card/measurement gaps; NOT training admission',
            'input_manifest':str(a.manifest),'input_manifest_sha256':sha(a.manifest),
            'card_manifest_sha256':sha(a.cards),'files':output_files,'counts':dict(counts),'memory_variants':dict(variants),
            'card_variant_metadata_field':'memory_variant',
            'paired_variant_policy':'retain correct/stale/none atomically per input row; record rejected and withheld variants',
            'equivalence_count_scope':'actual retained rows only',
            'mask_legacy_fixture_overrides':a.mask_legacy_fixture_overrides,
            'measurement_manifest_sha256':sha(a.measurements) if a.measurements else None,
            'by_task':dict(by_task),'token_p95':float(np.percentile(tokens,95)) if tokens else None,
            'token_max':max(tokens) if tokens else None,'over2048':sum(n>2048 for n in tokens),
            'longest128':{'path':str((a.output/'longest128.jsonl').resolve()),'sha256':sha(a.output/'longest128.jsonl')},
            'schema_version':'entities-plan-receipt/3.1','hard_limit':3072,'truncation':False,
            'new_candidates_evaluated_by_equivalence':counts['card_next_evaluated_equivalence'],
            'new_candidates_physically_executed':0,'RPent_cards_in_training':False,'PRO_inputs_used':False,
            'source_hashes':{name:sha(Path(__file__).resolve().parents[1]/name) for name in
                            ['robots/libero/v5_state.py','robots/libero/v5_cards.py','robots/libero/v5_verification.py']},
            'full_training_admission':False,'live_runtime_field_parity_verified':False,
            'remaining':'Furniture depth reconstruction, complete card coverage, runtime replay and original precision/recall required; unexecuted controls unknown.'}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('by_task','files','source_hashes')},indent=2))


if __name__=='__main__':main()
