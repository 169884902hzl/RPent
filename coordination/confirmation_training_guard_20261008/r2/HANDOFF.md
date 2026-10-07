确认状态永久排除规则已落入原版采集入口，提交 `aec5fe4`。请 Codex1 登记以下阈值，并核对历史确认范围；当前 `coverage_complete=false`，未授权新采集。

- 所有登记确认身份、布局参数、随机种子、状态 SHA 和几何指纹永久排除。未执行、失败和落定无效的确认状态同样排除，不按结果筛选。
- 摩卡壶确认种子 `580100–580199`；未来 v6.1 布局训练种子 `680100–689999`，端点均包含。
- 每个训练布局落定后，摩卡壶世界 XY 位置与**每一个**确认布局的欧氏距离须 `≥0.050 m`。检查实际落定位置，不能仅检查参数或不同种子；缺少落定坐标拒绝准入。
- 几何坐标仅用于私有生成和排除审计，不进入模型状态、候选、手册或 memory。

原版入口 `v5_batch_eval.main` 在启动 SAM/π0.5 服务前逐局检查；`OriginalCollection.__init__` 再检查，覆盖直接使用收集器的调用。配置须包含 `confirmation_exclusions.original={path,sha256}`，path 为绝对路径。命中原版确认 tuple 或状态 SHA 即拒绝，更换目标和指令不能绕过。登记范围不完整也拒绝采集。采集 manifest 保存 clearance 和检查源码 SHA。

布局守卫入口为 `robots.libero.v5_confirmation_exclusions.check_registered_training_layout(layout, registry_reference)`。布局生成器尚未正式接入、未开采，不把守卫的 CPU 检查当成物理训练布局准入。

真实登记表：

- 原版 665 distinct identities / 831 登记 rows：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/confirmation_registry_r2/official_confirmation_exclusions.json`，SHA `49273ed0e83a0183393f8771c77131ecf01c4478227878950c637443db035cdf`。r2 增加消费合同需要的 schema，r1 保留；身份不变。
- 摩卡布局全部 100 个（有效 98 / CPU 落定无效 2 均排除）：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill76_CPU_20261008/preparation_r2/confirmation_exclusions100.json`，SHA `885c74af801b30dd7b244e3fb04bdda9f1e0bcb3d9835a2b7ba722cbdb3b65d7`。
- 650 个旧 skill535 身份处于临时训练 hold，协议已将运行称为选择批，未擅自重标成永久确认：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/confirmation_registry_r2/ambiguous_training_hold_identities.json`，SHA `31dc149e325ab3917990ea930181decdb6020dd4879380770813ed5af620910e`。请 Codex1 按协议元数据澄清；不看成绩。

检查：相关 62 项窄测试通过。真实登记表 CPU 检查拒绝 665/665 原版身份、665/665 更换目标尝试、100/100 确认布局种子，以及 100/100 新种子相同 XY 尝试。报告为 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/confirmation_exclusion_checks_CPU_20261008/r2/report.json`，SHA `d26c75577eab6c916a76daa27d58a709131154ec82a0a6b5d8ad78f490007428`。后两类使用合成审计输入，仅检查拒绝逻辑；新增物理请求、训练行均为 0。

当前检查源码 SHA `27070e63b2f88e068fc0779b1382be7dcae8356e9563fa30554fe183d8d90b6c`，CPU 检查脚本 SHA `8826919902858d59f112f51395c0bb394536efabcf0d0bf0f1c6e3ec82894f4a`。登记不完整、技能未全过门槛，未冻结、未启动正式采集。
