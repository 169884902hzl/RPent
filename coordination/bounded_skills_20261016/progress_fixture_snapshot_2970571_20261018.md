# Codex3：静态家具快照与 node02 运行回执

本轮源码：`2970571a7f860613d8085622530e3514881e7cb7`，已推送 `user-fork/harness-v5`。仅原版场景开发、CPU 检查和仿真；未训练。

## 已修复并验证

`v5_branch_state.actuator_state()` 原先没有保存静态家具的 `model.body_pos/body_quat`。LIBERO `bddl_base_domain.py:776–779` 在 reset 中直接修改这些字段，它们不在 qpos 中。现在快照保存并恢复它们；旧快照缺少这两项的事实保留，不能据机器人传感器重放吻合宣称家具也吻合。

`probe_bounded_feasibility.episode()` 在执行前保存 `private_decision_snapshots/NNN.pkl`，包括动态物理状态、静态家具变换、执行器、控制器、RNG 和计数器。引用与 SHA 只在 choices 记录的外层 `private_pre_execution_snapshot`，不进入 public request 或 decision service。schema/模型接口没有变更。

CPU：17 项针对测试通过；scoped Ruff（忽略已有 CPY001）和 diff check 通过。真实 MuJoCo、无 renderer、CUDA_VISIBLE_DEVICES 为空的回归：静态微波炉平移 2cm/−1cm 时 qpos 不变，恢复后位置误差0m、四元数误差0。报告：`reports/fixture_branch_snapshot_CPU_20261018.json`。这项检查验证快照恢复，不是任务成功率，也没有确认微波炉旧记录的阻挡身份。

快照：`/public/home/sunyihan/rpent_libero_eval/source_bounded_2970571_20261017`；archive SHA256 `b04f79fff221bd4c356b650575400008c7c84bce905d3fcb0a5e811f2d67803e`。入口仍是 `scripts.probe_bounded_feasibility:episode`；解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

共享规格 SHA256 `d8478e7d29da148e9bcbc373575c080e93a57014c5cc36df84bf378829d18b8a`；schema SHA256 `0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5`。

## 新完整物理结果

全部关闭 π0.5、使用 `rgbd_dual_view/1`，仅原版开发局。

| Job / source | 类别/初态 | 官方任务结果 | 决策 | 仿真步 | 墙钟秒 |
|---|---|---:|---:|---:|---:|
|8025_100 / ca4ce83|drawer open init0|1/1|10|586|937.0|
|8025_101 / ca4ce83|drawer open init1|1/1|11|792|977.7|
|8028_60 / 78c7c46|two-cup transfer init0|0/1|19|1879|1390.3|

同源码抽屉2/2，Wilson95%为34.2–100%。双杯0/1，Wilson95%为0–79.3%；第一只杯子已转移，第二只已抬起并搬运，但随后 `measured_payload_collision` 导致 lower/scan 被拦，最终没有剩余可行公开动作。逐次数据完整保留。尚未取得当前源码每类20局，不能扩到100或宣布可行性通过。

## 资源和后续

最新截图/JSON：`reports/resource_latest_node02_cap3_20261018.{png,json}`。仅node02，三条通道各 `%1`；node01无本轮新作业。8032灶台启动检查接替已完成8028；8031盘子接触回执启动检查依赖8030；新8034微波炉启动检查依赖8025。依赖保证三通道总运行数不超过3。全部Nice500，不触碰c5/c6/rf或旧held作业。

顺序保持：先各类无π0.5 oracle上限，随后两对照、任务K1/K4、分叉。新源码必须同快照/launcher实际启动产生控制，再提交完整局。当前仍在开发；已关闭确认批不改判、状态永久排除训练。
