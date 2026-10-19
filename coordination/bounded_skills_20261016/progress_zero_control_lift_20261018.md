# 盒子 init4：零动作守卫不等于接触失败

1. 9515_4 的开夹爪恢复源于 oracle 错误归类；lift 因 `predicted_anchor_changed` 在 0 tick 时截断，尚未检验接触。
2. 保留 1 cm 锚点守卫和新请求的完整几何筛选，仅让这一零动作回执不触发“已尝试 lift 失败”的张开恢复。
3. CPU 原请求对照从 `set_gripper(open)` 改为重新测量的 `lift(e39)`，legal/acceptable 为 20/1。
4. 38 项 chunk / 离线前缀回归通过；仿真复验尚未完成，不作成功结论。
5. 私有 judge 升为 `/11`，公共 schema/legal 不变；Codex2 应按保存源码区分标签版本，Codex3 接着做同状态完整复验。

旧源 ee42501 / 9515_4：false，8 决策、245 tick、403.435 秒。row0 抓紧后公开表面轻微变化，lift 在控制前被锚点守卫拦截；row1 的 lift 已重新筛选为 collision=false、IK=true，但旧 oracle 见最近 lift 非 success 就选张开。这里不需要放宽守卫、力或预算。

`robots/libero/bounded_oracle.py` 只排除 `steps_used=0` 且 `stop_reason=predicted_anchor_changed` 的这一误归类。已实际执行的 lift、碰撞拒绝和持物丢失仍走原恢复。回归分别覆盖这四种情况，另有原有 blocked-lift / prefix / 离线标签检查。

原请求 CPU 诊断 `reports/box9515_guard_lift_CPU_20261018.json` 无仿真步进、GPU 或 RPC，基于 hash 匹配的私有保存上下文；选项坐标和后果仍来自公开请求。新脚本 `scripts/box9515_production_judge_CPU_20261018.py` 可在部署快照上再次核对生产实现，没有临时替换函数。

检查命令、源码 SHA 和原始压缩日志在 `reports/zero_control_lift_cpu_20261018.json`。首次新测试因构造的简化回执不满足请求 schema 失败，随后将该回执仅注入待测 oracle；另一次八项失败是已升级 judge 后测试仍断言 `/10`，已更新为 `/11`，最终 38 项通过。没有改执行判据以通过检查。
