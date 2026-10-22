"""Compare the joint intervention without conflating a grasp with a placed goal."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
from statistics import median


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def wilson(k,n):
    if not n:return None
    z=1.959963984540054;d=1+z*z/n
    c=(k/n+z*z/(2*n))/d;h=z*math.sqrt(k*(n-k)/n**3+z*z/(4*n*n))/d
    return [c-h,c+h]


def paired(rows,key):
    known=[r for r in rows if type(r['baseline'][key]) is bool and type(r['combination'][key]) is bool]
    good=[r['case'] for r in known if not r['baseline'][key] and r['combination'][key]]
    bad=[r['case'] for r in known if r['baseline'][key] and not r['combination'][key]]
    discordant=len(good)+len(bad)
    p=min(1.,2*sum(math.comb(discordant,k) for k in range(min(len(good),len(bad))+1))/2**discordant) if discordant else 1.
    return {'paired_known':len(known),'unknown':len(rows)-len(known),'improvements':len(good),
        'regressions':len(bad),'improved_cases_with_repeats':good,'regressed_cases_with_repeats':bad,
        'exact_mcnemar_p_descriptive_repeats_not_independent':p,
        **{arm:{'success':sum(r[arm][key] for r in known),'n':len(known),
            'wilson95_over_repeats':wilson(sum(r[arm][key] for r in known),len(known))}
            for arm in ('baseline','combination')}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    plan=json.loads(args.manifest.read_bytes());rows=[];by_case=defaultdict(list)
    for index,job in enumerate(plan['jobs']):
        pointer=json.loads((args.results/f'closed_{index:03d}.json').read_bytes())
        summary=Path(pointer['summary']);assert ref(summary)['sha256']==pointer['sha256']
        result=json.loads(summary.read_bytes());assert result['source_commit']==plan['source_commit']
        assert result['all_complete_initial_hashes_match'] and not result['training']
        assert result['case']==job['case'] and len(result['trials'])==6
        trials={(t['arm'],t['repeat']):t for t in result['trials']};assert len(trials)==6
        for repeat in range(3):
            arms={arm:trials[(arm,repeat)] for arm in ('baseline','combination')}
            assert all(t['complete_initial_sha256']==result['initial_physics_sha256'] for t in arms.values())
            assert arms['baseline']['trial_seed']==arms['combination']['trial_seed']
            row={'case':result['case']['name'],'mode':result['subtask']['mode'],
                'suite':result['case']['episode']['suite'],'repeat':repeat,
                'initial_physics_sha256':result['initial_physics_sha256'],'source':ref(summary)}
            for arm,trial in arms.items():
                row[arm]={key:trial[key] for key in ('trial_seed','private_subtask_success',
                    'registered_goal_success','native_task_success','sim_steps','preposition_steps',
                    'transport_steps','wall_s')}
                row[arm].update(policy_reported_success=trial['policy_reported_success'],
                    policy_sim_steps=trial['policy_result']['sim_steps'],
                    policy_stop_reason=trial['policy_result']['reason'])
            rows.append(row);by_case[row['case']].append(row)
    assert len(rows)==36 and len(by_case)==12
    endpoints=('private_subtask_success','registered_goal_success','native_task_success')
    stats={key:paired(rows,key) for key in endpoints}
    states=[]
    for case,group in by_case.items():
        states.append({'case':case,**{arm:{key:(True if any(r[arm][key] is True for r in group)
            else False if all(type(r[arm][key]) is bool for r in group) else None) for key in endpoints}
            for arm in ('baseline','combination')}})
    args.output.mkdir(parents=True,exist_ok=False)
    path=args.output/'paired_trials.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    report={'source_commit':plan['source_commit'],'manifest':ref(args.manifest),'rows':ref(path),
        'states':12,'trials_per_arm':36,'complete_initial_hashes_all_match':True,
        'endpoints':stats,'per_state_any_success':{key:paired(states,key) for key in endpoints},
        'by_mode':{mode:{key:paired([r for r in rows if r['mode']==mode],key) for key in endpoints}
            for mode in sorted({r['mode'] for r in rows})},
        'wall_median_s':{arm:median(r[arm]['wall_s'] for r in rows) for arm in ('baseline','combination')},
        'training':False,'confirmation':False,
        'scope':'A1 Cartesian commands/prompts are diagnostic interventions only, not runtime options. Wilson over repeated trials is descriptive; per-state aggregation also reported.'}
    (args.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    table=['| 状态 | 持续抓取/子任务 基线→组合 | 登记目标 基线→组合 | 原生整局 基线→组合 |',
        '|---|---:|---:|---:|']
    for case,group in by_case.items():
        values=[]
        for key in endpoints:
            values.append(' → '.join(f"{sum(r[arm][key] is True for r in group)}/{sum(type(r[arm][key]) is bool for r in group)}"
                + (' +unknown' if any(r[arm][key] is None for r in group) else '') for arm in ('baseline','combination')))
        table.append('| '+case+' | '+' | '.join(values)+' |')
    (args.output/'paired_table.md').write_text('\n'.join(table)+'\n')
    print(json.dumps({'output':str(args.output),'endpoints':stats}),flush=True)


if __name__=='__main__':main()
