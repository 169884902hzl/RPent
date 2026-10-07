只读诊断：old24 为 18 true / 5 false / 1 unknown；加 4528 首局为 19/25。五个最终 false 的 raw_native_success_controls 都是 0；一度 native 成功但最终 false 为 0/25。因此现有批次没有“成功后继续动作导致最终失败”的证据，不能用它解释这五个失败。

源码合同差异确实存在：source582r2 的 probe_v5_moka_transfer_public_20261007.py:212–215 用 complete_skill 将 native 终止保留为诊断 latch；v5_env_client.py:29–30 在 skill 内对 terminated 返回 false；serve_v5_moka_transfer_registered_20261007.py:68–69 使用 complete_probe_chunk；probe_v5_skill501_original.py:251–278 每块执行五控，只在外部 trunc 停止、native 成功仅计数。

这个固定块约定来自逆目标单技能诊断。对于 task19 同目标完整 transfer，没有反转原任务目标所需的隔离理由。不过当前确认 source、分母、结果均不改；任何 native-stop 开发只可用既有选择态另测。现有聚合计数也不能提供逐步首次成功位置，不能推断改停止合同后的反事实成绩。

输入只由用户/主代理提供的 registry 显式列举，读取完成的 4499_0、4502_0–7、4528_0；未读正在变化的 4531 ledgers。报告/逐局诊断只作执行后分析，绝不进训练或运行时条件。
