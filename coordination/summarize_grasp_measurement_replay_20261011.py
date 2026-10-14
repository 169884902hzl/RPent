"""Pair development measurement replays with immutable closed rows."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from coordination.classify_grasp_contact_phases_20261010 import diagnose

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
RUN=ROOT/'results/harness_v5/grasp_measurement_development_20261011_r4'
OUT=ROOT/'coordination/grasp_measurement_development_closed_20261011_r1'


def pin(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def summarize():
    registrations=json.loads((RUN/'startup_manifest.json').read_text())
    pairs,inputs,pan=[],[],[]
    for registered in registrations:
        plan_path=Path(registered['plan']['path'])
        plan=json.loads(plan_path.read_text())
        formal=json.loads((plan_path.parent/'formal_measurement_submission.json').read_text())
        paths=[RUN/plan_path.parent.parent.name/f'job{registered["startup_job"]}/part0/probe/episodes.jsonl']
        paths += [plan_path.parent.parent/f'job{formal["formal_job"]}/part{i}/probe/episodes.jsonl'
                  for i in range(formal['shards'])]
        rawrows={}
        for path in paths:
            inputs.append(pin(path))
            for line,raw in enumerate(map(json.loads,path.read_text().splitlines()),1):
                name=raw['case']['name']
                if name in rawrows:raise ValueError('duplicate development physical record')
                rawrows[name]=(raw,path,line)
        if set(rawrows)!={c['name'] for c in plan['cases']}:
            raise ValueError('incomplete registered measurement states')
        for case in plan['cases']:
            raw,path,line=rawrows[case['name']]
            old=case['diagnostic_closed_case']
            first=raw.get('first_attempt') or {}
            phase=raw.get('private_grasp_phase') or {}
            physical=first.get('physically_executed',False)
            item={'case':case['name'],'category':old['group'],
                  'method':'analytic' if 'analytic' in case['condition'] or 'frypan' in case['condition'] else 'pi05',
                  'state_sha256':case['state_sha256'],
                  'physical_outcome':'success' if old['registered_v3'] is True else 'failure' if old['registered_v3'] is False else 'unknown'}
            diagnosis=diagnose(raw,item)
            full_samples=phase.get('samples') or []
            indices=[s.get('control_index') for s in full_samples]
            indices_complete=(indices==list(range(len(full_samples)))
                              and phase.get('control_steps_sampled')==len(full_samples))
            complete=(not physical or (phase.get('trace_version')=='every-executed-skill-control/1-dev'
                         and bool(full_samples) and indices_complete and all('action' in s and 'scene_contacts' in s and
                         'tcp_xyz' in s and 'control_index' in s for s in full_samples)))
            newlabel=(first.get('private_hold_truth_v3') or
                      (first.get('private_setup_hold') or {}).get('truth_v3') or {})
            newtruth=newlabel.get('success')
            newchecks=newlabel.get('checks') or []
            row={'case':case['name'],'category':old['group'],'layout_seed':case['layout_seed'],
                 'state_sha256':case['state_sha256'],'closed_case':old['case'],
                 'old':{'input':old['input'],'line':old['line'],'v3':old['registered_v3'],
                        'failure_stage':old['private_contact_failure_class']},
                 'new':{'input':pin(path),'line':line,'v3_diagnostic_only':newtruth,
                        'public':(first.get('receipt') or {}).get('grasp_verified'),
                        'status':raw['status'],'failure_stage':diagnosis['contact_failure_class'],
                        'physical_controls_sampled':len(full_samples),'complete_control_trace':complete,
                        'control_indices_contiguous':indices_complete,
                        'physically_executed':physical,
                        'reference_support':phase.get('reference',{}).get('original_support_plane_evidence'),
                        'truth_unknown_reasons':sorted({c['unknown_reason'] for c in newchecks if c.get('unknown_reason')})},
                 'contact_diagnosis':diagnosis,'closed_verdict_not_recomputed':True,'training_allowed':False}
            pairs.append(row)
            if old['group']=='frypan' and old['registered_v3'] is None:pan.append(row)
    OUT.mkdir(parents=True,exist_ok=False)
    path=OUT/'paired_rows.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in pairs))
    report={'registered_states':len(pairs),'paired_rows':pin(path),'inputs':inputs,
            'producer':pin(Path(__file__)), 'complete_control_trace':sum(r['new']['complete_control_trace'] for r in pairs),
            'whole_skill_trace_not_saved':sum(r['new']['failure_stage']=='whole_skill_trace_not_saved' for r in pairs),
            'no_physical_attempt':sum(not r['new']['physically_executed'] for r in pairs),
            'per_category':{g:{'n':sum(r['category']==g for r in pairs),
                'failure_stages':dict(Counter(r['new']['failure_stage'] for r in pairs if r['category']==g))}
                for g in ('bottle','bowl','box','cup','frypan')},
            'old_pan16':{'n':len(pan),'new_truth_unknown':sum(r['new']['v3_diagnostic_only'] is None for r in pan),
                        'unknown_reasons':dict(Counter(reason for r in pan for reason in r['new']['truth_unknown_reasons']))},
            'confirmation_score_changed':False,'training_allowed':False,
            'qualification_claim':False}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='inputs'},indent=2))


if __name__=='__main__':summarize()
