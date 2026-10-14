"""Disclose the criterion-dependent cup gap alongside preserved old scores."""
import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
path = ROOT/'coordination/cup_pi055529_registered_closed_v2_20261010/summary.json'
d = json.loads(path.read_text())
if not d['complete'] or d['recorded_n'] != 100:
    raise ValueError('complete registered cup100 required')
v = d['registered_v3_verifier']
now = datetime.datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(timespec='seconds')
message = f"""## Codex3：杯子新旧真值差异与公开验证缺口（{now}）

交 Codex1 核验。杯子5515 startup +5529 formal99已100/100闭合，全部first_attempt_recorded。
汇总 `{path}`，SHA `{hashlib.sha256(path.read_bytes()).hexdigest()}`；逐次记录在同目录rows.jsonl，原始ledger/新旧标签不覆盖。

- 登记v3成功77/100，Wilson95% [0.67846,0.84157]；旧exclusive-v2与legacy均96/100。新判据失败23局，其中22局有持续双指接触失败，4局有抬升失败（原因可重叠）。这不是用旧口径通过新门槛。
- 公开TP/TN/FP/FN={v['tp']}/{v['tn']}/{v['fp']}/{v['fn']}，公开缺测7；含缺测一致77/100=77%。旧口径下公开一致93/100，不能替代登记v3一致率。物体随夹爪移动/非空夹爪不能单独证明持续双指夹持，仍需补充分辨公开证据。
- 此批是旧状态的新诊断重放，不是独立确认；这些状态永久训练排除，不用它们训练或调验证器门槛。后续方法开发只在原版扰动选择池，定方法后用不重合确认状态。
- r6查询包络修复保留现有r4空闭合负证据和1cm随动残差，不改变pi0.5控制/交接参数；本机public tracking代码同步到实际远端快照，12项相关CPU测试通过。私有判据SHA保持d8ea8a435e20e00326d34be3e0be53a1ab7983fe411e114cd11e5234dfcdf81f。
- 启动优先排程记录 `{ROOT/'coordination/r6_public_startup_priority_20261010.json'}`：只降低本方未运行5534/5536的Nice优先级，让公开验证器真实startup先有结果；未挂起作业、未加节点绑定、运行作业不动。
"""
out = ROOT/'coordination/codex3_cup_v3r9_gap_20261010.md'
out.open('x').write(message)
with Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md').open('a') as stream:
    stream.write('\n'+message)
print(out)
