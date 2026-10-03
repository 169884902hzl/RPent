"""Build skill-failure questions from explicit, already rendered post-action rows."""

import argparse
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import shared_v5r_schema as shared


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


CONDITIONAL_INSTRUCTION = (
    'A skill tool was called and returned a failed receipt. Classify that recorded '
    'failure as a runtime/input error or a failed physical/visual verification. '
    'This question does not judge episode termination or uncalled skills.'
)


def derive(parent, *, conditional=False):
    if parent.get('question_type') != 'action_outcome':
        return None
    receipt = parent['label_evidence']['executed_receipt']
    if receipt.get('verification') not in ('failed', 'execution_error'):
        return None
    cause = 'skill_execution_error' if receipt.get('error') else 'skill_execution_failure'
    choices = {
        'skill_execution_error': 'The skill raised a runtime or input error.',
        'skill_execution_failure': 'The skill failed physical or visual verification.',
        'perception_missing_object': 'No required object measurement is available.',
    }
    evidence = {'kind': 'programmatic_receipt_reason',
                'scope': 'skill_attempt_not_episode_termination',
                'executed_receipt': copy.deepcopy(receipt)}
    instruction = 'What failure is recorded for the most recent skill attempt?'
    if conditional:
        # A tool can return a failed receipt before completing the physical
        # skill. Preserve executed=false instead of claiming physical success.
        if receipt.get('tool') not in ('grasp', 'place', 'articulate', 'adjust_place',
                                       'regrasp_restage'):
            return None
        if cause == 'skill_execution_failure':
            measurements = ('gripper_opening', 'measured_z_rise_cm')
            if not (receipt.get('executed') is True
                    and receipt.get('verification') == 'failed'
                    and receipt.get('grasp_verified') is False
                    and all(isinstance(receipt.get(k), (int, float))
                            and not isinstance(receipt[k], bool)
                            and math.isfinite(receipt[k]) for k in measurements)):
                # Other failures need their own recorded measurement evidence;
                # a verification string alone cannot supply a measured judge.
                return None
            evidence['kind'] = 'measured_skill_verification'
            evidence['verification_evidence'] = {k: receipt[k] for k in
                                                ('grasp_verified', *measurements)}
        choices.pop('perception_missing_object')
        instruction = CONDITIONAL_INSTRUCTION
        evidence['scope'] = 'called_skill_with_failed_receipt/1'
        evidence['receipt_source'] = {
            k: parent.get('format_repair', {}).get(k) for k in
            ('runtime_source_file', 'runtime_source_line', 'source_request_sha256')}
    row = shared.auxiliary(parent, 'failure_reason', instruction, choices, {cause: 1.}, evidence)
    for name in ('suite', 'task_id', 'init_state_index', 'init_state_sha256',
                 'coordinate_quality', 'perception_measurement_evidence', 'memory_variant',
                 'format_repair', 'serializer_sha256', 'serialization_version'):
        if name in parent:
            row[name] = copy.deepcopy(parent[name])
    if shared.request_bytes(row['request']['state']) != shared.request_bytes(parent['request']['state']):
        raise ValueError('rendered state changed')
    return shared.render_example(row, seed=shared.digest(parent['request']), delete_probability=0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--choice-package', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--conditional-scope', action='store_true')
    args = parser.parse_args()
    if sha(args.manifest) != args.manifest_sha256:
        raise ValueError('registered rendered manifest changed')
    manifest = json.loads(args.manifest.read_text())
    sys.path.insert(0, str(args.choice_package))
    import parallel_schema
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.choice_package, local_files_only=True)
    args.output.mkdir(parents=True, exist_ok=False)
    destination = args.output / 'skill_failure_auxiliary.jsonl'
    counts, causes, suites, tasks, variants, judges = (Counter() for _ in range(6))
    seen, physical, tokens, inputs = {}, set(), [], []
    with destination.open('x') as output:
        for item in manifest['files']:
            if item['bucket'] not in ('train', 'unpaired_train'):
                continue
            path = Path(item['path'])
            if sha(path) != item['sha256']:
                raise ValueError('declared rendered input changed')
            inputs.append(item)
            n = 0
            with path.open() as source:
                for n, line in enumerate(source, 1):
                    parent = json.loads(line)
                    row = derive(parent, conditional=args.conditional_scope)
                    if row is None:
                        continue
                    counts['recorded_failed_skill_rows'] += 1
                    if (row.get('domain') != 'libero' or row.get('split') != 'train'
                            or not 10 <= row['seed'] <= 39
                            or not row.get('scene_id', '').startswith('original/')
                            or row['stage'] != 'receipt'):
                        raise ValueError('skill failure question is outside original training scope')
                    state = row['request']['state']
                    if 'sim_truth' in state or 'BDDL' in state or re.search(r'\b(?:obj|zone)_\w+', state):
                        raise ValueError('private geometry or internal ID entered public state')
                    try:
                        _, prepared = shared.prepare_example(row, tokenizer, parallel_schema, limit=3072)
                    except ValueError as error:
                        if 'token' not in str(error).lower() and '3072' not in str(error):
                            raise
                        counts['over_token_rejected'] += 1
                        continue
                    question = row['request']['questions']['action']
                    identity = shared.digest({'state': state, 'question': question['instructions'],
                                              'choices': sorted(question['criteria'].values())})
                    cause = row['option_names'][row['acceptable_actions'][0]]
                    if identity in seen:
                        if seen[identity] != cause:
                            raise ValueError('identical semantic request has conflicting failure labels')
                        counts['semantic_duplicates_removed'] += 1
                        continue
                    seen[identity] = cause
                    row['prompt_tokens'] = len(prepared.full_ids[0])
                    row['recorded_auxiliary_source'] = {'path': str(path), 'sha256': item['sha256'],
                                                         'line': n, 'request_sha256': shared.digest(parent['request'])}
                    row['derivation_scope'] = 'Existing measured post-action state and programmatic receipt classification; no new physical execution, not episode termination.'
                    output.write(json.dumps(row, ensure_ascii=False) + '\n')
                    causes[cause] += 1
                    suites[row['task_family']] += 1
                    tasks[f"{row['task_family']}/{row['task_id']}"] += 1
                    variants[row.get('memory_variant', 'none')] += 1
                    judges[row['judge']] += 1
                    origin = parent['format_repair']
                    physical.add((origin['runtime_source_file'], origin['runtime_source_line']))
                    tokens.append(row['prompt_tokens'])
                    counts['retained_questions'] += 1
            if n != item['rows']:
                raise ValueError('declared input row count differs')
    ordered = sorted(tokens)
    report = {
        'purpose': 'Provisional original-only skill-attempt failure auxiliaries; not appended to3088',
        'input_manifest': str(args.manifest), 'input_manifest_sha256': sha(args.manifest),
        'inputs': inputs, 'files': [{'path': str(destination.resolve()), 'sha256': sha(destination),
                                    'rows': counts['retained_questions'], 'bucket': 'auxiliary'}],
        'counts': dict(counts), 'failure_cause_counts': dict(causes), 'suite_counts': dict(suites),
        'task_counts': dict(tasks), 'memory_variant_counts': dict(variants),
        'existing_physical_skill_attempts': len(physical), 'new_physical_executions': 0,
        'new_independent_physical_states': 0, 'schema_version': 'entities-plan-receipt/3.1',
        'judge': 'mixed_by_receipt_evidence' if args.conditional_scope else 'program_termination',
        'judge_counts': dict(judges),
        'scope': ('called_skill_with_failed_receipt/1' if args.conditional_scope else
                  'skill_attempt_not_episode_termination'),
        'question_definition': ({
            'instructions': CONDITIONAL_INSTRUCTION,
            'option_names': ['skill_execution_error', 'skill_execution_failure'],
            'conditioning': 'Skill tool called and failed receipt returned; executed may be false.',
            'program_termination_evidence': 'Nonempty error in the original failed receipt.',
            'measured_predicate_evidence': 'Recorded grasp verification, opening and visual z rise.',
            'excluded_meanings': ['uncalled skill', 'episode termination',
                                  'missing object diagnosis', 'general root cause diagnosis'],
        } if args.conditional_scope else None),
        'token_p95': ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)] if ordered else None,
        'token_max': max(tokens) if tokens else None, 'prompt_limit': 3072, 'truncated_rows': 0,
        'script_sha256': sha(__file__), 'shared_schema_sha256': sha(shared.__file__),
        'exclusions': {'original_train_init_indices': list(range(10, 40)), 'validation_files_read': False,
                       'PRO_inputs_read': False, 'human102_or_sealed_inputs_read': False,
                       'Jev_labels_used': False},
        'full_training_admission': False,
        'remaining': 'Does not fabricate missing terminal categories or new physical recovery coverage; runtime/strict-verifier and development regressions remain pending.',
    }
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('counts', 'failure_cause_counts',
                                           'existing_physical_skill_attempts', 'token_p95', 'token_max')}))


if __name__ == '__main__':
    main()
