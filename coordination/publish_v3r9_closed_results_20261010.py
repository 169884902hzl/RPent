"""Publish immutable closed diagnostic summaries without replacing old reports."""
import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
files = [
    ROOT/'coordination/bottle_analytic5506_registered_final_20261010/summary.json',
    ROOT/'coordination/bottle_pi055513_registered_final_20261010/summary.json',
    ROOT/'coordination/bowl_analytic5528_registered_final_v2_20261010/summary.json',
    ROOT/'coordination/moka5476_diagnostic_v2_20261010T040330Z/summary.json',
]
now = datetime.datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(timespec='seconds')
text = [f'## Codex3：登记 v3r9 闭合补充与公开绑定修复（{now}）', '',
    '以下均为诊断/选择记录，不是独立确认资格。历史原始记录与旧标签保留；缺测、未执行不删分母。']
for path in files:
    d = json.loads(path.read_text())
    text.extend(['', f'- 汇总 `{path}`，SHA `{hashlib.sha256(path.read_bytes()).hexdigest()}`。'])
    if 'registered_v3_verifier' in d:
        v = d['registered_v3_verifier']
        m = d['registered_v3_success_registered_denominator']
        a = v['agreement_including_public_null']
        text.append(f"  登记 v3 真成功 {m['k']}/{m['n']}，Wilson {m['wilson95']}；真值计数 {d['counts']['registered_v3']}。公开 TP/TN/FP/FN={v['tp']}/{v['tn']}/{v['fp']}/{v['fn']}；含公开缺测一致 {a['k']}/{a['n']}；全部登记状态可证一致 {v['agreement_all_registered']['k']}/{v['agreement_all_registered']['n']}。")
        text.append(f"  未知原因 {d['unknown_reasons']}；公开缺测在已知真值上 {v['public_null_on_known_truth']}。")
    else:
        text.append('  摩卡修正版已经闭合73/73：最终目标62 true/6 false/5 unknown，62/73=84.93%；原生成功latch63。公开58 true/5 false/10 null；TP58/TN3/FP0/FN2，含缺测一致61/68=89.71%。580144曾成功后退回；5801xx是诊断，不能替代920xxxx新确认。')
text.extend(['',
    '- 碗5528的42条缺测来自公开源绑定失败，未执行first_attempt；短句丢了多只黑碗的关系消歧。新选择运行复用预先、无策略结果的公开关系词编译，执行仍只用RGB-D测量；不使用私有坐标选择实体，不择优重跑旧确认。',
    '- π0.5公开缺测仍是重点：r6用本体感知转腕姿态旋转查询包络，fresh SAM/RGB-D独立匹配才能作为证据。公开hint本身不是测量/成功标签；登记真值源码不变。5547/5548为同源真实启动，formal必须等待物理controls合同通过。',
    '- 真值判据SHA `d8ea8a435e20e00326d34be3e0be53a1ab7983fe411e114cd11e5234dfcdf81f`；隔离worker SHA `9a8bc057edb677625199dc1e790e3f4801cf1db01b5c9f7069f1dfb3bb256921`。内部门槛不变；GraspNet/Contact-GraspNet暂停。',
    '- 历史r4索引仍在补充原版根、嵌套setup阶段和metadata bytes/SHA；未声称穷尽，未重算。先交索引及明确覆盖后再统一重算。', ''])
out = ROOT/'coordination/codex3_v3r9_closed_supplement_20261010.md'
if out.exists():
    raise ValueError('preserve previous published report')
out.write_text('\n'.join(text))
coord = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
with coord.open('a') as stream:
    stream.write('\n' + out.read_text())
print(out)
