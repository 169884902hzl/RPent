# 10/18：搬运后的公开持物身份关联

1. 9515_2 的 `public_hold_lost` 是公开身份关联错误；零动作恢复显示盒子仍离地且保持双指接触。
2. 关联改为用 pre-lift RGB-D 经公开 EEF 运动变换后的表面位置排名；发布的坐标仍必须来自当前分割实例，缺测时不填预测位置。
3. 保存掩码重放已纠正同一时刻 e12/e11 的错配；这不是完整 SAM 重放或修复后物理成功证据。
4. CPU：469 项通过、1 项因同进程 MuJoCo 导入顺序失败；该项在干净进程原样通过。首次失败日志完整保留。
5. Codex3 接着做同快照、同 launcher 启动和 init2 完整开发复测；Codex1/Codex2 核对关联来源说明。无训练、确认批重判或冻结。

## 根因与边界

9515_2 原结果 false，7 决策、361 tick、369.014 秒。决策 row2 以后，私有零动作恢复显示物体约离支撑面 24.5 cm，双指接触持续成立，最大仿真恢复残差为 0。真值仅用于诊断，未作为执行器或模型输入。原始失败保留。

旧 `MeasuredScene.refresh()` 以旧静态位置贪心匹配当前同名实例。搬运后，地面 cream-cheese 误检先占据 held ID e12；当前帧真正被夹住的盒子获得 e11。公开持物校验因而对错误实例执行，返回 `public_hold_lost`。

`MeasuredSkillAdapter.refresh()` 只把参考 RGB-D 表面通过参考/当前公开 EEF 位姿变换，传入 `association_positions`。`MeasuredScene.refresh()` 仅在距离排名时使用它；当前位姿、边界和点云仍取自本帧。没有当前实例时维持 cached/invisible。证据字段明确 `prediction_is_measurement=false`。不改变持物阈值、静态背景否决、payload 碰撞、力、速度或预算。

保存 final masks 的重放对照：旧 e12 在地面约 [0.160,0.025,0.018] m，新 e12 匹配本帧真实盒子约 [0.021,0.237,0.263] m；预测关联中心约 [0.016,0.252,0.264] m，没有代替发布测量。此重放不执行控制、不调用 SAM RPC、不使用私有坐标。

## 检查与后续物理复测

- `reports/box9515_transport_private_CPU_20261018.json`：恢复、接触和源码/输入 SHA。
- `reports/box9515_association_saved_masks_CPU_20261018.json`：公开保存掩码的逐实例对照及输入 SHA。
- `reports/transport_identity_validation_summary_20261018.json`：实际命令、469+1 的分进程结果、源码 SHA 及压缩原始日志。

首次聚合命令退出 1 的日志不覆盖；`test_v5_chunk_stops_before_actions_after_native_termination` 在全套里因先前导入 MuJoCo 触发启动断言，在独立进程退出 0。没有为使检查通过而修改运行时断言或测试判据。

同轮辅助修复：prepare 在创建快照前检查 CPU receipt 的绝对路径、存在性及 JSON；监控只延后 peer 数组的待排替补，给真实 startup 留下一空位；微波炉诊断使用逐 job 新输出并拒绝覆盖原报告。schema 保持 bounded-skills/3 与 public-request-legal/2。

待完成：修复后的 init2 物理终态、真实盒子其余原版状态、盘子 9534 两状态和微波炉 9513_140。不得用本次 CPU 结果代替这些物理结果。
