# control580 r3 4495 配对诊断与 off320 开发入口

4495_0 已 COMPLETED 0:0，墙钟 6 分 43 秒。完成的是固定物理采集，不代表关火成功或技能准入。只用原版 libero_goal task7 的已访问 train seed0。

## 物理结果

| 同一 raw state | off 块末端关火 | off 末端关节角 | after_contact / release / retreat |
|---|---:|---:|---|
| r2 job4467：off 前 release、retreat、12 hold controls | 0/160 | 2.093517 rad | turn_on 均 true；turn_off 均 false |
| r3 job4495：off 前保持姿态，仅采图 | 0/160 | 0.234521 rad | turn_on、turn_off 均 false |

每个块实际执行 5 controls，私有真值每块末端保存一次；不能把 0/160 写成逐 control 的 0/800。私有 labels_chunk.jsonl 共 322 行（on/off 各含初始状态及 160 个块末端），与公开执行块时间点配对完全一致，私有标签均标为 controller_access=false、affects_actions_or_stop=false。

r3 实际 contact controls 为 on800 + off800；另有 24 个 open-gripper hold controls，以及独立 release、retreat 的脚本运动。因此 1600 不是所有物理控制总数。末 10 块的 q 从 0.860441 降至 0.234521 rad；末 5 块仍持续下降，EEF 每块位移约 2–3 mm，支持登记固定更长开发预算作判别实验。该局从未在保存的块末端达到 turn_off，无法讨论“已关火又退回”，也未保存逐 control 真值来排除块内短暂成功。

6 个时序 frame / 12 个 view 中，真正重新查询 control 的 view 只有 4 个，全部 no_valid_current_control / unmeasured；control_pose、directed angle 均为 0。另 8 个 raw view 故意不重复 SAM，只保留图像，不计为 SAM 查询失败。公开接口没有接触传感器，retreat 命令也不能证明机械臂已撤离到无遮挡位置。stop_admitted=false。

## 4335 与 4495 的最早分歧

两局 raw state SHA 相同；初始 agentview / wrist high RGB、world 点云和 cached agentview policy PNG 的 SHA 相同。两局实际均是 on160 / off160，每块分别调用 vla_act(max_chunks=1)，不是一次 max_chunks=160。

第一个可见分歧在 on 第 1 块第 1 个 action。off 前 EEF 已相差约 2.82 cm。因此不能把结果差异单项归因于 off 前 release、retreat 或采图。prefix_diagnosis.json 保存两局前三个块的所有动作、初始输入哈希、pre-off 公开观测及 r3 末十块的 EEF 位移和私有诊断角度。

当前安装的 OpenPI/RLinf 代码在 eval 下仍在 noise=None 时使用 torch.normal 采样初始噪声。没有保存推理时 RNG 状态和完整 native wrist policy / proprioception 输入，不能宣称全模型输入一致，也不能把本次分歧正式归因于某个 seed。

## off320 独立开发入口

新版本 temporal-control-capture/4-dev 固定 on160 / off320，保留 pre-off 姿态，只用原登记 train seed0–2；validation seed3–4 排除。原始 r2、r3 和既有 source555 不修改。执行源码由 immutable source555 加 r4 的 collector / driver / diagnostic server 覆盖构成，25 个显式文件逐一记录 SHA；不用 glob/scandir。

新 manifest：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r4_off320/capture_manifest.json`

SHA-256：`10d3dfb57daae71fb5b9b36bc27d372ef61709862d9b84187b269afbecf000a4`

固定 2400 contact controls，另 24 hold controls 和独立 release/retreat。预算仅来自 manifest 的整数，不根据关节、谓词、私有标签停止。公开停止仍关闭，私有评分只在执行之后保存。off320 私有 ledger 应为 482 行（on161 + off321）。

默认 off160 合同测试 7/7，新 off320 的执行计数、环境作用域、私有 ledger 回归 3/3。3 个分片均已使用同一 run_capture.sbatch 做 CPU 预检，全部 passed、source_files_checked=25；物理首局尚待主代理提交。

首局只提交：
`sbatch --array=0-0%1 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r4_off320/run_capture.sbatch`

其余分片必须等同一 snapshot / launcher 首局保存实际 physical controls 才放行。预期首局产物为 `temporal_control580_off320_original_r4_20261008/probe_job<job>/part0/` 下的 collector_boundary.json、episodes.jsonl、case/public_red_chunks.jsonl 和 labels_chunk.jsonl。startup_error / collection_error 均非零退出；exit0 本身不算物理证据。

已有 r3 同 launcher 物理合同的确切路径为：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_original_r3_20261008/probe_job4495/part0/collector_boundary.json`

以及同目录 episodes.jsonl，和该行显式 output_dir 引出的 public_red_chunks.jsonl / labels_chunk.jsonl。report.json 的 inputs 记录全部路径与 SHA。

本报告是开发诊断；未训练模型、未用于冻结或独立确认。确认排除注册表仍标记 incomplete，只能说对已登记排除项 overlap=0。
