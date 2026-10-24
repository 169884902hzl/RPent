"""Close exact-state option-expansion/model-A cohorts without mixing sources."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics


def ref(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(reference):
    path=Path(reference['path']);assert ref(path)==reference,path;return path


def wilson(k,n):
    z=1.959963984540054;d=1+z*z/n;m=(k/n+z*z/(2*n))/d
    r=z*math.sqrt(k/n*(1-k/n)/n+z*z/(4*n*n))/d
    return [m-r,m+r]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--arm',choices=['model_A','oracle_A_option10_r2'],required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    old={r['arm_id']:r for r in map(json.loads,a.baseline.read_text().splitlines())}
    plan_path=a.run/'preparation'/(a.arm+'.json');plan=json.loads(plan_path.read_bytes())
    n=46 if a.arm=='model_A' else 40;assert len(plan['jobs'])==n
    pointers=sorted((a.run/a.arm).glob('closed_*.json'));assert len(pointers)==n,(len(pointers),n)
    rows=[];sources=[];phase_counts=Counter();skill_counts=Counter();failures=Counter()
    for i,j in enumerate(plan['jobs']):
        source=checked(json.loads((a.run/a.arm/f'closed_{i:03d}.json').read_bytes()));x=json.loads(source.read_bytes())
        assert x['feedback']=={'task_success':True,'subgoal_status':False} and x['human_available'] is False
        assert type(x['success']) is bool and not x['training'] and not x['confirmation']
        b=old[x['arm_id']]
        assert x['initial_physics_sha256']==b['initial_physics_sha256'],x['arm_id']
        assert x['policy_seed']==b['policy_seed'] and j['libero_config']==b['libero_config']
        assert x['decisions']<=40 and x['sim_steps']<=10000
        assert x['source_commit']==plan['source_commit']
        for record in x['decision_records']:
            if a.arm=='model_A':assert record['selector']['selector']=='model_A_HTTP' and not record['selector']['oracle_called']
            for receipt in record['receipts']:
                skill_counts[receipt['skill']]+=1
                if receipt['outcome'] not in {'success','no_effect'}:
                    phase_counts[receipt['phase'] or 'unclassified']+=1;failures[receipt['stop_reason']]+=1
        row={'arm_id':x['arm_id'],'case':x['case']['name'],'domain':x['domain'],'success':x['success'],
            'decisions':x['decisions'],'sim_steps':x['sim_steps'],'loop_wall_s':x['wall_s'],
            'worker_wall_s':source.stat().st_mtime-(source.parent/'assignment.json').stat().st_mtime,
            'source_commit':x['source_commit'],'initial_physics_sha256':x['initial_physics_sha256'],
            'policy_seed':x['policy_seed'],'libero_config':j['libero_config'],
            'effective_k':j['k'],'registered_baseline_k':j.get('registered_baseline_k',j['k']),
            'old_pi_A':b['pi_A']['success'],'old_oracle_A':b['oracle_A']['success'],
            'old_oracle_AB':b['oracle_AB']['success'],'old_pi18':b['old_pi18'],
            'old_oracle24':b['old_oracle24'],'A1_M28':b['A1_M28'],'stop_reason':x['stop_reason'],
            'raw_summary':ref(source)}
        row['own_union_before']=bool(row['old_pi18'] or row['old_oracle24'] or row['old_pi_A'] or row['old_oracle_A'] or row['old_oracle_AB'])
        row['own_union_with_this_arm']=row['own_union_before'] or row['success']
        rows.append(row);sources.append(ref(source))
    a.output.mkdir(parents=True,exist_ok=False)
    data=a.output/'paired_cases.jsonl';data.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
    stats={}
    for domain in ['d2','original']:
        subset=[r for r in rows if r['domain']==domain]
        if not subset:continue
        k=sum(r['success'] for r in subset);n=len(subset)
        stats[domain]={'successes':k,'n':n,'wilson95':wilson(k,n),
            'median_decisions':statistics.median(r['decisions'] for r in subset),
            'median_worker_wall_s':statistics.median(r['worker_wall_s'] for r in subset),
            'mean_worker_wall_s':statistics.mean(r['worker_wall_s'] for r in subset),
            'median_loop_wall_s':statistics.median(r['loop_wall_s'] for r in subset)}
    d2=[r for r in rows if r['domain']=='d2'];assert sum(r['own_union_before'] for r in d2)==33
    changes={key:{'improved':sum(r['success'] and not r[key] for r in d2),
        'regressed':sum(r[key] and not r['success'] for r in d2),'n':40}
        for key in ['old_pi_A','old_oracle_A']}
    manifest={'arm':a.arm,'source_commit':plan['source_commit'],'plan':ref(plan_path),'data':ref(data),
        'matched_complete_initial_seed_config':len(rows),'counts':stats,'changes':changes,
        'old_own_method_union':33,'own_union_with_this_arm':sum(r['own_union_with_this_arm'] for r in d2),
        'skill_receipts':dict(skill_counts),'failure_phase_receipts':dict(phase_counts),'failure_reasons':dict(failures),
        'sources':sources,'training':False,'D2_training':False,
        'wall_scope':'N8 worker start to summary, includes initialization/restoration; loop separately retained',
        'original_six_scope':'3 distinct initial states, each two registered runs; all model effective K1; not six independent layouts'}
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    table=['| 回合 | 纯π+A | 旧oracle+A | 旧oracle+AB | A1-M | 本臂成功 | 决策 | worker秒 | 步数 | 旧并集 | 加本臂并集 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        table.append(f"| {r['arm_id']} | {int(r['old_pi_A'])} | {int(r['old_oracle_A'])} | {int(r['old_oracle_AB'])} | {'—' if r['A1_M28'] is None else int(r['A1_M28'])} | {int(r['success'])} | {r['decisions']} | {r['worker_wall_s']:.1f} | {r['sim_steps']} | {int(r['own_union_before'])} | {int(r['own_union_with_this_arm'])} |")
    (a.output/'paired_table.md').write_text('\n'.join(table)+'\n')
    lines=['# '+a.arm+' 闭合结果','','| 域 | 成功 | Wilson95% | 决策中位 | worker秒 中位/均值 |','|---|---:|---:|---:|---:|']
    for domain,s in stats.items():
        lo,hi=s['wilson95'];interval=f'{lo:.1%}–{hi:.1%}' if domain=='d2' else '三初态重复，见说明'
        lines.append(f"| {domain} | {s['successes']}/{s['n']} | {interval} | {s['median_decisions']} | {s['median_worker_wall_s']:.1f}/{s['mean_worker_wall_s']:.1f} |")
    lines+=['','同完整初态、策略种子、配置逐局核对。每局A-only、human_available=false、40决策/10000控制；不重置世界。',
        'worker墙钟来自并行N8，不是N1时延。原版六条是三初态各两条，不能视为六个独立布局。',
        '模型A按服务约定所有请求K1（原登记K4仅保留为基线身份）；旧oracle+A为K4。差值不能全归因于模型权重。',
        '并集只是这些实际方法的成功集合，不是单一闭环策略的成功率，也不是穷举数学上界；A1-M仅外部对照，不计入我们的并集。',
        '旧8eb开发回放因私有规则缺陷中止，保留原件，未并入本分母。PRO/D2/确认集不进入训练。','',
        '| 对照 | 改善 | 退步 |','|---|---:|---:|']
    lines += [f"| {key} | {c['improved']} | {c['regressed']} |" for key,c in changes.items()]
    (a.output/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'arm':a.arm,'counts':stats,'changes':changes,'own_union_with_this_arm':manifest['own_union_with_this_arm']}))


if __name__=='__main__':main()
