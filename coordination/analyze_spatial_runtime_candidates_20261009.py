"""Audit candidate coverage and selections using saved public measurements."""

from collections import Counter
from dataclasses import fields
import hashlib
import json
from pathlib import Path
import re

from robots.libero.v5_oracle_policy import OriginalOraclePolicy
from robots.libero.v5_state import Entity, Candidate

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
INPUT = ROOT / 'artifacts/A3_regressions_and_spatial_binding_20261009_r1/episode_diagnoses.jsonl'
OUTPUT = ROOT / 'artifacts/spatial_runtime_candidate_coverage_20261009_r1'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    OUTPUT.mkdir(exist_ok=False)
    output, table = [], ['|task/init|success|source unbound|bound source grasp omitted|bound transfer omitted|wrong source selections|',
                         '|---|---|---|---|---|---|']
    field_names = {f.name for f in fields(Entity)}
    for row in [json.loads(x) for x in INPUT.read_text().splitlines()]:
        if row['episode']['suite'] != 'libero_spatial_task':
            continue
        trace = Path(row['current']['choices']['path'])
        records, counts = [], Counter()
        for line in trace.read_text().splitlines():
            a = json.loads(line)
            ctx = a['request']['context']
            instruction = json.loads(next(x.removeprefix('instruction ') for x in ctx.splitlines() if x.startswith('instruction ')))
            entities = [Entity(**{k:tuple(v) if k in ('xyz','lower','upper') else v
                        for k,v in r.items() if k in field_names}) for r in a['measurements']]
            axis = re.search(r'right_world=(\[.*?\]) front_world=(\[.*?\])', ctx)
            axes = tuple(tuple(json.loads(x)) for x in axis.groups()) if axis else ((1,0,0),(0,-1,0))
            # Independent public-reference diagnostic only. This policy is not
            # called by the model runtime. No private predicates are read here.
            binder = OriginalOraclePolicy(None)
            source = binder.bind('akita_black_bowl', entities, instruction, axes)
            target = binder.bind('plate', entities, '', axes, source_reference=False)
            candidates = [Candidate.from_text(x) for x in a['candidates']]
            selected = Candidate.from_text(a['selected'])
            if source is None:
                counts['source_unbound'] += 1
            else:
                if not any(c.tool=='grasp' and c.object==source.id for c in candidates):
                    counts['source_grasp_omitted'] += 1
                if target and not any(c.tool=='vla_subtask' and c.object==source.id and c.target==target.id and c.mode=='on' for c in candidates):
                    counts['source_target_macro_omitted'] += 1
                if selected.tool in ('grasp','regrasp_restage','place','adjust_place','vla_subtask') and selected.object!=source.id:
                    counts['different_source_selected'] += 1
            record = {'decision':a['decision'], 'instruction':instruction,
                'public_reference_source':source.id if source else None,
                'public_reference_target':target.id if target else None,
                'public_reference_status':'unique' if source else 'unresolved',
                'selected':a['selected'], 'candidates':a['candidates'],
                'measurements':a['measurements'], 'receipt':a['receipt']}
            records.append(record)
        result = {'episode':row['episode'], 'success':row['current_success'], 'counts':dict(counts),
                  'records':records, 'input':ref(trace),
                  'label_source':'independent public-language binding, not private task truth'}
        output.append(result)
        e=row['episode']
        table.append(f"|{e['task']}/{e['seed']}|{int(row['current_success'])}|{counts['source_unbound']}|"
                     f"{counts['source_grasp_omitted']}|{counts['source_target_macro_omitted']}|{counts['different_source_selected']}|")
    ledger=OUTPUT/'coverage.jsonl'
    ledger.write_text(''.join(json.dumps(x)+'\n' for x in output))
    (OUTPUT/'REPORT.md').write_text('\n'.join(table)+'\n\nUnresolved public references cannot identify the intended simulator instance.\n')
    manifest={'records':ref(ledger),'input':ref(INPUT),'script':ref(Path(__file__)),
        'new_physics_runs':0,'training_allowed':False,'private_goal_reads':0}
    path=OUTPUT/'manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    print('\n'.join(table));print(json.dumps({'manifest':ref(path)}))


if __name__=='__main__':
    main()
