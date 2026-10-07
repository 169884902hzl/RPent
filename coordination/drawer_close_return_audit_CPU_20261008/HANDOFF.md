# 原版抽屉“已关上又退回”与公共停止器 CPU 审计

复用 4319/4327 正式阶段报告，再沿登记 manifest 读取 16 份明确列出的原始 `episodes.jsonl`。原始字节哈希均与正式汇总的 captures 一致，20 个注册状态均覆盖。只做 CPU 分析，没有改源代码、旧判定或记录，没有新物理回合。

## 结果

两版各自的关闭试验均为：曾达官方请求端点 9/10，最终保住端点 7/10（Wilson 95%：39.68–89.22%）；“达端点后又丢失”2/10（5.67–50.98%）。两版是相同 20 个状态配对，不是 40 个独立初态。

| 版本/作业 | 关闭接触中丢端点 | 接触结束后丢端点 | 公共停止 | 停止时真值已经 false | 开启最终端点 |
|---|---:|---:|---:|---:|---:|
| clearance-v8 / 4319 | 1 局，2 次转换 | 1 局，release 后 | 9/10 | 2/9 | 10/10 |
| frontmost+clearance / 4327 | 1 局，1 次转换 | 1 局，release 后 | 8/10 | 2/8 | 10/10 |

“接触结束后丢端点 1 局”是已有正式报告的范围；本次补齐了此前未合并统计的 **接触过程中先关上、继续动作又打开**。不能把两者合并成“退避导致”。每个关闭试验的三个最终失败互斥：从未关上 1、继续接触中丢失 1、release 后丢失 1。

## 逐局关闭配对

`首次达标` 用已经执行完成的动作块数，下面不是 runtime 的 truth stop。每块 5 个控制步。

| 原版 task/seed | 4319 首次达标/总块 | 4319 最终 | 4327 首次达标/总块 | 4327 最终 | 保存证据的解释 |
|---|---:|---|---:|---|---|
| t23/s10 | 23/30 | true | 26/35 | true | 最终保住 |
| t23/s20 | 未达/10 | false | 未达/10 | false | 两版 public 在第 5、10 块均误判 true |
| t0/s10 | 12/20 | true | 12/20 | true | 最终保住 |
| t23/s30 | 25/30 | true | 20/25 | true | 最终保住 |
| t0/s20 | 12/160 | true | 12/160 | true | 两版已关住，但 public 未量到稳定固定参考面，跑满预算 |
| t28/s10 | 14/20 | true | 14/20 | true | 最终保住 |
| t0/s30 | 12/20 | true | 13/30 | true | 最终保住 |
| t22/s10 | 19/25 | true | 61/70 | false | 4327 public stop 时 true，首次保存 false 在 release 后 |
| t22/s20 | 18/35 | false | 18/160 | true | 4319 第 25、31 块后 true→false；4327 保住却漏停 |
| t22/s30 | 19/25 | false | 20/75 | false | 4319 release 后丢失；4327 第 25 块后丢失，此后仍执行 50 块 |

逐局原始文件、行号、全部公共测量、真值转换和分阶段状态见 `per_trial.jsonl`；没有重建未保存的 release EEF 轨迹。

## 公共停止器实际行为

- 入口 `V5Executor.drawer_public_stop`：4319/4327 冻结源码第 1814 行；当前工作副本第 1881 行。
- 三者函数 SHA 一致：`8a8dc24d11989fb61876625936023b932dd19996a85070314ba0e3c7d59cbd3b`。
- 每 5 块刷新一次当前 RGB-D，必须连续两次几何 verified、不同 source_step、固定面稳定且沿测得朝外轴位移 ≤5 mm，才停止 π0.5。两次之间仍执行 π0.5 接触动作，没有保持端点的中性稳定阶段。
- 4319 t22/s20：第 20 块 public=true/private=true；第 25 块两者 false；第 30 块两者 true；第 35 块 public=true/private=false，随后误停。
- 4327 t22/s30：第 20 块 public=true/private=true；第 25 块两者 false。第 70、75 块 public=true/private=false，才停止。
- t23/s20 两版测得 signed extension 约 −8.7/−9.0 mm，但官方端点始终 false。它不是只改 0.5 mm 阈值就能解释的临界误差，需核对移动面与固定面的几何对应。
- t0/s20：已关住后仍跑 148 个块。4327 t22/s20：第 18 块起持续关住，公共第 20 块却测到 62 mm extension，之后多为 missing moving/static face，仍跑至 160。漏测没有伪造成功，但会继续接触和耗预算。
- 原版 WhiteCabinet `close` 是 qpos >0；公共 close 是测得 extension ≤0.5 mm。真值只用于本 CPU 诊断与标签，没有用于动作、ROI 或停止。

## 下一步开发方案（尚未实现或物理验证）

1. 在第一帧**可信公共**关闭证据出现后暂停 π0.5 接触，改为短中性稳定控制并重新测量第二帧。先做同选择状态的开发对照，确认其能减少“两个观测间又推拉开”。不能把第一帧 true 直接当成功。
2. 优先修 t23/s20 与 t22/s20 的面身份/固定参照失配：当前实体 ID 对得上不证明拟合点属于同一实际抽屉；需用选中部件的当前双视角几何与固定柜体锚点核对。保留所有 false/null，不放宽阈值。
3. 将 release 与 clearance 作为需要测量的保持端点阶段；用 RGB-D 和本体感知核对松手/撤离的变化。现有记录只能定位 release 阶段丢端点，不能断言“夹着把手拉开”或确定具体接触原因。
4. 在原版选择状态验证后，再按独立确认批的原定门槛验收；这些每类 10 局的选择结果不授资格。

以上仅方案；未修改抽屉、微波炉、灶台运行代码或启用任何私有真值控制。

## 产物

远端：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_close_return_audit_CPU_20261008/r1/report.json`

SHA：`89f544835ca96853680ea528c9296ca0cc8b921093122495519849dbd835c633`

同目录 `per_trial.jsonl` 保存全部 40 次执行的逐次记录与原始 locator；`explicit_inputs.json` 和 `audit_saved_trajectories.py` 位于父目录，loader 只读取显式引用。

CPU 命令（已执行，exit 0）：

```bash
python3 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_close_return_audit_CPU_20261008/audit_saved_trajectories.py \
  --inputs /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_close_return_audit_CPU_20261008/explicit_inputs.json \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_close_return_audit_CPU_20261008/r1
```

复用的正式证据：`drawer569_monitor_CPU_20261006/final_20261006T180710.101434Z/fixture_stage_scoring_report.json` 与 `drawer571_monitor_CPU_20261006/final_20261006T181240.205782Z/fixture_stage_scoring_report.json`。原判定全部保留。
