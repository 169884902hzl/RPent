# π 整句默认模式：40 局 D2 与原版 6 臂闭合

46 臂全部完成，恢复预算 1，human_available=false，oracle_choices_used=0。每臂完整物理初态 SHA 与纯 π 对照一致。只做评测，不进入训练。

| D2 方法 | 成功 | Wilson 95% |
|---|---:|---:|
| 只用 π，失败重试一次 | 18/40 | 30.7%–60.2% |
| 模型 A，旧合法集 4 | 10/40 | 14.2%–40.2% |
| 模型 B，合法集 5 | 10/40 | 14.2%–40.2% |
| 本次 π 默认模式，合法集 5 | 9/40 | 12.3%–37.5% |
| 开局 oracle 回放 | 24/40 | 44.6%–73.7% |

本次相对纯 π 改善 2 局、退步 11 局、共同成功 7 局；相对模型 B 改善 4 局、退步 5 局；相对旧模型 A 改善 5 局、退步 6 局。逐局见 paired_table.md 和 paired_cases.jsonl。

原版 6 臂为 4/6：碗、盒子各 K1/K4 成功，杯子 K1/K4 均失败。模型 B 为 1/6，纯 π 为 6/6。这是 3 个独立初态各自两种 K，不把 6 臂视为 6 个独立布局。

登记模式使用 next-a 权重（5825fe0f4a29a268483413e6af07fb67be542df6b9477b5e79156749eb4efa26），策略 pi-whole-task-margin/1、enabled=true、delta=2.0；阈值由 Codex2 在训练域固定。它不是 next-b 加一个阈值，未使用 D2 调整阈值。旧模型对照同时有合法集、schema、编码容量和上下文长度变化，差额不能只归因于权重。

D2 单局墙钟中位数 72.90 s，决策数中位数 2.5，仿真步数中位数 292；40 局总墙钟 3939.49 s。29 局以 failed_chunk_recovery_budget 停止，2 局 environment_reports_task_incomplete，9 局 native_success。首个动作：整句调用 5/40、子任务调用 32/40、自有 move_to 3/40。因此本服务是带偏好的模型策略，不是强制每局先调用整句。选择审计保存于 choice_audit.json；它记录请求所选项，后续 chunk 项可能在执行前被截断。

执行源码树：4718f24e61851aacd10ee25a0f9818d550b61a53。服务由 Codex2 管理：11721、18065、capacity=256、context=32768。服务登记 SHA c9ca932547e6e1a82c2b88ae4e62403a2b186ea60dbc8840f0fbdf83e9ee20c1，服务源码 manifest SHA 2b0aad9a6c7636d1c7e327eef985dacd9da81969bd72fc21fc486ddb06e9c435。

已在共享登记和 Codex2 owner_alert 通知 46 臂闭合、无需再保留该服务；未自行取消 Codex2 的作业。原始结果在 /public/home/sunyihan/rpent_libero_eval/results/bounded_skills/next_b_pi_first_20261023/pi_default_*，本目录 manifest 与 JSONL 保留每臂原件路径和 SHA。
