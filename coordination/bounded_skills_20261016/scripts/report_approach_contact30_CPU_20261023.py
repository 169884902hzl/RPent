"""Make per-state/per-point readable evidence from the closed 30 forks."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args()
r=a.report
attributions=[json.loads(s) for s in (r/'CPU_approach_pair_attribution_r2/cases.jsonl').read_text().splitlines()]
paired=[json.loads(s) for s in (r/'CPU_approach_contact30/paired.jsonl').read_text().splitlines()]
by_case={v['case']:v for v in attributions}
table=['| 状态 | 手部 | 目标/场景记录点对 | 起点最小有符号间距 mm | 起点在4mm带内点对 | 直线到位/接触 | 高位通过/到位 | 高位停止原因 |',
       '|---|---|---:|---:|---:|---|---|---|']
points=[];contacts={k:Counter() for k in ('straight_no_veto','elevated_screened')}
for row in paired:
    source=by_case[row['case']];pairs=source['pairs'];counts=Counter(p['classification'] for p in pairs)
    for i,point in enumerate(pairs):
        points.append({'case':row['case'],'point_index':i,**point})
    for arm in row['arms']:
        contact1mm=any(d < -0.001 and d < arm['initial_contacts'].get(k,0.)-0.001 for k,d in arm['contact_pairs'].items())
        c=contacts[arm['arm']];c['registered']+=1;c['executed']+=arm['steps_used']>0
        c['screen_pass']+=arm['screen_passed'];c['arrived']+=arm['arrived']
        c['contact1um']+=arm['new_or_deeper_nonattached_hand_contact'];c['contact1mm']+=contact1mm
        if arm['steps_used']==0 and arm['new_or_deeper_nonattached_hand_contact']:raise AssertionError('zero-step contact scoring')
    direct,elevated=row['arms']
    start=min((p['initial_min_signed_box_clearance_m'] for p in pairs),default=None)
    table.append('| '+row['case']+' | '+','.join(sorted({p['hand_part'] for p in pairs}))
        +f" | {counts['target']}/{counts['other_scene']} | "+('?' if start is None else f'{start*1000:.4f}')
        +f" | {sum(p['start_inside_4mm_margin'] for p in pairs)} | {int(direct['arrived'])}/{int(direct['new_or_deeper_nonattached_hand_contact'])}"
        +f" | {int(elevated['screen_passed'])}/{int(elevated['arrived'])} | {elevated['stop_reason']} |")
(r/'approach_attribution_table.md').write_text('\n'.join(table)+'\n')
fields=['case','point_index','hand_part','classification','screen_cloud','target_anchor','target_label',
    'point_world_m','initial_min_signed_box_clearance_m','this_point_start_signed_box_clearance_m',
    'this_point_rejected_signed_box_clearance_m','start_inside_4mm_margin','instance_matches',
    'captured_screen_point_distance_m']
with (r/'approach_point_pairs.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
    for point in points:
        writer.writerow({k:json.dumps(point[k],ensure_ascii=False) if isinstance(point[k],(list,dict)) else point[k] for k in fields})
(r/'approach_contact_metrics.json').write_text(json.dumps({k:dict(v) for k,v in contacts.items()},indent=2)+'\n')
text='''已完成同一完整初态的30对。修复高位路线仅3/30通过完整筛查，3例执行均跟踪误差停止，0例到位，因此不接入生产 measured_anchor，也不启动条件性的N2/155新路径回归。

| 路线 | 实际执行 | 到位 | 新增或加深接触 ≥1 µm | ≥1 mm |
|---|---:|---:|---:|---:|
'''
for name,label in [('straight_no_veto','直线，仿真诊断关闭否决'),('elevated_screened','修复高位，保留否决')]:
    c=contacts[name];text+=f"| {label} | {c['executed']}/30 | {c['arrived']}/30 | {c['contact1um']}/{c['executed']}已执行 | {c['contact1mm']}/{c['executed']}已执行 |\n"
text+='''
高位另外27例没有执行，26例扫掠否决、1例数值逆解失败，不能当作无碰撞成功。直线到位且未出现新增或加深接触为5/30。三个高位执行例的最大跟踪误差分别为4.247、4.085、3.373 cm。

CPU逐例归因覆盖324条原日志保存的点对：146条来自目标点云，178条来自场景点云，没有匹配桌面点。54条的起点最小间距已在4 mm余量内。每个记录点与保存或纯CPU重建的点云匹配误差均不超过1 µm。每个手部最多32条记录，因此这些不是全部碰撞点对。

178条场景点对中，62条距选中实例测量点云不超过8 mm，52条缺少邻近实例标签。邻近不能证明属于目标，不能据此豁免。旧指标中284条相对起点余量减小超过1 µm；余量减小不等于物理穿入，本报告的真接触计数单独来自MuJoCo。

修复仅在诊断中启用：已占用余量的连通表面按实际穿入深度不增加判定；最后一段仅允许所选目标与手指接触，手掌和其他障碍仍检查4 mm余量。未放宽阈值，未改生产速度或力。私有接触只作评判，不参与路径选择。

逐状态见 approach_attribution_table.md；逐点坐标、手部、起点/否决位间距与身份匹配见 approach_point_pairs.csv，原始精确归因见 CPU_approach_pair_attribution_r2/cases.jsonl。两臂初态及终点30/30相同，原件引用与源码树在 CPU_approach_contact30/manifest.json。
'''
(r/'APPROACH_CONTACT_RESULT.md').write_text(text)
print(json.dumps({k:dict(v) for k,v in contacts.items()}))
