# 抽屉 v9：公开面身份问题、中性保持与 CPU 数据合同

已实现 `drawer_endpoint_hold_v9` 独立开关，默认关闭。旧 `drawer_public_stop_v6` 保留，供修前对照。v9 每完成一个 π0.5 块观察一次；首个**准入的公开端点**出现后，不再执行下一块，而执行 6 个零 delta 控制步（0.3 秒，夹爪命令为 0，保持当前执行器目标），取得新第二帧。两帧必须有不同 `source_step`、端点仍成立、固定参考面稳定、沿朝外轴的移动面变化 ≤5 mm；缺帧、失效、中断都不停止。保持阶段不 release、不 retreat，也不读私有 joint/solved。

该机制不是关闭验证器资格。保存轨迹证明现行几何会把静止后部面当移动抽屉面；v9 的 close 停止与最终回执均记 `unmeasured`（`drawer_close_face_identity_not_qualified`），直到公开面身份验证器经过独立确认。open 继续复用既有 signed-v6 的 141 mm 门槛；关闭几何估计 0.5 mm 门槛保留为诊断值，未放宽门槛。

入口：`robots/libero/v5_drawer_endpoint_hold.py:make_drawer_endpoint_hold`，经 `V5Executor.drawer_public_stop` 的 v9 分支调用。最终回执用同模块的 `measure_public_drawer_endpoint`。行为只在显式同时启用 v6/v9 的原版开发包中测试；未启用到评测、冻结或训练采集。

## 已保存证据

沿此前登记的 16 份显式 4319/4327 ledgers 复算，原始字节哈希一致，没有改旧记录/判定，没有新物理回合。两版为相同 20 个状态配对，关闭各 10 个。

| 作业 | 几何规则 | TP | FP | TN | FN | unknown |
|---|---|---:|---:|---:|---:|---:|
| 4319 | 已保存 signed-v6 | 16 | 4 | 8 | 0 | 47 |
| 4319 | 只保留双视角 moving 面 | 8 | 1 | 2 | 0 | 64 |
| 4319 | 双视角 + signed ≥−0.5 mm | 4 | 1 | 2 | 0 | 68 |
| 4327 | 已保存 signed-v6 | 14 | 7 | 23 | 2 | 75 |
| 4327 | 只保留双视角 moving 面 | 5 | 4 | 9 | 0 | 103 |
| 4327 | 双视角 + signed ≥−0.5 mm | 0 | 4 | 9 | 0 | 108 |

分母为保存的 post-block 测量样本，不是独立回合或确认批。后两项只是 CPU 假设，不准入 runtime；增加 abstain 不能当可靠性通过。

4327 的原版 LIBERO-90 t23/s20：10 个动作块中私有诊断 q 都为 −0.1576836229、始终未关闭；公开移动面却从 y=0.06009 m 换成 y=0.22644 m（第 5 块）。固定柜体面 y=0.21777 m；新 moving 面只有 wrist 支持，agentview moving=null。当前实体 ID 相同不能证明实际拟合面身份相同。私有 q 只在隔离的诊断 ledger，未用于停止或 ROI。

远端报告：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_close_return_audit_CPU_20261008/identity_r1/report.json`，SHA256 `99b4aec3cf5578753fdf65f21adb3f4e36230150cd9c067ccb6f2162d5f5cbb6`。

## 可执行的多帧公开验证器合同

CPU 索引产物：`.../drawer_close_return_audit_CPU_20261008/temporal_inputs_r1/manifest.json`，SHA256 `9ed8fd75c08fb99a2e62917ecc5f0daac9888e8d337be1ff88835518d94ee826`。

- 306 个保存时序样本：train open 77、close 155；validation open 33、close 41。14/6 个互斥原始状态 SHA 分组；配对的两种 harness 版本始终同组。
- 固定分割规则：已登记 seed 30 为验证，其他登记选择 seed 为训练；不依据成绩。当前无独立确认批，不能授资格。
- 每条公开输入包含 before + 最近 3 帧 agentview/wrist 的 RGB 和校准世界点云显式文件/SHA、测量柜体 bbox、测量面几何、EEF 与夹爪开度。坐标来源 `calibrated_rgbd_and_robot_proprioception`；不含 BDDL 目标、私有 joint、sim 物体坐标或成功标签。
- 80 条不足 3 个当前帧，保留 unknown；226 条有完整时序。346 个唯一索引帧都有两相机原文件。保存时采样每 5 块，不能补造中间画面；v9 新开发包按每块记录。
- 真值只在独立 `private_labels.jsonl`，按 sample_id 对齐、`controller_access=false`，`judge=measured_predicate`。这些 LIBERO-90 选择诊断数据只用于小验证器开发，不进入机器人决策 SFT/DAgger；不改变原版 40 任务训练边界。
- 现有共享特征入口：`robots.libero.v5_temporal_verifier.frame_features` + `sequence_features`，profile=`world_xy_grid_v1`；CPU 编码器调用 `scripts.prepare_v5_temporal_endpoint_cpu.encode_sequence`，不是另写一个特征流水线。
- 下一步物理确认需新状态、按原门槛登记；当前没有模型已训练、没有关闭资格、没有新的物理成绩。

本目录的 `prepare_public_temporal_inputs.py` 和 `encode_public_temporal_inputs.py` 可直接执行。只读取 manifest 中显式列出的 ledgers/每帧文件，未枚举 artifacts。

## 窄验证与同源单局包

已执行：

```bash
python3 -m pytest tests/unit_tests/robots/libero/test_v5_drawer_endpoint_hold.py tests/unit_tests/robots/libero/test_v5_drawer_public_stop.py -q
```

28 passed；覆盖首次端点后无第二个 policy block、实际 6 步零控制、新第二帧、失去端点、缺测、非公开来源、hold 被中断、关闭面身份 abstain，以及旧 v6 路径。`git diff --check` 与 launcher `bash -n` 通过。本机 pytest 提示缺 timeout 插件，不影响这批测试。

`prepare_single_case.py` 从旧 4327 同源 20 态 manifest 精确选取 t23/s20 的已访问原版状态，保持 instruction/reset/setup/160 完整块及评分不变；只启用 v9 every-block 公开记录。`run_single_case.sbatch` 先查 source/input SHA 和原始状态字节，独立目录执行。当前未提交 GPU；源码快照、准备后的 manifest 与真实 CPU preflight 将另附 continuation。
