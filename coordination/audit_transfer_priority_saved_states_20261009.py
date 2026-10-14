"""Compare macro coverage on fixed measured states, without new physics."""

from collections import Counter
from dataclasses import fields
import hashlib
import json
from pathlib import Path
import re

from robots.libero.v5_public_transfer_reference import transfer_reference
from robots.libero.v5_state import Entity, Candidate
from robots.libero.v5_subtasks import subtask_candidates

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
INPUT=ROOT/'artifacts/spatial_runtime_candidate_coverage_20261009_r1/coverage.jsonl'
OUTPUT=ROOT/'artifacts/spatial_transfer_priority_saved_states_20261009_r1'


def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}


def main():
    OUTPUT.mkdir(exist_ok=False)
    records=[]; table=['|task/init|states|public pair resolved|transfer available before/after|','|---|---:|---:|---:|']
    names={f.name for f in fields(Entity)}
    for entry in [json.loads(x) for x in INPUT.read_text().splitlines()]:
        trace=Path(entry['input']['path'])
        counts=Counter(); states=[]
        for line in trace.read_text().splitlines():
            a=json.loads(line);context=a['request']['context']
            instruction=json.loads(next(s[len('instruction '):] for s in context.splitlines() if s.startswith('instruction ')))
            scene=[Entity(**{k:tuple(v) if k in ('xyz','lower','upper') else v
                    for k,v in r.items() if k in names}) for r in a['measurements']]
            m=re.search(r'right_world=(\[.*?\]) front_world=(\[.*?\])',context)
            axes=tuple(tuple(json.loads(s)) for s in m.groups()) if m else None
            robot=a['robot_measurement'];eef=robot['eef_xyz'];held=robot.get('held')
            before=subtask_candidates(scene,instruction,tuple(eef),held,view_axes=axes)
            after=subtask_candidates(scene,instruction,tuple(eef),held,view_axes=axes,instruction_transfer_binding_v1=True)
            reference=transfer_reference(scene,instruction,axes)
            expected=Candidate('vla_subtask',reference['source'],reference['target'],reference['mode']) if reference['source'] and reference['target'] else None
            counts['states']+=1
            if expected:
                counts['pair_resolved']+=1;counts['before_available']+=expected in before;counts['after_available']+=expected in after
            states.append({'decision':a['decision'],'public_reference':reference,
                'expected_candidate':expected.text() if expected else None,
                'before':[c.text() for c in before],'after':[c.text() for c in after],
                'selected':a['selected'],'held':held})
        result={'episode':entry['episode'],'counts':dict(counts),'states':states,'input':ref(trace)};records.append(result)
        e=entry['episode'];table.append(f"|{e['task']}/{e['seed']}|{counts['states']}|{counts['pair_resolved']}|{counts['before_available']}/{counts['after_available']}|")
    p=OUTPUT/'coverage.jsonl';p.write_text(''.join(json.dumps(x)+'\n' for x in records))
    (OUTPUT/'REPORT.md').write_text('\n'.join(table)+'\n\nCoverage on saved public measurements, not physical success.\n')
    manifest={'records':ref(p),'input':ref(INPUT),'script':ref(Path(__file__)),
        'public_modules':[ref(Path(__import__(name,fromlist=['']).__file__)) for name in
            ('robots.libero.v5_public_transfer_reference','robots.libero.v5_subtasks')],
        'new_physics_runs':0,'training_allowed':False}
    p=OUTPUT/'manifest.json';p.write_text(json.dumps(manifest,indent=2)+'\n')
    print('\n'.join(table));print(json.dumps({'manifest':ref(p)}))


if __name__=='__main__':main()
