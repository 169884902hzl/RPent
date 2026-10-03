# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Bind registered original-task rewrites to existing physical branch labels."""

from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace

from robots.libero.v5_oracle_policy import OriginalOraclePolicy
from robots.libero.v5_state import Candidate, Entity
import shared_v5r_schema as shared


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def registered_rewrites(row, bank, trace_path, inputs):
    """Use the physical trajectory's goal variant rather than original wording."""
    task = f"{row['suite']}/{row['task_id']}"
    if '/cf_' not in row['scene_id']:
        return task, bank['tasks'][task]['rewrites']
    config_path = trace_path.parent / 'config.json'
    config = json.loads(config_path.read_text())
    spec_path = Path(config['counterfactual_spec'])
    digest = sha(spec_path)
    if digest != row['counterfactual_spec_sha256']:
        raise ValueError('registered counterfactual specification changed')
    spec = json.loads(spec_path.read_text())
    suffix = row['scene_id'].split('/cf_', 1)[1].split('/', 1)[0]
    if suffix != spec['variant_bddl_sha256'][:12]:
        raise ValueError('counterfactual scene and wording goal differ')
    inputs[str(config_path)] = sha(config_path)
    inputs[str(spec_path)] = digest
    return task + '/cf_' + suffix, spec['rewrites']


def complete_memory_triplets(rows):
    """Reject all paired variants when any rewrite loses a valid binding."""
    grouped = collections.defaultdict(list)
    for row in rows:
        evidence = row['rewrite_evidence']
        group = (row['scene_id'], row['step'], evidence['physical_origin_request_sha256'],
                 row['instruction_sha256'])
        grouped[group].append(row)
    retained, withheld = [], []
    for group in grouped.values():
        variants = {row['memory_variant'] for row in group}
        if variants == {'unpaired_none'} or variants == {'correct', 'stale', 'none'}:
            retained.extend(group)
        else:
            withheld.extend(group)
    return retained, withheld


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--wording-bank', type=Path, required=True)
    parser.add_argument('--choice-package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rendered-prefix', action='store_true',
                        help='Expand recorded prefix rows after recovery/card rerender, without rebuilt geometry')
    args = parser.parse_args()
    from transformers import AutoTokenizer
    sys.path.insert(0, str(args.choice_package))
    import parallel_schema
    tokenizer = AutoTokenizer.from_pretrained(args.choice_package, local_files_only=True)
    manifest = json.loads(args.manifest.read_text())
    bank = json.loads(args.wording_bank.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    counts = collections.Counter()
    per_task = collections.defaultdict(collections.Counter)
    per_goal = collections.defaultdict(collections.Counter)
    texts, base_states, unique_requests, lengths = set(), set(), set(), []
    inputs = {str(p): sha(p) for p in (args.manifest, args.wording_bank)}
    episodes = {}
    allowed_buckets = ('train', 'unpaired_train') if args.rendered_prefix else ('train',)
    selected_files = [d for d in manifest['files'] if d['bucket'] in allowed_buckets]
    for desc in selected_files:
        original = Path(desc['path'])
        assert sha(original) == desc['sha256']
        inputs[str(original)] = desc['sha256']
        for row in map(json.loads, original.read_text().splitlines()):
            if row['question_type'] != 'next_skill':
                continue
            path = Path(row['format_repair']['runtime_source_file']) if args.rendered_prefix else original.parent/'choices.jsonl'
            if args.rendered_prefix and row['format_repair'].get('measurement_evidence') is not None:
                raise ValueError('rebuilt geometry needs its explicit measurement ledger; this mode uses recorded prefix geometry')
            if path not in episodes:
                inputs[str(path)] = sha(path)
                episodes[path] = {event['decision']: event for event in map(json.loads, path.read_text().splitlines())}
    train = args.output/'train.jsonl'
    rejects = args.output/'rejections.jsonl'
    with train.open('x') as writer, rejects.open('x') as rejected:
        for desc in selected_files:
            original = Path(desc['path'])
            for row in map(json.loads, original.read_text().splitlines()):
                if row['question_type'] != 'next_skill':
                    continue
                assert row['domain'] == 'libero' and row['split'] == 'train' and 10 <= row['seed'] < 40
                assert row['suite'] in ('libero_spatial', 'libero_object', 'libero_goal', 'libero_10')
                assert row['question_type'] == 'next_skill' and row['judge'] == 'physics_branch'
                trace_path = Path(row['format_repair']['runtime_source_file']) if args.rendered_prefix else original.parent/'choices.jsonl'
                step = episodes[trace_path][row['step']]
                if not args.rendered_prefix:
                    assert step['request']['context'] == row['request']['state']
                branches = row['label_evidence']['branches']
                before = copy.deepcopy(branches[0]['before'])
                key = f"{row['suite']}/{row['task_id']}"
                goal_key, rewrites = registered_rewrites(row, bank, trace_path, inputs)
                assert len(rewrites) >= 30 and len(set(rewrites)) == len(rewrites)
                entities = [Entity(**{k: e[k] for k in Entity.__dataclass_fields__ if k in e}) for e in step['measurements']]
                assert all(e.get('src') == 'perception' for e in step['measurements'])
                state = row['request']['state']
                robot = re.search(r'robot gripper_opening=([0-9.]+) held=(\S+)', state)
                held = None if robot[2] == 'none' else robot[2]
                receipts = [json.loads(line.removeprefix('receipt ')) for line in state.splitlines() if line.startswith('receipt ')]
                axes_match = re.search(r'right_world=(\[.*?\]) front_world=(\[.*?\])', state)
                axes = (tuple(json.loads(axes_match[1])), tuple(json.loads(axes_match[2]))) if axes_match else ((1, 0, 0), (0, 1, 0))
                criteria = row['request']['questions']['action']['criteria']
                codes = list(criteria)
                choices = [Candidate.from_text(criteria[c]) for c in codes]
                base_id = shared.digest(row['request'])
                physical_id = row['format_repair']['source_request_sha256'] if args.rendered_prefix else base_id
                base_states.add((row['scene_id'], row['step'], physical_id))
                per_task[key]['rendered_base_variant_rows'] += 1
                per_goal[goal_key]['rendered_base_variant_rows'] += 1
                for index, instruction in enumerate(rewrites):
                    counts['attempted'] += 1
                    rpc = SimpleNamespace(call=lambda *a, **kw: copy.deepcopy(before))
                    policy = OriginalOraclePolicy(rpc)
                    reason = None
                    try:
                        action = policy.choose(entities, choices, held, receipts, instruction, axes,
                                               native_success=before.get('official_solved', False))
                        selected = codes[choices.index(action)]
                        if selected not in row['acceptable_actions']:
                            reason = 'rewrite_not_bound_to_a_physically_acceptable_choice'
                    except (ValueError, StopIteration, IndexError) as error:
                        reason = 'unresolved_rewrite_binding:' + type(error).__name__
                    if reason is not None:
                        counts[reason] += 1
                        rejected.write(json.dumps({'base_request_sha256': base_id, 'instruction': instruction,
                                                   'reason': reason, 'binding': policy.last_binding})+'\n')
                        continue
                    new = copy.deepcopy(row)
                    first, rest = state.split('\n', 1)
                    assert first.startswith('instruction ')
                    new['request']['state'] = 'instruction '+json.dumps(instruction, ensure_ascii=True)+'\n'+rest
                    new['instruction_sha256'] = hashlib.sha256(instruction.encode()).hexdigest()
                    new['wording_bank_sha256'] = inputs[str(args.wording_bank)]
                    new['rewrite_evidence'] = {'base_request_sha256': base_id, 'physical_source_file': str(original),
                                              'physical_source_sha256': desc['sha256'], 'physical_labels_reused': True,
                                              'new_independent_physical_state': False, 'fresh_binding': policy.last_binding,
                                              'raw_physical_trace': str(trace_path), 'raw_physical_trace_sha256': inputs[str(trace_path)],
                                              'physical_origin_request_sha256': physical_id,
                                              'registered_goal_key': goal_key,
                                              'label_scope': 'retained tested skills plus recorded card equivalences; new recovery skills remain unknown'}
                    new = shared.render_example(new, seed=910000+counts['attempted'], delete_probability=0)
                    try:
                        new, prepared = shared.prepare_example(new, tokenizer, parallel_schema, limit=3072)
                    except ValueError as error:
                        if 'token' not in str(error).lower() and '3072' not in str(error):
                            raise
                        counts['over_token_rejected'] += 1
                        continue
                    new['prompt_tokens'] = len(prepared.full_ids[0])
                    assert new['prompt_tokens'] <= 3072
                    request_hash = shared.digest(new['request'])
                    if request_hash in unique_requests:
                        counts['duplicate_request_rejected'] += 1
                        continue
                    unique_requests.add(request_hash)
                    new['source_key'] = {**new['source_key'], 'request_hash': request_hash}
                    new['base_request_sha256'] = request_hash
                    texts.add(instruction)
                    lengths.append(new['prompt_tokens'])
                    per_task[key]['rewrite_rows'] += 1
                    per_goal[goal_key]['rewrite_rows'] += 1
                    counts['admitted_action_rows'] += 1
                    writer.write(json.dumps(new, ensure_ascii=True)+'\n')
                writer.flush()
    if args.rendered_prefix:
        expanded = [json.loads(line) for line in train.read_text().splitlines()]
        retained, withheld = complete_memory_triplets(expanded)
        counts['incomplete_memory_triplet_rows_withheld'] = len(withheld)
        counts['admitted_action_rows'] = len(retained)
        train.write_text(''.join(json.dumps(row, ensure_ascii=True) + '\n' for row in retained))
        with rejects.open('a') as rejected:
            for row in withheld:
                rejected.write(json.dumps({'base_request_sha256':row['rewrite_evidence']['base_request_sha256'],
                    'instruction_sha256':row['instruction_sha256'], 'memory_variant':row['memory_variant'],
                    'reason':'paired_memory_rewrite_missing_variant'}) + '\n')
        lengths = [row['prompt_tokens'] for row in retained]
        texts = {json.loads(row['request']['state'].splitlines()[0].removeprefix('instruction ')) for row in retained}
        unique_requests = {shared.digest(row['request']) for row in retained}
        base_states = {(row['scene_id'], row['step'], row['rewrite_evidence']['physical_origin_request_sha256']) for row in retained}
        for counter in [*per_task.values(), *per_goal.values()]:
            counter['rewrite_rows'] = 0
        for row in retained:
            per_task[f"{row['suite']}/{row['task_id']}"]['rewrite_rows'] += 1
            per_goal[row['rewrite_evidence']['registered_goal_key']]['rewrite_rows'] += 1
        task_states, goal_states = collections.defaultdict(set), collections.defaultdict(set)
        for row in retained:
            physical = (row['scene_id'], row['step'],
                        row['rewrite_evidence']['physical_origin_request_sha256'])
            task_states[f"{row['suite']}/{row['task_id']}"].add(physical)
            goal_states[row['rewrite_evidence']['registered_goal_key']].add(physical)
        for key, states in task_states.items():
            per_task[key]['retained_unique_physical_base_states'] = len(states)
        for key, states in goal_states.items():
            per_goal[key]['retained_unique_physical_base_states'] = len(states)
    report = {'purpose':'Original-task CPU rewrite expansion; provisional, not appended to3088 or declared final-format admission',
              'input_files': inputs, 'generator_sha256': sha(__file__), 'device':'CPU',
              'counts':dict(counts), 'by_task':{k:dict(v) for k,v in per_task.items()},
              'by_goal':{k:dict(v) for k,v in per_goal.items()},
              'unique_instruction_texts':len(texts), 'unique_physical_base_rows':len(base_states),
              'unique_action_requests':len(unique_requests), 'new_independent_physical_states':0,
              'rewrites_are_not_new_independent_states':True,
              'schema_version':'entities-plan-receipt/3.1', 'hard_prompt_limit':3072, 'truncated_rows':0,
              'prompt_p95':sorted(lengths)[math.ceil(.95*len(lengths))-1] if lengths else None,
              'prompt_max':max(lengths) if lengths else None,
              'files':[{'path':str(train), 'sha256':sha(train), 'rows':len(lengths)}],
              'exclusions':{'training_init_indices':list(range(10,40)), 'PRO_inputs_used':False,
                            'human102_or_sealed_inputs_read':False, 'Jev_training_labels_used':False},
              'rejections':{'path':str(rejects),'sha256':sha(rejects)},
              'source_behavior_and_format_preserved_from_base_rows':True}
    report['rendered_prefix'] = args.rendered_prefix
    (args.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('input_files','by_task')},indent=2))


if __name__ == '__main__':
    main()
