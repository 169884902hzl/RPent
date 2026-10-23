"""Close feedback arms, preserving per-episode decisions, latency and pairs."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics


def reference(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(value):
    path=Path(value['path']); assert reference(path)==value,path
    return path


def wilson(k,n):
    z=1.959963984540054
    mean=(k/n+z*z/(2*n))/(1+z*z/n)
    radius=z*math.sqrt(k/n*(1-k/n)/n+z*z/(4*n*n))/(1+z*z/n)
    return [mean-radius,mean+radius]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--suffix',default='_r1')
    args=parser.parse_args(); rows={};old=None;counts={};plans={};raw_sources=[]
    for arm in ('pi_A','oracle_A','oracle_AB'):
        plan_path=args.run/'preparation'/(arm+args.suffix+'.json')
        plan=json.loads(plan_path.read_bytes());plans[arm]=reference(plan_path)
        old=[json.loads(s) for s in checked(plan['old_pair_table']).read_text().splitlines()]
        rows[arm]={}
        for i,job in enumerate(plan['jobs']):
            raw=checked(json.loads((args.run/(arm+args.suffix)/f'closed_{i:03d}.json').read_bytes()))
            value=json.loads(raw.read_bytes())
            value['k']=job['k']
            value['libero_config']=job['libero_config']
            raw_sources.append(reference(raw))
            value['worker_wall_s']=raw.stat().st_mtime-(raw.parent/'assignment.json').stat().st_mtime
            assert value['arm_id']==job['arm_id'] and value['feedback']=={'task_success':True,'subgoal_status':arm=='oracle_AB'}
            assert type(value['success']) is bool
            assert value['decisions']<=40 and value['human_available'] is False
            assert 0<=value['sim_steps']<=10000
            assert not value['training'] and not value['confirmation']
            rows[arm][value['domain']+'|'+value['arm_id']]=value
        assert len(rows[arm])==46
        for domain in ('d2','original'):
            values=[r for r in rows[arm].values() if r['domain']==domain]
            n=len(values);success=sum(r['success'] for r in values)
            counts[arm+'|'+domain]={'successes':success,'n':n,'wilson95':wilson(success,n),
                'median_decisions':statistics.median(r['decisions'] for r in values),
                'median_wall_s':statistics.median(r['wall_s'] for r in values),
                'median_worker_wall_s':statistics.median(r['worker_wall_s'] for r in values),
                'mean_worker_wall_s':statistics.mean(r['worker_wall_s'] for r in values),
                'mean_wall_s':statistics.mean(r['wall_s'] for r in values),
                'median_sim_steps':statistics.median(r['sim_steps'] for r in values),
                'stop_reasons':dict(Counter(r['stop_reason'] for r in values))}
            if domain=='original':
                counts[arm+'|'+domain]['by_k']={}
                for k in sorted({v['k'] for v in values}):
                    subset=[v for v in values if v['k']==k];n_k=len(subset);s_k=sum(v['success'] for v in subset)
                    counts[arm+'|'+domain]['by_k'][str(k)]={'successes':s_k,'n':n_k,'wilson95':wilson(s_k,n_k),
                        **{'median_'+field:statistics.median(v[field] for v in subset)
                            for field in ('decisions','wall_s','worker_wall_s','sim_steps')},
                        'mean_worker_wall_s':statistics.mean(v['worker_wall_s'] for v in subset)}
    old_by_name={r['case']:r for r in old};paired=[]
    for key,a in rows['pi_A'].items():
        b=rows['oracle_A'][key];c=rows['oracle_AB'][key]
        assert a['initial_physics_sha256']==b['initial_physics_sha256']==c['initial_physics_sha256'],key
        assert a['policy_seed']==b['policy_seed']==c['policy_seed'],key
        assert a['libero_config']==b['libero_config']==c['libero_config'],key
        historical=old_by_name.get(a['case']['name']) if a['domain']=='d2' else None
        if historical:
            assert a['initial_physics_sha256']==historical['initial_physics_sha256'],key
        paired.append({'case':a['case']['name'],'arm_id':a['arm_id'],'domain':a['domain'],
            'initial_physics_sha256':a['initial_physics_sha256'],
            'policy_seed':a['policy_seed'],'libero_config':a['libero_config'],
            'old_pi18':historical['pi_only_success'] if historical else None,
            'old_oracle24':historical['oracle_from_start_success'] if historical else None,
            'A1_M28':historical['A1_M_success'] if historical else None,
            **{arm:{k:rows[arm][key][k] for k in ('success','decisions','wall_s','worker_wall_s','sim_steps','stop_reason')}
               for arm in rows}})
    args.output.mkdir(parents=True,exist_ok=False)
    data=args.output/'paired_cases.jsonl';data.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in paired))
    table=['| 回合 | 旧 π | 旧 oracle | A1-M | π+A 成功/决策/秒 | oracle+A 成功/决策/秒 | oracle+AB 成功/决策/秒 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in paired:
        line=[r['arm_id'],*['—' if r[k] is None else str(int(r[k])) for k in ('old_pi18','old_oracle24','A1_M28')]]
        for arm in rows:
            x=r[arm];line.append(f"{int(x['success'])}/{x['decisions']}/{x['worker_wall_s']:.1f}")
        table.append('| '+' | '.join(line)+' |')
    (args.output/'paired_table.md').write_text('\n'.join(table)+'\n')
    lines=['# 成功反馈与持续尝试', '', '| 方法 | 域 | 成功 | Wilson 95% | 决策中位 | worker 墙钟中位/均值秒 | 循环中位秒 | 仿真步中位 |',
        '|---|---|---:|---|---:|---:|---:|---:|']
    for key,row in counts.items():
        arm,domain=key.split('|');lo,hi=row['wilson95'];interval=f'{lo:.1%}–{hi:.1%}' if domain=='d2' else '见 K 分列'
        lines.append(f"| {arm} | {domain} | {row['successes']}/{row['n']} | {interval} | {row['median_decisions']} | {row['median_worker_wall_s']:.1f}/{row['mean_worker_wall_s']:.1f} | {row['median_wall_s']:.1f} | {row['median_sim_steps']} |")
        for k,sub in row.get('by_k',{}).items():
            lo,hi=sub['wilson95'];lines.append(f"| {arm} | original K={k} | {sub['successes']}/{sub['n']} | {lo:.1%}–{hi:.1%} | {sub['median_decisions']} | {sub['median_worker_wall_s']:.1f}/{sub['mean_worker_wall_s']:.1f} | {sub['median_wall_s']:.1f} | {sub['median_sim_steps']} |")
    changes={}
    d2=[r for r in paired if r['domain']=='d2']
    for arm,baseline in [('pi_A','old_pi18'),('oracle_A','old_oracle24'),('oracle_AB','old_oracle24')]:
        known=[r for r in d2 if type(r[baseline]) is bool]
        changes[arm+'_vs_'+baseline]={'paired_n':len(known),'baseline_unknown':len(d2)-len(known),
            'improved':sum(r[arm]['success'] and not r[baseline] for r in known),
            'regressed':sum(r[baseline] and not r[arm]['success'] for r in known)}
    changes['oracle_AB_vs_oracle_A']={'paired_n':len(d2),'baseline_unknown':0,
        'improved':sum(r['oracle_AB']['success'] and not r['oracle_A']['success'] for r in d2),
        'regressed':sum(r['oracle_A']['success'] and not r['oracle_AB']['success'] for r in d2)}
    lines+=['','| 逐状态比较 | 配对数 | 改善 | 退步 |','|---|---:|---:|---:|']
    lines += [f"| {name} | {value['paired_n']} | {value['improved']} | {value['regressed']} |" for name,value in changes.items()]
    lines+=['','每回合最多40次决策、10000环境步；失败或无进展回执交还决策，不重新初始化世界。',
        'A是只读原生成功标志；B是显式授权的登记谓词真值。两臂oracle自身均可读私有进度，B的公开与否不构成新增oracle知识。',
        'oracle使用规则与历史有限采样的方法偏好；本表是可执行诊断回放，不是穷尽全部动作与种子的数学上界。',
        '逐局表墙钟为worker启动至summary写出（assignment和summary时间戳，含环境初始化、初始感知与恢复）；JSONL同时保留恢复后的决策循环wall_s。并行N8运行，不称N1时延。',
        '原版6臂是3个独立初态各K1/K4，不视为6个独立布局。',
        '原版 Wilson 按 K 分别使用3个初态；不把6个配对运行当作6个独立布局。主表使用冻结v8菜单，v9新接触技能的训练状态实测另列。',
        '对旧基线的差值同时包含成功反馈、持续尝试与宽容准备，不能归因于某一个改动。',
        '逐回合决策、墙钟、停止原因见paired_table.md和paired_cases.jsonl；D2、PRO与确认集不进入训练。']
    (args.output/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    summary={'counts':counts,'pairs':reference(data),'complete_initial_SHA_matched_pairs':46,
        'D2_initial_SHA_matched_old_pi':40,'plans':plans,'raw_summaries':raw_sources,'training':False}
    summary['per_state_changes']=changes
    (args.output/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))


if __name__=='__main__':main()
