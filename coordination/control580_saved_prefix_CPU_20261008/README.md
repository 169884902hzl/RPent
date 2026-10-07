# 灶台保存前缀 CPU 对照交接

本包只复用原版 `libero_goal/task7/init2`，是既有验证器训练态上的物理诊断，不是确认批，不进入训练或最终评测。没有读取 val3/4、PRO 扰动、密封集或人工指令。

## 已真实执行

固定前缀：on160 + off20，共 900 个控制；每块 5 控制。恢复官方初始状态后，按已固定 SDK 执行 15 个开夹爪 settling 控制，再执行保存的 float32 动作。两次重放各有 180 个检查点，动作 SHA、公开 EEF、夹爪开度全部逐块精确一致。

注意 reset 的实际顺序是 seed → reset → set_init_state → 15 settling 控制 → 900 个保存动作；不是从 raw state 直接播动作。

前缀动作字节 SHA256：`ded3f8681b9531f519e5e672033f436d12a6838a957a36e6faca63c2d962c89c`。

随后各执行固定 20 步：

| 后缀 | 控制向量 | 执行后严格 turn_off | 执行后私有旋钮 qpos |
|---|---|---|---:|
| release | `[0,0,0,0,0,0,-1]` | false | 0.004612754088495409 |
| neutral / 不松手 | `[0,0,0,0,0,0,0]` | false | 0.005232822735097805 |

两分支执行时间相同，私有标签只在所有预定物理执行结束后读取。未使用 qpos 决定动作或停点。原 run 接触终点为 true，两种后缀均回退；因此不能把回退归为 release 独有。release 分支的终点 qpos 与原 run 的第一帧 after_release 相同。

远端不可变入口：

`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/control580_saved_prefix_CPU_20261008/job4538_part2_replay_r1/manifest.json`

SHA256：`7eb5e2dd17626a7e17565404f408092c724261d40c4b85b3bc8ef6b96eebc1bd`。

解释器：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

环境：`LIBERO_TYPE=standard CUDA_VISIBLE_DEVICES=''`；执行时 source555 为 PYTHONPATH，关闭相机 renderer，不调用 SAM、VLA 或决策服务。源码入口 `scripts/replay_v5_stove_saved_prefix_CPU_20261008.py::main`。reset adapter、SDK、ControlEnv 和私有评分函数的确切路径与 SHA 均在 replay_manifest.json。

## 九局固定块诊断

完整包：`../control580_fixed_withdrawal_CPU_20261008/grid9_same_run_r2/`。远端对应 `results/harness_v5/control580_fixed_withdrawal_same_run_CPU_20261008/grid9_same_run_r2/summary/`。

| off块数 | init | 接触终点 qpos | 松手三帧末端 qpos | 撤臂三帧末端 qpos | 接触终点 off → 松手后 off |
|---:|---:|---:|---:|---:|---|
| 20 | 0 | 0.731983 | 0.729532 | 0.855426 | false → false |
| 20 | 1 | 0.203488 | 0.103508 | 0.001271 | false → false |
| 20 | 2 | -0.005364 | 0.008832 | 0.011190 | true → false |
| 40 | 0 | 0.127239 | 0.077281 | 0.075496 | false → false |
| 40 | 1 | 0.246464 | 0.283292 | 0.276439 | false → false |
| 40 | 2 | 0.428549 | 0.468081 | 0.469940 | false → false |
| 160 | 0 | -0.005426 | 0.001885 | 0.001072 | true → false |
| 160 | 1 | -0.005433 | 0.001386 | 0.000656 | true → false |
| 160 | 2 | 0.633435 | 0.645045 | 0.646696 | false → false |

9 局全部 COMPLETED 0:0。接触终点 3/9，松手后 0/9，撤臂后 0/9。它们只覆盖 3 个重复使用的训练态，不能作为独立确认或泛化证据。

已逐帧检查 126 个公开 RGB 视图：接触/松手时主视角旋钮受夹爪或腕部遮挡，腕部视角主要是炉圈、夹爪和灶台侧面；撤臂后主视角 9/9 旋钮无遮挡，腕部 9/9 旋钮已出视野。旋钮角度算法测量仍为 0。黑色炉圈在严格 off=true 与 false 都出现，不能用炉圈颜色阈值准入 stop。

## 下一步方案（尚未实现/运行）

1. **先分清维持控制与自由回弹。** 在这三个既有 train 态上，复用已通过的保存动作前缀，再做固定长度、预先写死的后缀；记录公开动作、末端和机器人关节运动，同时把接触对、关节约束/力只写进执行后私有诊断。比较零动作保持、保持接触的固定公开控制、先解除接触后保持，不能根据私有 qpos 在线挑停点。当前一对等时结果只证明 release 不是唯一因素。
2. **公开时序验证器。** 保存动作前、多块接触中和撤臂后的双视角 RGB-D；用公开标定投影定位旋钮，再跟踪旋钮轮廓/平面/角度变化，联合已公开的动作与末端跟踪误差。若需要机器人关节位置/速度，应显式接入本体感知，不能读家具关节。原版 40/90 的私有真值只作训练标签；确认态排除。先验证完整视频是否有可辨信号，再训练小验证器，不能继续调单帧红色阈值。
3. **停止与稳定分开。** 接触中的公开终点预测可触发“停止继续转动”，随后执行明确的接触保持/释放/撤离序列并做多帧稳定验证；仅瞬时到达终点不能给 verified。公开稳定证据缺失时记 unmeasured，失稳时给可恢复失败。stop 只有在独立确认批上满足既定一致率后才能准入；现阶段仍关闭。

估计：固定 CPU 后缀与接触诊断 1–2 小时；公开旋钮可见性/跨帧跟踪原型 0.5–1 天；小验证器数据、训练与独立确认另需物理采集，当前不承诺已具备 stop。这里不投 GPU、不改现行摩卡确认 source、配方或门槛。
