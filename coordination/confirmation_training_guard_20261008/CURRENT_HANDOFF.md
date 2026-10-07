# 确认状态永久排除训练：当前交接

用户要求已登记到权威 `/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md`，请 Codex1 登记阈值。尚未收到 Codex1 的登记回执，不写成已经复核。

- 所有确认状态登记即永久排除训练，包括布局参数、随机种子、状态 SHA、几何指纹；成功、失败、未执行和落定无效均保留排除身份。更换指令或目标不能绕过。
- 摩卡壶确认布局种子为 `580100–580199`；未来 v6.1 布局训练种子为 `680100–689999`，端点均包含。
- 每个训练布局**落定后**的摩卡壶世界 XY，与**每一个**确认布局的欧氏距离须 `≥0.050 m`。不同种子或不同参数不能替代位置检查；缺少落定测量不能准入。
- 几何仅作私有排除审计元数据，不进模型状态、候选、训练特征、手册或 memory。主模型、技能验证器、旧行合并、DAgger、图像重放的训练准入都须消费排除登记，保留拒绝计数和原始记录。

当前源码为 `robots/libero/v5_confirmation_exclusions.py`。原版采集入口和收集器构造器都已接线，提交 `aec5fe4`；布局检查函数已经实现，实际布局训练生成器尚未启动或接线，不将 CPU 检查写成物理训练布局准入。

已实核两份不可变登记表：

| 范围 | 远端路径 | SHA256 |
|---|---|---|
| 665 个原版确认身份、831 条登记请求 | `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/confirmation_registry_r2/official_confirmation_exclusions.json` | `49273ed0e83a0183393f8771c77131ecf01c4478227878950c637443db035cdf` |
| 100 个确认布局，含 2 个 CPU 无效布局 | `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill76_CPU_20261008/preparation_r2/confirmation_exclusions100.json` | `885c74af801b30dd7b244e3fb04bdda9f1e0bcb3d9835a2b7ba722cbdb3b65d7` |

既有 CPU 消费检查覆盖 665 个原版身份、665 次更换目标、100 个确认种子和 100 个新种子同位置尝试，均拒绝；相关 62 项窄测试已通过。报告路径和完整合同见 [r2/HANDOFF.md](r2/HANDOFF.md)。本次只核对真实登记表 SHA、永久排除标志和现有接线，没有新增训练行。

旧 skill535 开合 1200 条、放置 400 条已被用户明确改称**选择批**，不再构成待用户批准或待 Codex1 批准的重分类事项；旧临时 hold 文件作为历史记录保留，不能据此重标永久确认。六份显式确认计划的身份并集与 665 身份登记一致，495/497 复用池无新增身份。更完整的登记来源核对见本目录的 `role_resolution_r3/` 交接；不把六份计划当成已证全历史覆盖。

技能门槛仍未全部达到、行为未冻结，正式训练采集尚未启动。
