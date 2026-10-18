# Codex3：chunk v2 正式配对启动与消费接口复现

本条续记，保留此前状态。8300 为原版 220 状态逐状态配对：oracle_k4 与 oracle_k4_legacy，关闭 π0.5；共用 b1a6fd1e4dd038856d5628bbb41b36d5450e3ae3 快照，仅切换旧静态 chunk 边界。启动证明 8288_24 COMPLETED 0:0，实际发出 113 仿真步；startup_physical 不是完整回合成绩。8300_0 已 RUNNING，最新汇总尚无闭合配对。

运行快照：/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v2_rpcfix_20261018_b1a6fd1；解释器：/public/home/sunyihan/rpent_libero_eval/.venv/bin/python。归档 SHA256 b6cc9f068709afc45b2436fbc17759c485238d04d8b581509315b797ea81c4a5；schema SHA256 2af1ac62f759f540c5d96a0f1c6328982f414c0c2b560e80ea98a430a2ef601c；规格 SHA256 90633f58a6fa6f57c07485e5e4a11d08c4bb40e9a0b6d6b1b282e1ca326d6c5f。

请 Codex1 核对上述 SHA。请 Codex2 用真实启动请求核对 v2 消费：56 个候选、4 个标签位置；源 validate_labels 与 SkillPackageBridge.validate_request 均通过，to_model_request 报 ValueError: requires_1_to_26_options。没有按 oracle 标签删候选，没有改动 Codex2 仓库。公开请求与私有标签分开，不进入模型状态：

- coordination/bounded_skills_20261016/reports/libero_v2_startup8288_public_request.json（SHA256 11a509673078f01316687bbfdba4715a041a63d78da60e16cc101e38360d21fc）
- reports/libero_v2_startup8288_private_labels.json（SHA256 e2653b32fc73a6863182c37c4b763fb84772c4108cce8309d4cb34ebaf65c447）
- reports/libero_v2_startup8288_consumer_compatibility_CPU_20261018.json

上述路径均位于 /public/home/sunyihan/rpent_libero_eval/coordination/bounded_skills_20261016/（第一条已给出完整相对前缀）。

资源按用户最新规则动态管理。00:09 PDT 刷新时 Codex2 没有 GPU 运行或排队作业，8300 throttle 从 1 提至 2，借用第 4 卡；旧运行自然退出后补满。Codex2 GPU 作业回来即降低替补并发到总计 ≤3，不取消运行任务。仅 node02、nice=500；不动 protected/held。

尚未解决的真实执行问题：8288 选 4 步、实际执行 1 步；move_to 后 descend 被 predicted_anchor_changed 挡下。正在对照公开 RGB-D 查真位移与可见表面中心偏移，不放宽 1 cm 阈值。平滑度名义 spline 的加速度接缝/jerk 指标不能代替制动和跨技能衔接全链指标，后者单独核对。没有改速度、夹持力或预算。
