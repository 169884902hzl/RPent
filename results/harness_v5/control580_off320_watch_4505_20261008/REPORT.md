# control580 固定 off320 首局 4505 开发结果

4505_0 COMPLETED 0:0，墙钟 10 分 20 秒。原版 libero_goal task7 / train seed0，沿用 source555 加 r4 独立预算覆盖，同一 run_capture.sbatch。没有重跑确认状态或最终评测。

## 完整物理记录

- on160 + off320，共 2400 contact controls；另有 24 open-gripper temporal hold controls，以及独立 release、retreat 脚本动作。
- 公开 off ledger 完整 320 行，每行实际执行 5 controls，source_step 严格递增。
- 私有 labels_chunk.jsonl 完整 482 行（on161 + off321，各含初始状态），全部 controller_access=false / affects_actions_or_stop=false，并与 320 个 off 块末端的公开执行记录逐一配对。
- collector_boundary.status=completed，model_or_skill_success=null，stop_admitted=false；这是完成采集，不代表关火最终成功。

## 真值终点与退回

47/320 个保存的 off 块末端 turn_off=true，其中前 160 块 44 个，后 160 块 3 个。首次达到终点为块22 / 110 controls / q=-0.005481 rad。块49 / 245 controls / q=0.012038 rad 已退回 false。真值为真的连续块区间为：22–48、52–54、61–65、69–71、88、108–110、152–153、181、270–271。

最终块320 / 1600 off controls 的 q=0.054040 rad，turn_off=false；after_contact、after_release、after_retreat 均 turn_off=false。首次成功之后有 252 个保存块末端为 false。

这局明确观察到“到达关火终点后继续动作，随后退回”。公共停止仍关闭，固定预算没有根据任何私有标签提前结束。增加预算不能代替终点停止。r3 同一 raw state 的 off160 从未在保存块末端关火，而本次首次成功发生在前 160 块内；π0.5 跨跑中间动作/噪声未固定，所以不能把跨跑变化归因于预算单项。

真值每 5 controls 保存一次；不能把 47/320 当作逐 control 成功率或独立任务成功率，也不对这些同局相关帧计算总体 Wilson 区间。本局最终关火失败保留。

## 公开测量

release / retreat 后时序共 6 frame / 12 view。只有 4 个 view 重新查询 control，全部 no_valid_current_control / unmeasured；control_pose 和 directed angle 均 0。另 8 个 view 故意只保存 raw RGB-D，不计为 SAM 查询失败。时序恢复帧全部私有 turn_off=false，因此正类来自已保存的 off 块末端 raw RGB-D，不能声称现行几何验证器已能测到终点。

后续只能用 train seed0–2 的已登记公开多帧 RGB-D 和本体证据拟合开发验证器；私有谓词只进标签。validation seed3–4 保持未用，不用于拟合或调阈值，资格 pending。当前 stop_admitted=false。

## 产物

运行时 manifest SHA：`10d3dfb57daae71fb5b9b36bc27d372ef61709862d9b84187b269afbecf000a4`

运行目录：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_off320_original_r4_20261008/probe_job4505/part0/`

report.json 记录所有 manifest/ledger 引出的输入路径和 SHA、完整块末端标签、公开测量可用性。paired_report.json 与原 r3 seed0 按 raw_state_sha256 配对。源 commit 为 c56de638fc5a5f0376194768b4d3d484369eb435；普通 runtime / planner / 字段格式未修改。
