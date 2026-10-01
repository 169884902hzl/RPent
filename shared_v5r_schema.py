"""Shared MuJoCo/LIBERO auxiliary schema; preserve the frozen public state."""
from copy import deepcopy
import hashlib
import json
import math
import random

STATE_SERIALIZER_SHA = '316753ea7c0a4bc8701d4fc5b5117662dc037523af28111fc440896f480418f6'
SERIALIZATION_VERSION = '316753ea+aux_questions_v1'
QUESTION_TYPES = ('next_skill', 'goal_done', 'subgoal_done', 'action_outcome', 'progress', 'failure_reason')
JUDGE_SOURCES = ('measured_predicate', 'physics_branch', 'plan_oracle', 'program_termination')
RETENTION_JUDGE = 'dataset_annotation'
# Fractions of task rows; general retention is counted separately.
AUXILIARY_CAPS = {'goal_done': .10, 'subgoal_done': .10, 'action_outcome': .10,
                  'progress': .10, 'failure_reason': .10}


def request_bytes(request):
    return json.dumps(request, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def digest(request):
    return hashlib.sha256(request_bytes(request)).hexdigest()


def next_skill(row):
    result = deepcopy(row)
    evidence = row.get('label_evidence') or {}
    measured_branches = any((b.get('result') or {}).get('status') is not None
                            and b.get('evaluation') is not None for b in evidence.get('branches', []))
    judge = ('physics_branch' if evidence.get('physical_branch_checked') or evidence.get('physical_branch_verified') or measured_branches
             else 'plan_oracle')
    if row.get('domain') == 'general':
        if 'answer' not in evidence:
            raise ValueError('retention_row_missing_dataset_annotation')
        judge = RETENTION_JUDGE
    result.update(question_type='next_skill', judge=judge, serialization_version=SERIALIZATION_VERSION)
    if request_bytes(result['request']) != request_bytes(row['request']):
        raise ValueError('next_skill_request_changed')
    result['base_request_sha256'] = digest(row['request'])
    return result


def auxiliary(row, question_type, instruction, choices, target, evidence):
    """Add one question branch. Oracle/evaluator labels never enter the state."""
    if question_type not in AUXILIARY_CAPS:
        raise ValueError('unknown_auxiliary_judge')
    if not 2 <= len(choices) <= 26:
        raise ValueError('invalid_auxiliary_option_count')
    codes = [f'C{i}' for i in range(len(choices))]
    probabilities = [float(target.get(name, 0)) for name in choices]
    if any(not math.isfinite(v) or v < 0 for v in probabilities) or sum(probabilities) <= 0:
        raise ValueError('invalid_soft_target')
    probabilities = [v / sum(probabilities) for v in probabilities]
    request = {'state': row['request']['state'], 'questions': {'action': {
        'type': 'choice', 'instructions': instruction,
        'criteria': dict(zip(codes, choices.values()))}}}
    if request['state'].encode() != row['request']['state'].encode():
        raise ValueError('auxiliary_state_changed')
    key = {'request_hash': digest(row['request']),
        'scene': row.get('scene_id', row.get('episode_id')), 'stage': row['stage'], 'step': row['step']}
    kind = evidence['kind']
    judge = ('physics_branch' if kind in ('executed_finish_branch', 'evaluated_physical_branch') else
             'program_termination' if kind in ('executed_done_gate', 'programmatic_receipt_reason') else
             'measured_predicate')
    if row.get('domain') not in ('mujoco', 'libero'):
        raise ValueError('auxiliary_source_domain_required')
    return {k: deepcopy(row[k]) for k in ('seed', 'scene_id', 'episode_id', 'task_family', 'stage', 'step', 'domain') if k in row} | {
        'bucket': 'auxiliary', 'source_bucket': row.get('bucket'),
        'schema_version': 'entities-plan-receipt/3.1', 'serialization_version': SERIALIZATION_VERSION,
        'split': row.get('split', 'train'), 'question_type': question_type, 'judge': judge, 'request': request,
        'target': dict(zip(codes, probabilities)), 'option_names': dict(zip(codes, choices)),
        'acceptable_actions': [c for c, v in zip(codes, probabilities) if v == max(probabilities)],
        'evaluated_actions': codes, 'unknown_actions': [],
        'base_request_sha256': digest(row['request']), 'source_key': key,
        'origin_source_key': deepcopy(row.get('source_key')),
        'label_evidence': evidence, 'source': deepcopy(row.get('v5_source', row.get('source')))}


def render_example(row, seed=None, delete_probability=.5):
    """One renderer for training and serving. Unaugmented requests stay exact.

    Permutation and deletion touch the question/options only. Keep every
    acceptable option; labels and soft target weights follow their option.
    """
    result = deepcopy(row)
    retention = (result.get('domain') == 'general' and result.get('judge') == RETENTION_JUDGE
                 and 'answer' in result.get('label_evidence', {}))
    if result.get('question_type', 'next_skill') not in QUESTION_TYPES or not (result['judge'] in JUDGE_SOURCES or retention):
        raise ValueError('invalid_question_type_or_judge')
    if seed is None:
        return result
    rng = random.Random(seed)
    question = row['request']['questions']['action']
    old_codes = list(question['criteria'])
    good = set(row['acceptable_actions'])
    order = list(old_codes)
    if rng.random() < delete_probability and len(order) > max(2, len(good)):
        removable = [c for c in order if c not in good]
        # For soft labels a nonzero target is never removed.
        removable = [c for c in removable if not row.get('target', {}).get(c, 0)]
        cap = min(len(removable), len(order) - max(2, len(good)))
        if cap:
            removed = set(rng.sample(removable, rng.randint(1, cap)))
            order = [c for c in order if c not in removed]
    rng.shuffle(order)
    mapping = {old: f'C{i}' for i, old in enumerate(order)}
    result['request']['questions']['action']['criteria'] = {mapping[c]: question['criteria'][c] for c in order}
    for field in ('acceptable_actions', 'evaluated_actions', 'unknown_actions'):
        result[field] = [mapping[c] for c in row.get(field, []) if c in mapping]
    if 'target' in row:
        result['target'] = {mapping[c]: row['target'].get(c, 0) for c in order}
    if 'option_names' in row:
        result['option_names'] = {mapping[c]: row['option_names'][c] for c in order}
    if 'candidates' in row:
        by_code = dict(zip(old_codes, row['candidates']))
        result['candidates'] = [deepcopy(by_code[c]) for c in order]
    if 'candidate_mapping' in row:
        result['candidate_mapping'] = {mapping[c]: row['candidate_mapping'][c] for c in order}
    for field in ('finish_code', 'complete_code'):
        if row.get(field):
            result[field] = mapping.get(row[field])
    if row.get('subgoal_removed_codes'):
        result['subgoal_removed_codes'] = [mapping[c] for c in row['subgoal_removed_codes'] if c in mapping]
    result['augmentation'] = {'seed': str(seed), 'old_to_new': mapping,
                              'removed': [c for c in old_codes if c not in mapping]}
    return result


def prepare_example(row, tokenizer, prompt_module, limit=3072, seed=None):
    rendered = render_example(row, seed=seed)
    q = rendered['request']['questions']['action']
    schema = {'action': {'type': 'enum', 'description': q['instructions'],
                        'choices': list(q['criteria']), 'choice_descriptions': q['criteria']}}
    prepared = prompt_module.prepare_prompts(tokenizer, rendered['request']['state'], schema, limit)
    return rendered, prepared
