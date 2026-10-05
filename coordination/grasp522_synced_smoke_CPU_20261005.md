# Codex3 child：3662 同步帧只读审计

接受 parent `/root` 的独立 CPU 审计任务；不修改 probe/runtime，不提交作业、不推送、不拟合阈值。只读显式 smoke manifest、四个 episodes.jsonl 完整换行前缀，以及各闭合回合 states.json 声明的文件；未发现或读取 PRO、人工/密封文本。旧结果不变。

3658 已先交 parent 与 summary owner：4/4 case 与注册精确匹配、4/4 choices SHA，通过 133 帧逐视角布尔核对，0 矛盾、0 执行/基础设施错误；原版私有子目标完成 2/4。不能把公共放置验证代替私有完成判定。

3662 四分片均 COMPLETED / 0:0，耗时分别 1:59、6:43、10:12、3:23。以下是实际读取并保存的 CPU 审计结果，不是 Slurm 状态替代物理证据。

| 核对项 | 实际结果 |
| --- | --- |
| 显式 case / closed choices SHA | 4/4 / 4/4 |
| 同步 sample metadata 文件 SHA 与内容 | 257/257 |
| states 保存的 EEF/quat/gripper qpos 与同步 raw observation | 257/257 完全一致，最大绝对差 0 |
| 目标点 NPZ 文件 SHA、数组 SHA、shape/dtype/finite/current 来源 | 205/205 |
| 同帧 SAM mask + world 精确重建目标点数组 | 205/205 |
| states 声明的 SAM mask 原始数组 hash 前缀 | 250/250；完整文件 SHA 另行计算，未宣称已有独立期望 SHA |
| private 前后与 sample sim_time 相同 | 257/257 |
| 独立 pixel-capture sim_time 已记录 | 0；不能凭 private bracket 相同虚构这一字段 |
| 布尔逻辑矛盾 / instrument error / execution error / infrastructure error | 0 / 0 / 0 / 0 |

每个 sample 的私有标签严格复算为：相对于登记 pregrasp 的物体 lower extent 上升 ≥3 cm、目标有手指接触、且未接触原支撑几何。它是**瞬时**诊断标签，不是 0.5 秒持续夹持真值，未用最终 hold 回填早期帧。

| 类别 | samples | instant positive / negative | wide samples | wide positive / negative |
| --- | ---: | ---: | ---: | ---: |
| frypan | 120 | 1 / 119 | 97 | 0 / 97 |
| moka pot | 137 | 10 / 127 | 84 | 2 / 82 |
| 合计 | 257 | 11 / 246 | 181 | 2 / 179 |

wide 定义保留 calibration513：opening ≥0.07729756832122803 m。全部 181 wide 帧中，2 个阳性均为 null，179 个阴性有 125 个 false、54 个 null（包含 4 个 pregrasp null）。2 个 wide 阳性位于 moka centre 的 step68/69，两个相机均缺当前目标点，不能从这些帧拟合最低点数阈值。阈值继续为 null。

全部 sample 的公共 frame verdict：true 2、false 154、null 101；instant-positive 是 true 1/null 10，instant-negative 是 false 154/true 1/null 91。不得把 unknown 算作判对，不得将 257 个相关帧当成 257 次独立抓取或正式确认结果。这四个方法请求只覆盖一个原版 task/init 场景状态，不能满足独立确认门槛。

唯一公共 true / instant false：moka handle，sample20 / source_step20 / chunk66。视觉 lower 上升 4.0527 cm，私有 lower 上升 2.4970 cm；当时有单侧手指接触、无支撑接触，opening 5.3837 cm。差异在登记 3 cm lift 阈值与测量值，不能写成“没有抓住”或持续夹持失败；原始判定未改。

最终不可变报告：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp522_synced_smoke_CPU_20261005/report2/report.json`

SHA `70c01d53713840d66acd50a119b8cbdf1464d06d956e10cebe81af2fea722fb3`。

逐帧证据 `report2/frames.jsonl`，SHA `4e86112b410238df8b0a3216fb7ab9f93a35a5fd1f83e97443e527a571ec5888`。四个 `ledger0–3_closed_prefix.jsonl` 保存本次所读完整前缀，身份在报告中。第一版三回合 `report1` 保留，不覆盖。

审计脚本 `scripts/audit_v5_grasp522_synced_smoke.py`，SHA `34a7fb225ce00517aedcb2fed6755253467ed93592a992c4d916933bc41f0059`。实际运行 CPU 命令：

```bash
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
  /public/home/sunyihan/rpent_libero_eval/scripts/audit_v5_grasp522_synced_smoke.py \
  --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp520_original_frame_calibration_20261005/preparation/smoke4.json \
  --manifest-sha256 76961c5906489d856f63819177a4a00b496f3907c48dd1a14d2a29dd80dd3987 \
  --ledger /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp520_original_frame_calibration_20261005/diagnostic_job3662/part0/episodes.jsonl \
  --ledger /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp520_original_frame_calibration_20261005/diagnostic_job3662/part1/episodes.jsonl \
  --ledger /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp520_original_frame_calibration_20261005/diagnostic_job3662/part2/episodes.jsonl \
  --ledger /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp520_original_frame_calibration_20261005/diagnostic_job3662/part3/episodes.jsonl \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp522_synced_smoke_CPU_20261005/report2
```

没有新增机器人动作、capture、回执改动、标签拟合、训练行或独立 confirmation。现有同步证据支持继续原版未筛选 pilot，但 wideTP 严重不足且被遮挡，不能宣称验证器或抓取达到 95% 门槛。
