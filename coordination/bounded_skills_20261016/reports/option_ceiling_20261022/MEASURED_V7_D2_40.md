恢复预算 1 档的 40 局采样与独立整局回放全部闭合；原生整局成功 24/40，Wilson 95% 44.6–73.7%。
实测采样包络 30/38，另 2 局私有规则未覆盖；已知分母的 Wilson 95% 63.7–88.9%。
前版回放 23/40、模型 10/40、A1-M 28/40；新旧回放结果翻转为 2 好 1 坏，完整初态 0 相同、38 不同、2 缺失，差额不作纯选项收益或选择错误归因。
覆盖规则的子任务中双方全部失败 10 处，未知 1 处；未覆盖规则的 2 局单列。
本批只评测；新增公开锚点调用、额外采样及私有目标续接同时变化。未用 D2 调阈值，也未训练模型。

| 整局臂 | 成功 | Wilson 95% |
|---|---:|---:|
| 新 v7 独立回放 | 24/40 | 44.6–73.7% |
| 前版独立回放 | 23/40 | 42.2–71.5% |
| 旧 schema6 模型 HTTP 闭环 | 10/40 | 14.2–40.2% |
| A1-M | 28/40 | 54.6–81.9% |

采样包络按已测分支逐子任务择优，受先前选中路径限制；它不是部署策略的整局期望成功率，也不是穷举全部后继状态的数学上界。私有目标进展不进入公开请求或模型状态。未覆盖规则的整句 fallback 可有实际整局回放结果，但不能据此认证它的子任务采样上限。

本批采样成功而独立回放失败 7 局：libero_10_task_t2_s40, libero_goal_swap_t2_s40, libero_goal_task_t2_s40, libero_goal_task_t3_s40, libero_object_swap_t4_s40, libero_spatial_swap_t4_s40, libero_spatial_task_t4_s40。新批与历史十五条差异分开保留，不覆盖旧分数。

回放成功而采样包络为 False 的 1 局：libero_10_swap_t0_s40。这也说明这里的采样包络并非数学上的整局上界。

| 套件 | 原生回放 | Wilson 95% | 采样包络 | Wilson 95% | A1-M |
|---|---:|---:|---:|---:|---:|
| libero_10_swap | 3/5 | 23.1–88.2% | 2/4 + 1 unknown | 15.0–85.0% | 3/5 |
| libero_10_task | 3/5 | 23.1–88.2% | 4/4 + 1 unknown | 51.0–100.0% | 3/5 |
| libero_goal_swap | 2/5 | 11.8–76.9% | 3/5 + 0 unknown | 23.1–88.2% | 3/5 |
| libero_goal_task | 2/5 | 11.8–76.9% | 4/5 + 0 unknown | 37.6–96.4% | 4/5 |
| libero_object_swap | 4/5 | 37.6–96.4% | 5/5 + 0 unknown | 56.6–100.0% | 4/5 |
| libero_object_task | 4/5 | 37.6–96.4% | 4/5 + 0 unknown | 37.6–96.4% | 3/5 |
| libero_spatial_swap | 4/5 | 37.6–96.4% | 5/5 + 0 unknown | 56.6–100.0% | 4/5 |
| libero_spatial_task | 2/5 | 11.8–76.9% | 3/5 + 0 unknown | 23.1–88.2% | 4/5 |

下面按子任务类型汇总：进展是登记目标或局部子任务的私有诊断判据；local 和 native 另列。这里 native 是分支端点的环境终止信号，不是该方法从初态独立完成整局的成功率。重复试次及连续子任务不视为独立布局。

| 子任务 | 方法 | 私有进展 | Wilson 95% | local | native |
|---|---|---:|---:|---:|---:|
| in | full_task | 25/36 | 53.1–82.0% | 25/36 (53.1–82.0%) | 25/36 (53.1–82.0%) |
| in | in_place | 27/36 | 58.9–86.2% | 27/36 (58.9–86.2%) | 24/36 (50.3–79.8%) |
| in | initial_pose | 20/36 | 39.6–70.5% | 20/36 (39.6–70.5%) | 17/36 (32.0–63.0%) |
| in | measured_anchor | 27/36 | 58.9–86.2% | 27/36 (58.9–86.2%) | 24/36 (50.3–79.8%) |
| in | self | 7/12 | 32.0–80.7% | 7/12 (32.0–80.7%) | 6/12 (25.4–74.6%) |
| on | full_task | 33/48 | 54.7–80.1% | 31/48 (50.4–76.6%) | 31/48 (50.4–76.6%) |
| on | in_place | 32/48 | 52.5–78.3% | 32/48 (52.5–78.3%) | 30/48 (48.4–74.8%) |
| on | initial_pose | 32/48 | 52.5–78.3% | 32/48 (52.5–78.3%) | 29/48 (46.3–73.0%) |
| on | measured_anchor | 29/48 | 46.3–73.0% | 29/48 (46.3–73.0%) | 23/48 (34.5–61.7%) |
| on | self | 10/16 | 38.6–81.5% | 10/16 (38.6–81.5%) | 8/16 (28.0–72.0%) |
| open | full_task | 0/6 | 0.0–39.0% | 0/6 (0.0–39.0%) | 0/6 (0.0–39.0%) |
| open | in_place | 0/6 | 0.0–39.0% | 0/6 (0.0–39.0%) | 0/6 (0.0–39.0%) |
| open | initial_pose | 0/6 | 0.0–39.0% | 0/6 (0.0–39.0%) | 0/6 (0.0–39.0%) |
| open | measured_anchor | 0/6 | 0.0–39.0% | 0/6 (0.0–39.0%) | 0/6 (0.0–39.0%) |
| open | self | 0/2 | 0.0–65.8% | 0/2 (0.0–65.8%) | 0/2 (0.0–65.8%) |
| pick | full_task | 61/120 | 42.0–59.6% | 57/120 (38.8–56.4%) | 57/120 (38.8–56.4%) |
| pick | in_place | 56/120 | 38.0–55.6% | 51/117 + 3 unknown (34.9–52.6%) | 12/120 (5.8–16.7%) |
| pick | initial_pose | 48/117 + 3 unknown | 32.5–50.1% | 48/117 + 3 unknown (32.5–50.1%) | 4/120 (1.3–8.3%) |
| pick | measured_anchor | 59/117 + 3 unknown | 41.5–59.3% | 53/117 + 3 unknown (36.6–54.3%) | 12/120 (5.8–16.7%) |
| pick | self | 13/39 + 1 unknown | 20.6–49.0% | 13/39 + 1 unknown (20.6–49.0%) | 0/40 (0.0–8.8%) |
| turn_on | full_task | 6/6 | 61.0–100.0% | 2/6 (9.7–70.0%) | 2/6 (9.7–70.0%) |
| turn_on | in_place | 6/6 | 61.0–100.0% | 6/6 (61.0–100.0%) | 0/6 (0.0–39.0%) |
| turn_on | initial_pose | 6/6 | 61.0–100.0% | 6/6 (61.0–100.0%) | 0/6 (0.0–39.0%) |
| turn_on | measured_anchor | 0/6 | 0.0–39.0% | 0/6 (0.0–39.0%) | 0/6 (0.0–39.0%) |
| turn_on | self | 0/2 | 0.0–65.8% | 0/2 (0.0–65.8%) | 0/2 (0.0–65.8%) |

[按套件 × 子任务 × 方法的三种判据统计及 Wilson 区间](measured_v7_D2_rates_expanded.json)保留全部分类。每个已覆盖子任务的逐方法进展次数如下；π 每变体三次，自有技能一次。各次种子、local/native、仿真步数、真实调用参数及原件引用见 [逐子任务记录](measured_v7_D2_subtasks.jsonl)。

逐子任务 Wilson 95% 对照：0/3=0.0–56.1%，1/3=6.1–79.2%，2/3=20.8–93.9%，3/3=43.9–100.0%；0/1=0.0–79.3%，1/1=20.7–100.0%。

| 局 / 子任务 | self | in_place | initial_pose | full_task | measured_anchor |
|---|---:|---:|---:|---:|---:|
| libero_10_swap_t0_s40 / g0:pick | 0/1 | 0/3 | 0/3 | 0/3 | 1/3 |
| libero_10_swap_t0_s40 / g0:in | 0/1 | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_10_swap_t1_s40 / g0:pick | 0/1 | 1/3 | 0/3 | 3/3 | 3/3 |
| libero_10_swap_t1_s40 / g1:pick | 0/0 + 1 unknown | 3/3 | 0/0 + 3 unknown | 3/3 | 0/0 + 3 unknown |
| libero_10_swap_t2_s40 / g0:turn_on | 0/1 | 3/3 | 3/3 | 3/3 | 0/3 |
| libero_10_swap_t2_s40 / g1:pick | 0/1 | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_10_swap_t4_s40 / g0:pick | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_10_swap_t4_s40 / g0:on | 1/1 | 2/3 | 0/3 | 2/3 | 3/3 |
| libero_10_swap_t4_s40 / g1:pick | 1/1 | 1/3 | 1/3 | 0/3 | 3/3 |
| libero_10_swap_t4_s40 / g1:on | 1/1 | 3/3 | 3/3 | 3/3 | 0/3 |
| libero_10_task_t0_s40 / g0:pick | 0/1 | 3/3 | 3/3 | 0/3 | 0/3 |
| libero_10_task_t0_s40 / g0:in | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_10_task_t0_s40 / g1:pick | 0/1 | 3/3 | 3/3 | 3/3 | 2/3 |
| libero_10_task_t0_s40 / g1:in | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_10_task_t1_s40 / g0:pick | 0/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_10_task_t2_s40 / g0:turn_on | 0/1 | 3/3 | 3/3 | 3/3 | 0/3 |
| libero_10_task_t2_s40 / g1:pick | 0/1 | 3/3 | 0/3 | 2/3 | 1/3 |
| libero_10_task_t2_s40 / g1:on | 0/1 | 3/3 | 0/3 | 3/3 | 3/3 |
| libero_10_task_t4_s40 / g0:pick | 1/1 | 3/3 | 3/3 | 0/3 | 2/3 |
| libero_10_task_t4_s40 / g0:on | 1/1 | 0/3 | 3/3 | 0/3 | 3/3 |
| libero_10_task_t4_s40 / g1:pick | 1/1 | 0/3 | 0/3 | 0/3 | 3/3 |
| libero_10_task_t4_s40 / g1:on | 0/1 | 0/3 | 3/3 | 0/3 | 0/3 |
| libero_goal_swap_t0_s40 / g0:open | 0/1 | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_goal_swap_t1_s40 / g0:pick | 1/1 | 2/3 | 0/3 | 3/3 | 0/3 |
| libero_goal_swap_t1_s40 / g0:on | 0/1 | 2/3 | 2/3 | 3/3 | 0/3 |
| libero_goal_swap_t2_s40 / g0:pick | 0/1 | 1/3 | 0/3 | 0/3 | 0/3 |
| libero_goal_swap_t2_s40 / g0:on | 1/1 | 0/3 | 0/3 | 0/3 | 3/3 |
| libero_goal_swap_t3_s40 / g0:pick | 1/1 | 2/3 | 1/3 | 3/3 | 0/3 |
| libero_goal_swap_t3_s40 / g0:in | 0/1 | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_goal_swap_t4_s40 / g0:pick | 0/1 | 1/3 | 1/3 | 0/3 | 0/3 |
| libero_goal_swap_t4_s40 / g0:on | 0/1 | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_goal_task_t0_s40 / g0:open | 0/1 | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_goal_task_t1_s40 / g0:pick | 0/1 | 0/3 | 0/3 | 3/3 | 0/3 |
| libero_goal_task_t2_s40 / g0:pick | 0/1 | 2/3 | 2/3 | 1/3 | 2/3 |
| libero_goal_task_t2_s40 / g0:on | 1/1 | 3/3 | 0/3 | 3/3 | 0/3 |
| libero_goal_task_t3_s40 / g0:pick | 0/1 | 3/3 | 3/3 | 1/3 | 2/3 |
| libero_goal_task_t3_s40 / g0:in | 0/1 | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_goal_task_t4_s40 / g0:pick | 0/1 | 0/3 | 0/3 | 3/3 | 0/3 |
| libero_object_swap_t0_s40 / g0:pick | 0/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_object_swap_t0_s40 / g0:in | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_object_swap_t1_s40 / g0:pick | 0/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_object_swap_t1_s40 / g0:in | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_object_swap_t2_s40 / g0:pick | 1/1 | 1/3 | 3/3 | 2/3 | 3/3 |
| libero_object_swap_t2_s40 / g0:in | 1/1 | 3/3 | 2/3 | 3/3 | 3/3 |
| libero_object_swap_t3_s40 / g0:pick | 0/1 | 0/3 | 0/3 | 0/3 | 3/3 |
| libero_object_swap_t3_s40 / g0:in | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_object_swap_t4_s40 / g0:pick | 0/1 | 0/3 | 1/3 | 0/3 | 0/3 |
| libero_object_swap_t4_s40 / g0:in | 0/1 | 3/3 | 0/3 | 1/3 | 3/3 |
| libero_object_task_t0_s40 / g0:pick | 0/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_object_task_t0_s40 / g0:in | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_object_task_t1_s40 / g0:pick | 0/1 | 1/3 | 1/3 | 3/3 | 3/3 |
| libero_object_task_t2_s40 / g0:pick | 0/1 | 1/3 | 2/3 | 0/3 | 2/3 |
| libero_object_task_t2_s40 / g0:in | 0/1 | 3/3 | 0/3 | 3/3 | 3/3 |
| libero_object_task_t3_s40 / g0:pick | 0/1 | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_object_task_t4_s40 / g0:pick | 0/1 | 3/3 | 2/3 | 2/3 | 3/3 |
| libero_spatial_swap_t0_s40 / g0:pick | 1/1 | 3/3 | 3/3 | 3/3 | 2/3 |
| libero_spatial_swap_t0_s40 / g0:on | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_spatial_swap_t1_s40 / g0:pick | 1/1 | 0/3 | 0/3 | 3/3 | 3/3 |
| libero_spatial_swap_t1_s40 / g0:on | 0/1 | 3/3 | 3/3 | 1/3 | 0/3 |
| libero_spatial_swap_t2_s40 / g0:pick | 1/1 | 2/3 | 3/3 | 3/3 | 1/3 |
| libero_spatial_swap_t2_s40 / g0:on | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_spatial_swap_t3_s40 / g0:pick | 1/1 | 0/3 | 0/3 | 0/3 | 2/3 |
| libero_spatial_swap_t3_s40 / g0:on | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_spatial_swap_t4_s40 / g0:pick | 0/1 | 0/3 | 0/3 | 2/3 | 0/3 |
| libero_spatial_task_t0_s40 / g0:pick | 0/1 | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_spatial_task_t1_s40 / g0:pick | 1/1 | 0/3 | 0/3 | 3/3 | 1/3 |
| libero_spatial_task_t1_s40 / g0:on | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_spatial_task_t2_s40 / g0:pick | 1/1 | 2/3 | 1/3 | 0/3 | 1/3 |
| libero_spatial_task_t2_s40 / g0:on | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_spatial_task_t3_s40 / g0:pick | 0/1 | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_spatial_task_t4_s40 / g0:pick | 0/1 | 0/3 | 0/3 | 0/3 | 1/3 |
| libero_spatial_task_t4_s40 / g0:on | 0/1 | 1/3 | 3/3 | 3/3 | 2/3 |

| 双方均失败的子任务 | 记录的停止原因（次数） |
|---|---|
| libero_10_swap_t0_s40 / g0:in | failed_chunk_recovery_budget: 13 |
| libero_10_swap_t2_s40 / g1:pick | failed_chunk_recovery_budget: 9, preparation_not_reached: 3, public_terminal_selection: 1 |
| libero_goal_swap_t0_s40 / g0:open | failed_chunk_recovery_budget: 9, preparation_not_reached: 3, public_terminal_selection: 1 |
| libero_goal_swap_t3_s40 / g0:in | failed_chunk_recovery_budget: 12, public_terminal_selection: 1 |
| libero_goal_swap_t4_s40 / g0:on | failed_chunk_recovery_budget: 13 |
| libero_goal_task_t0_s40 / g0:open | failed_chunk_recovery_budget: 9, preparation_not_reached: 3, public_terminal_selection: 1 |
| libero_goal_task_t3_s40 / g0:in | failed_chunk_recovery_budget: 13 |
| libero_object_task_t3_s40 / g0:pick | failed_chunk_recovery_budget: 12, source_binding_missing: 1 |
| libero_spatial_task_t0_s40 / g0:pick | measured_success_after_handoff: 6, failed_chunk_recovery_budget: 4, preparation_not_reached: 2, subtask_completed: 1 |
| libero_spatial_task_t3_s40 / g0:pick | failed_chunk_recovery_budget: 12, preparation_not_reached: 1 |

下面继续展开实际内部失败回执，而非只使用外层恢复预算标签；计数包含该分支内各次失败尝试，不能直接当作唯一物理根因。完整逐次证据见 [130分支回执](measured_v7_D2_receipt_audit_both_failed_receipts.jsonl)。

| 局 / 子任务 | 自有技能内部失败 | π分支内部失败 |
|---|---|---|
| libero_10_swap_t0_s40 / g0:in | move_to:predicted_anchor_changed: 1, observe:measured_sweep_collision: 1 | call_vla:block_budget: 17, call_vla:preparation_not_reached: 6, call_vla:no_progress_blocks: 1 |
| libero_10_swap_t2_s40 / g1:pick | move_to:measured_sweep_collision: 5, ask_help:no_human_available_use_observe_restage_or_other_approach: 1, observe:measured_sweep_collision: 1 | call_vla:block_budget: 10, call_vla:preparation_not_reached: 9, call_vla:no_progress_blocks: 2 |
| libero_goal_swap_t0_s40 / g0:open | move_to:measured_sweep_collision: 5, ask_help:no_human_available_use_observe_restage_or_other_approach: 1 | call_vla:block_budget: 16, call_vla:preparation_not_reached: 3, call_vla:no_progress_blocks: 2 |
| libero_goal_swap_t3_s40 / g0:in | ask_help:no_human_available_use_observe_restage_or_other_approach: 1, lower:measured_sweep_collision: 1, observe:measured_sweep_collision: 1 | call_vla:block_budget: 19, call_vla:preparation_not_reached: 3, call_vla:no_progress_blocks: 2 |
| libero_goal_swap_t4_s40 / g0:on | observe:measured_sweep_collision: 2 | call_vla:block_budget: 18, call_vla:preparation_not_reached: 6 |
| libero_goal_task_t0_s40 / g0:open | move_to:measured_sweep_collision: 5, ask_help:no_human_available_use_observe_restage_or_other_approach: 1 | call_vla:block_budget: 12, call_vla:preparation_not_reached: 5, call_vla:no_progress_blocks: 1 |
| libero_goal_task_t3_s40 / g0:in | 无失败回执（见外层停止原因及公开/私有判据） | call_vla:block_budget: 18, call_vla:preparation_not_reached: 4, call_vla:no_progress_blocks: 2 |
| libero_object_task_t3_s40 / g0:pick | 无失败回执（见外层停止原因及公开/私有判据） | call_vla:block_budget: 18, call_vla:preparation_not_reached: 3, call_vla:no_progress_blocks: 3 |
| libero_spatial_task_t0_s40 / g0:pick | 无失败回执（见外层停止原因及公开/私有判据） | call_vla:block_budget: 5, call_vla:completion_lost_during_handoff: 4, call_vla:preparation_not_reached: 3 |
| libero_spatial_task_t3_s40 / g0:pick | descend:tracking_error: 2, descend:measured_sweep_collision: 1 | call_vla:block_budget: 18, call_vla:preparation_not_reached: 2, call_vla:completion_lost_during_handoff: 2, call_vla:no_progress_blocks: 1 |

[本批7局回放差异的逐段回执](measured_v7_D2_receipt_audit_replay_gap_receipts.jsonl)保留实际调用参数、种子、源/目标ID、各段local/private/native结果和停止原因；只读提取，不重判。[提取manifest](measured_v7_D2_receipt_audit_manifest.json)保存SHA。

上述覆盖规则的 72 个子任务共 936 个分支；不含两处未覆盖规则的整句fallback调用。

| 请求变体 | 分支数 | 实际进入π推理 | 未进入推理 |
|---|---:|---:|---:|
| in_place | 216 | 216 | 0 |
| initial_pose | 216 | 192 | 24 |
| full_task | 216 | 216 | 0 |
| measured_anchor | 216 | 177 | 39 |

筛查拒绝不能自动称作真实碰撞或误杀；数值 IK 未找到解不能证明几何不可达；交还标签不能单独证明物体滑落。所有失败保留，未重跑闭合回合换分数。

未覆盖规则的局：libero_10_swap_t3_s40, libero_10_task_t3_s40。具体规则见 [未覆盖清单](measured_v7_D2_unsupported_cases.jsonl)。

[40 局逐对表](measured_v7_D2_comparison.md)保留与前版、模型及 A1 的逐局对照；[原始对照 JSONL](measured_v7_D2_comparison.jsonl)含每条 summary 的路径与 SHA。完整 A1 积分/控制器/RNG 初态仍缺，不把 EEF 相同视为完整初态相同。

执行 Git tree `2db200134ea6689e36a66e8aee6f45daa8270b4e`；归档 SHA256 `7a08e6f42ad4b452d68f3b463cde883c2e0aeb20fe8ba9340ce2791d511ebcb2`；schema7 SHA256 `546299a6f4d956ddc6a249edc5e64bb532a135e1199e345b222c687611b72182`；contract SHA256 `a0fef7407efb67b4f9cde557cfa09ffcf3964eaaf9eaabad9f671d4e5b900f0b`。这些是实际执行快照，报告交付的 Git commit 另记。

[登记 manifest](measured_v7_D2_manifest.json)、[完整分类与调用统计](measured_v7_D2_delivery_summary.json)、[逐次子任务](measured_v7_D2_subtasks.jsonl)、[双方均失败](measured_v7_D2_both_failed_subtasks.jsonl)均保留原件引用。公开执行与 efa 快照逐 blob 相同，仅私有阶段续接不同；N1/N2/155 回归见本目录对应报告。PRO、D2、确认状态不进训练。
