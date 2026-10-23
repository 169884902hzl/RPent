"""Report the completely closed model arm independently of pending recovery forks."""
import argparse
from collections import Counter
import json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--closed',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
manifest=json.loads((a.closed/'manifest.json').read_text())
rows=[json.loads(s) for s in (a.closed/'paired_cases.jsonl').read_text().splitlines()]
original=[json.loads(s) for s in (a.closed/'original6.jsonl').read_text().splitlines()]
assert len(rows)==40 and len(original)==6 and all(r['v_next_b_success'] is not None for r in rows+original)
rows=[{k:v for k,v in r.items() if not k.startswith('pi_then_oracle')} for r in rows]
a.output.mkdir(parents=True,exist_ok=False)
(a.output/'paired_cases.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
(a.output/'original6.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in original))
comparison={key:{'improved':sum(r['v_next_b_success'] and not r[key] for r in rows),
    'regressed':sum(not r['v_next_b_success'] and r[key] for r in rows),
    'both_success':sum(r['v_next_b_success'] and r[key] for r in rows),
    'both_failure':sum(not r['v_next_b_success'] and not r[key] for r in rows)}
    for key in ('pi_only_success','v_next_a_success','oracle_from_start_success')}
out={'D2':{k:manifest['D2'][k] for k in ('pi_only_success','v_next_a_success','v_next_b_success','oracle_from_start_success','A1_M_success')},
    'original6':manifest['original6'],'paired_comparison':comparison,
    'same_complete_initial_as_pi_only':46,'human_available':False,
    'model_source_tree':'4718f24e61851aacd10ee25a0f9818d550b61a53',
    'adapter_sha256':'253e09f0de4b833e602dcb2abd4e40a2652782485641fbf3b2bb8477830a8af7',
    'comparison_caveat':manifest['comparison_caveat'],'original6_scope':manifest['original6_scope'],
    'interface_error_attempts_preserved':True,'oracle_choices_used':0,'training':False,'evaluation_only':True}
(a.output/'manifest.json').write_text(json.dumps(out,indent=2)+'\n')
text='''v-next-b闭环已全部完成：D2为10/40，原版为1/6；两者均未超过只用π的18/40、6/6。
全部46臂在开跑前恢复与纯π相同的完整物理初态，每条请求显式human_available=false，运行选择不使用oracle。
合法集由4换成5，同时引入schema7人类能力字段、扩展候选编码和32k长度上限，因此差额不能只归于权重。

| D2方法 | 成功 | 95% Wilson |
|---|---:|---:|
'''
for key,label in [('pi_only_success','只用π，失败重试一次'),('v_next_a_success','v-next-a，旧合法集4'),('v_next_b_success','v-next-b，合法集5'),('oracle_from_start_success','开局oracle独立回放'),('A1_M_success','A1-M')]:
    m=out['D2'][key];lo,hi=m['wilson95'];text+=f"| {label} | {m['success']}/{m['n']} | {lo*100:.1f}–{hi*100:.1f}% |\n"
text+='\n| 场景 | 只用π | v-next-a | v-next-b | 开局oracle | A1-M | 决策数 | 仿真步 |\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
for r in rows:
    text+='| '+r['case']+' | '+' | '.join(str(int(r[k])) for k in ('pi_only_success','v_next_a_success','v_next_b_success','oracle_from_start_success','A1_M_success'))+f" | {r['model']['decisions']} | {r['model']['sim_steps']} |\n"
text+='\n| 原版臂 | 只用π | v-next-b | 停止原因 |\n|---|---:|---:|---|\n'
for r in original:text+=f"| {r['arm_id']} | {int(r['pi_only_success'])} | {int(r['v_next_b_success'])} | {r['model']['stop_reason']} |\n"
text+='''
原版6臂是3个独立初态分别按K1/K4运行，不能当作6个独立布局。新模型原版1/6的Wilson区间为3.0–56.4%，纯π6/6为61.0–100%。

原服务11688没有修改。原始120编码/16k请求产生的接口错误尝试全部保留，闭合重跑使用同一adapter；扩展编码保留前120项映射，增加136个验证为单token的字符，不删候选。只取消自有副本11709/11713。原件引用、每局初态SHA、实际服务版本及四段时延保留在paired_cases.jsonl与original6.jsonl。
'''
(a.output/'MODEL_CLOSED.md').write_text(text)
print(json.dumps(out))
