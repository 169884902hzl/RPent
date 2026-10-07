# job4463 微波炉真实启动与双帧采集

物理运行已完成：16 个动作块、80 个请求与实际执行 controls（setup 8 块 + 首次 open 8 块）。单局 ledger status=first_attempt_recorded，infrastructure_failure=false。18 帧组成 9 个双帧记录（before 一组，after 八组）；不是技能确认批。

Slurm FAILED 1 的原文为 `startup_error: no requested physical controls`。launcher 从 `first_attempt.server_chunk_execution` 读控制步数，但 producer 写在 row 顶层，造成启动检查误报。原始物理记录保留，不把这次数据计作零物理。

本例 setup close 没把门关上；私有 open 谓词在 first open 前后均为 true，关节角均 -1.501553。公开 receipt 的 verified + no_effect 不能证明成功完成一次开门。私有关节/谓词仅作诊断标签，不进入运行时状态或候选。

显式 ledger、计划、slurm 日志与源码身份均在 report.json / manifest.json 固定，不扫描 artifacts。门平面质量、停止行为和完整预算的技能成功率仍需另行物理验证。
