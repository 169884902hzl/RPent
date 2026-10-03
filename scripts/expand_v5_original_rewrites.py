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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--wording-bank', type=Path, required=True)
    parser.add_argument('--choice-package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
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
    texts, base_states, unique_requests, lengths = set(), set(), set(), []
    inputs = {str(p): sha(p) for p in (args.manifest, args.wording_bank)}
    episodes = {}
    for desc in manifest['files']:
        if desc['bucket'] != 'train':
            continue
        original = Path(desc['path'])
        assert sha(original) == desc['sha256']
        inputs[str(original)] = desc['sha256']
        path = original.parent/'choices.jsonl'
        if path not in episodes:
            inputs[str(path)] = sha(path)
            episodes[path] = {row['decision']: row for row in map(json.loads, path.read_text().splitlines())}
    train = args.output/'train.jsonl'
    rejects = args.output/'rejections.jsonl'
    with train.open('x') as writer, rejects.open('x') as rejected:
        for desc in manifest['files']:
            if desc['bucket'] != 'train':
                continue
            original = Path(desc['path'])
            trace = episodes[original.parent/'choices.jsonl']
            for row in map(json.loads, original.read_text().splitlines()):
                assert row['domain'] == 'libero' and row['split'] == 'train' and 10 <= row['seed'] < 40
                assert row['suite'] in ('libero_spatial', 'libero_object', 'libero_goal', 'libero_10')
                assert row['question_type'] == 'next_skill' and row['judge'] == 'physics_branch'
                step = trace[row['step']]
                assert step['request']['context'] == row['request']['state']
                branches = row['label_evidence']['branches']
                before = copy.deepcopy(branches[0]['before'])
                key = f"{row['suite']}/{row['task_id']}"
                rewrites = bank['tasks'][key]['rewrites']
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
                base_states.add((row['scene_id'], row['step'], base_id))
                per_task[key]['physical_base_rows'] += 1
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
                                              'new_independent_physical_state': False, 'fresh_binding': policy.last_binding}
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
                    counts['admitted_action_rows'] += 1
                    writer.write(json.dumps(new, ensure_ascii=True)+'\n')
                writer.flush()
    report = {'purpose':'Original-task CPU rewrite expansion; provisional, not appended to3088 or declared final-format admission',
              'input_files': inputs, 'generator_sha256': sha(__file__), 'device':'CPU',
              'counts':dict(counts), 'by_task':{k:dict(v) for k,v in per_task.items()},
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
    (args.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('input_files','by_task')},indent=2))


if __name__ == '__main__':
    main()
