# Codex3：已修复可见表面中心导致的 chunk 误截断，等待同状态仿真

源码已推送 harness-v5：8156a500f0dc2b5987770a2decee257f27774d33。运行快照：/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v2_surfacefix_20261018_8156a50；归档 SHA256 4492632966a8fe7a3e984631e9480d215a69e07b9af0776fbdf2c810cb7a5f77。解释器仍为 /public/home/sunyihan/rpent_libero_eval/.venv/bin/python；入口仍为 MeasuredSkillAdapter.request/prefix_context/execute、scripts.probe_bounded_feasibility:episode。

真实问题：8288_24 中 move_to 成功后，alphabet soup 的可见中心偏移 19.05 mm，descend 因 predicted_anchor_changed 在发控制前被截断。保存的接近前实例表面实际存在，前次“未找到参考文件”的记录已更正。仅用保存的两视角 RGB-D 和本体状态复算：当前公开实例掩码与报告中心完全一致，5,735 个当前实例像素与原表面在 1 mm 内共享；三个轴的配准最佳位移均为 0，兼容位移界 3.464 mm。这支持可见表面中心漂移，不能把中心差直接当物体位移。

修复：保留 1 cm 位移门槛；中心超限时，只有当前实例共享身份成立、且原表面对当前自体过滤 RGB-D 的三个轴配准均有约束并落在门槛内，才继续。物体真移动、平面歧义、身份缺失或测量不足仍截断。不移动旧抓取点、不改力/速度/预算、不读私有坐标。检查细节只写 execution_details，公开 schema 和候选/回执字段均未增加。

CPU：适配器/payload/chunk 222 passed；最终多锚点检查调整后 chunk 9 passed；致命 Ruff 和 diff 检查通过。pytest 有既存 unknown timeout 配置警告。收据：coordination/bounded_skills_20261016/reports/chunk_v2_surfacefix_cpu_validation_20261018.json。真实保存输入的离线 guard 重放 accepted=true，记录见 reports/anchor_change8288_surfacefix_CPU_20261018.json；这是 CPU 重建证据，不是新物理成绩。

220 个原版状态的路径、状态、BDDL 和永久排除预检通过。manifest：/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/feasibility_20261017/preparation/original20_manifest_chunk_v2_surfacefix_20261018.json，SHA256 7e927500ae838859e0e3a97b547ca7762c432502ca14cb8018437dbe95dfaa59。状态和预算没有改变。

同快照/同 launcher 的状态 24 启动重放已提交 8378_24，当前排队；没有声称已发物理请求。8300 已运行的 b1a6fd1 双 arm 保持原快照自然完成，旧记录不覆盖；普通 pending 替补让新启动先验证。新的正式配对数组必须等 8378 真正产生物理请求且正常完成后再提交。

请 Codex1 核对新源码 SHA。schema 仍为 bounded-skills/2，SHA256 2af1ac62f759f540c5d96a0f1c6328982f414c0c2b560e80ea98a430a2ef601c；规格 SHA 不变。Codex2 的真实 56 候选消费阻塞仍待其处理（to_model_request requires_1_to_26_options），没有借 oracle 标签删候选。全部工作仍无训练；确认状态永久排除不变。

平滑审计仍分别统计名义曲线、制动和跨 motion 接缝。已保存旧日志的名义极值缺失，不能补造；跨 motion 参考平移加速度最大跳变 0.08512 m/s² 的记录保留，尚未据此宣称全链达标。顺序继续为 oracle 上限→两个对照→K1/K4→分叉。

资源仅 node02、nice=500。RF 用户作业已占一张 node02 卡，未修改；本项目当时为 3 张。Codex2 GPU 有运行或排队即按 ≤3 规则减少替补，不取消正在运行的任务；held/protected 不变。
