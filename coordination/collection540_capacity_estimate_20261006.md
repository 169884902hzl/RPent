# collection540：冻结后采集容量与独立确认池（CPU 估算）

只读取显式原版 catalog、17 个选择/确认 manifest、2 份专家 ledger 和 1 份单技能逐次报告。没有新物理回合、训练行或 Slurm 提交；不授权采集。未打开 PRO 任务文件、人工测试文件或 sealed 内容。

## 已核产物

- 130 个原版任务（40 + LIBERO-90），官方初态 6,500；原始 state SHA 全部唯一。
- 具名选择/确认预留排除 1,809 个 state SHA。再排除 init 0–9、40/41 后，公开可用上界 3,494：train init 10–39 上界 2,593；validation init 42–49 上界 901。验证按 init 留出，不能按训练行随机切分。
- 这些仍是上界：公开的密封范围 metadata 未定位；具名清单完整性未由 Codex1 登记核全，后续确认批也会消耗新状态。

|套件|官方状态|训练上界|验证上界|
|---|---:|---:|---:|
|libero_10|500|121|56|
|libero_90|4500|1994|637|
|libero_goal|500|39|56|
|libero_object|500|139|72|
|libero_spatial|500|300|80|

## 开合独立确认池

以下均按唯一官方 state SHA 计数，重复 reset 不增加独立状态。public-safe 列排除 init 0–9、40/41；仍需扣未知密封范围。场景池只是 BDDL 元数据中真实存在该家具，不代表测量/技能已通过。

|类型|原任务目标匹配 public-safe|真实家具场景 public-safe|原目标匹配缺口（到100）|
|---|---:|---:|---:|
|drawer_open|60|1225|40|
|drawer_close|204|1225|0|
|microwave_open|0|114|100|
|microwave_close|0|114|100|
|stove_turn_on|105|708|0|
|stove_turn_off|0|708|100|

原版微波炉目标任务的独立池已经用尽：LIBERO-90 task33/35 与旧原版 Long9 选择池不能再次计作确认。原版 LIBERO-90 task34/36/37 各50个官方状态，共150个尚未预留 state；公开安全范围剩114个。可从这些真实微波炉场景预登记100个唯一状态，作为单技能反事实确认；开/关分别固定真实 setup，保留 setup/缺测失败，joint truth 单列，不把原任务 full solved() 当技能成功。剩余14个余量很小，未知密封范围可能造成硬缺口，必须在确认前核对。
抽屉与灶台可同样采用真实原版 fixture 的单技能反事实；不开新 PRO 任务，不以成功结果选状态。

## 回合和 GPU-hours 估算

按每个 train init 各1局专家和1局 done-gated DAgger：2,593 + 2,593 = 5,186 局。历史 job3414 的200局平均94.02秒、中位34.75秒、P90 336.53秒，单卡串行估算为135.44 GPU-hours。
物理分支必须每候选至少4个种子：每关键状态 C×4 次执行（C=3/6/24分别为12/24/96次）。下表用旧单技能12次逐次 wall 的中位50.18秒及P90 83.90秒作保守 fresh-reset 参考；快照恢复实际吞吐未测，不能把这些数字当精确交期。

|每局关键状态|每状态候选|分支执行次数|轨迹+分支 GPU-hours（单技能中位）|轨迹+分支 GPU-hours（单技能P90）|
|---:|---:|---:|---:|---:|
|2|3|124464|1870.3|3036.0|
|2|6|248928|3605.2|5936.6|
|2|24|995712|14014.3|23340.2|
|4|3|248928|3605.2|5936.6|
|4|6|497856|7074.9|11737.8|
|4|24|1991424|27893.2|46545.0|

不预设2–3进程/卡带来的加速，也未包含共享决策服务的额外 GPU 消耗。冻结后先用显式首批测快照分支吞吐再更新成本，不能把未执行的候选记作已验证。

## 路径、SHA 与实际命令

- 远端目录：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/collection540_capacity_CPU_20261006/`。
- `preparation/original130_catalog.json` SHA `a6b0e7ba982e6b3ecf276985b804107c349c63861bf165af0ee5ddcc67906be9`。
- `preparation/estimate_index_complete_known.json` SHA `1b42b7a98a8146cf577206da6282b747a93638e483ae058453e788d54bc9cfae`。
- `report.json` SHA `97e2db5f2a3ae837e861f712d0a077fd0ca2db6723e152650c58090a0daeeba3`。
- `scripts/estimate_v5_collection540_capacity.py` SHA `4c1ddc50fc80c3723aaa13b156f6a1dec970b8c43296efcc83fef0b6e7a3e48f`。
- 完整 inputs 及逐任务计数在 report/index；本地已按字节同步上述三份 JSON。

```bash
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python /public/home/sunyihan/rpent_libero_eval/scripts/estimate_v5_collection540_capacity.py \
  --index /public/home/sunyihan/rpent_libero_eval/results/harness_v5/collection540_capacity_CPU_20261006/preparation/estimate_index_complete_known.json \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/collection540_capacity_CPU_20261006/report.json
```

该命令已经 CPU 执行通过。输出要求新文件；复算应指定新的输出，不覆盖上述产物。

公开密封范围 metadata 定位只读了 COORDINATION/529 显式 access 注册；COORDINATION 中关于“密封范围排除”的说明没有列出 LIBERO init 范围，故报告保留缺口。没有去打开 sealed 文件查范围。
