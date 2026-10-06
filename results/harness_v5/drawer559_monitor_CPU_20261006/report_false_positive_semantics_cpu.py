"""Compare nine saved4254 false positives with original installed predicate semantics."""

import ast
import hashlib
import json
from pathlib import Path
import re


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = Path(__file__).resolve().parent / 'final_20261006T164608.567363Z'
report = json.loads((OUT / 'statistic/report.json').read_text())
envs = ROOT / '.venv/lib/python3.10/site-packages/liberopro/liberopro/envs'
objects = envs / 'objects/articulated_objects.py'
predicates = envs / 'predicates/base_predicates.py'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def ordinal(text):
    found = re.search(r'(?:^|[ _])(top|middle|bottom)(?:[ _]|$)', text)
    return found.group(1) if found else None


tree = ast.parse(objects.read_text())
semantics = {}
for name in ('WoodenCabinet', 'WhiteCabinet'):
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    init = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    ranges = {}
    for node in ast.walk(init):
        if isinstance(node, ast.Assign):
            target = ast.unparse(node.targets[0])
            for key in ('default_open_ranges', 'default_close_ranges'):
                if key in target:
                    ranges[key] = ast.literal_eval(node.value)
    assert set(ranges) == {'default_open_ranges', 'default_close_ranges'}
    methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    assert isinstance(methods['is_open'].body[0].test.ops[0], ast.Lt)
    assert isinstance(methods['is_close'].body[0].test.ops[0], ast.Gt)
    semantics[name] = {**ranges, 'open_qpos_strictly_less_than_m': max(ranges['default_open_ranges']),
                       'close_qpos_strictly_greater_than_m': min(ranges['default_close_ranges']),
                       'class_line': cls.lineno, 'source_excerpt': ast.get_source_segment(objects.read_text(), cls)}
records = []
for ledger in report['original_explicit_inputs']:
    if ledger['role'] != 'ledger' or not ledger.get('exists'):
        continue
    snapshot = Path(ledger['snapshot'])
    for line_number, line in enumerate(snapshot.read_text().splitlines(), 1):
        row = json.loads(line)
        case, first = row['case'], row['first_attempt']
        receipt = first['receipt']
        after = first.get('private_after') or {}
        if receipt.get('articulate_verified') is not True or after.get('satisfied') is not False:
            continue
        symbol = case['object_symbol']
        category = 'WoodenCabinet' if symbol.startswith('wooden_cabinet_') else 'WhiteCabinet'
        assert symbol.startswith(('wooden_cabinet_', 'white_cabinet_'))
        semantics_case = semantics[category]
        qpos = after['joint_qpos'][0][0]
        mode = case['mode']
        derived_score = qpos < semantics_case['open_qpos_strictly_less_than_m'] if mode == 'open' else qpos > semantics_case['close_qpos_strictly_greater_than_m']
        assert derived_score is after['satisfied']
        selected = receipt['object']
        public_entities = {}
        for phase in ('before', 'after'):
            public_entities[phase] = next((entity for entity in first['public_' + phase]['entities']
                                           if entity['id'] == selected), None)
        metrology = first['verification_measurements']['articulation']
        distance = metrology['measured_extension_cm'] / 100
        expected_joint = symbol.replace('_region', '_level')
        matching = {'official_goal_symbol_matches_private_predicate': after['predicate'] == [mode, symbol],
                    'official_ordinal_matches_recorded_joint': after['joint_names'] == [expected_joint],
                    'public_selected_ordinal_matches_official_symbol': all(
                        entity is not None and ordinal(entity['name']) == ordinal(symbol)
                        for entity in public_entities.values()),
                    'public_selected_name_matches_case_category': all(
                        entity is not None and entity['name'] == case['object_category']
                        for entity in public_entities.values()),
                    'metrology_tracks_selected_entity': all(
                        metrology[phase].get('current_part') == selected for phase in ('before', 'after'))}
        item = {'case': case['name'], 'episode': case['episode'], 'mode': mode,
                'original_goal_symbol': symbol, 'private_predicate': after['predicate'],
                'private_before_joint_qpos': (first.get('private_before') or {}).get('joint_qpos'),
                'private_after_joint_qpos': after['joint_qpos'], 'private_joint_names': after['joint_names'],
                'private_satisfied_preserved': after['satisfied'], 'public_verdict_preserved': True,
                'original_object_class': category, 'original_predicate_semantics': semantics_case,
                'public_selected_id': selected, 'public_selected_entities': public_entities,
                'public_parent_entities': {phase: next((entity for entity in first['public_' + phase]['entities']
                    if entity['id'] == (public_entities[phase] or {}).get('part_of')), None) for phase in ('before', 'after')},
                'symbol_ordinal_and_identity_checks': matching, 'public_measured_extension_cm': distance * 100,
                'scoring_only_negated_private_qpos_extension_cm': -qpos * 100,
                'public_extension_minus_scoring_extension_mm': (distance + qpos) * 1000,
                'scoring_endpoint_gap_mm': (qpos - semantics_case['open_qpos_strictly_less_than_m']) * 1000
                    if mode == 'open' else (semantics_case['close_qpos_strictly_greater_than_m'] - qpos) * 1000,
                'evidence_interpretation': 'Public ordinal, selected entity and recorded joint match; measured movement is short of original open endpoint'
                    if mode == 'open' else 'Public ordinal and recorded bottom joint match; original close endpoint is missed by2.032mm and measured extension differs by0.532mm',
                'original_ledger': ledger['path'], 'captured_ledger': {**ref(snapshot), 'line': line_number},
                'choices': {'path': str(Path(row['output_dir']) / 'choices.jsonl'), 'sha256': row['choices_sha256']},
                'original_BDDL_reference': case['bddl'],
                'private_values_used_for_control_or_public_repair': False}
        records.append(item)
assert len(records) == 9
output = {'scope': 'Only nine preserved4254 false positives, original installed predicate source and saved scoring qpos; no PRO task file, physics or relabeling',
          'original_predicate_source': ref(predicates), 'original_object_semantics_source': ref(objects),
          'original_predicate_dispatch': {'open': 'Open.__call__ -> arg.is_open()', 'close': 'Close.__call__ -> arg.is_close()'},
          'semantics': semantics, 'records': records,
          'all_public_ordinal_identity_checks_match': all(all(row['symbol_ordinal_and_identity_checks'].values()) for row in records),
          'limits': 'Matching public names/ordinals and displacement support the target identity; this is saved evidence, not a geometric proof of segmentation correctness',
          'public_verdicts_or_thresholds_changed': False, 'private_qpos_use': 'Scoring diagnosis only, never runtime input or replacement public label',
          'new_physics': 0, 'new_model_calls': 0, 'new_training_rows': 0, 'producer': ref(Path(__file__).resolve())}
path = OUT / 'false_positive_semantics_report.json'
path.write_text(json.dumps(output, indent=2) + '\n')
table = OUT / 'false_positive_semantics.tsv'
table.write_text('case\tmode\toriginal_goal_symbol\tprivate_qpos_m\tpublic_extension_cm\tendpoint_gap_mm\tpublic_minus_qpos_extension_mm\tordinal_identity_matches\n' + ''.join(
    f"{row['case']}\t{row['mode']}\t{row['original_goal_symbol']}\t{row['private_after_joint_qpos'][0][0]:.9f}\t{row['public_measured_extension_cm']:.2f}\t{row['scoring_endpoint_gap_mm']:.3f}\t{row['public_extension_minus_scoring_extension_mm']:.3f}\t{all(row['symbol_ordinal_and_identity_checks'].values())}\n"
    for row in records))
print(json.dumps({'report': ref(path), 'table': ref(table), 'all_ordinal_identity_checks_match': output['all_public_ordinal_identity_checks_match'],
                  'rows': [{key: row[key] for key in ('case', 'original_goal_symbol', 'private_after_joint_qpos',
                           'public_measured_extension_cm', 'scoring_endpoint_gap_mm', 'public_extension_minus_scoring_extension_mm')}
                           for row in records]}))
