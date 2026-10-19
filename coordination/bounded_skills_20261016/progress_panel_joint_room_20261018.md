# 竖直表面接触余量修复：部署回执

1. 10:05 五项已有直接答案：profile、碗 init2 修复、CPU 任意前缀标签、候选顺序无语义、最近三条详细回执；完整证据仍在 `progress_prefix_judge9_and_door_identity_20261018.md`。
2. 新源码 `184ba1d7eddf7f703f1e6efe79acc1dbf068b4cd` 已推送 harness-v5；267 项 CPU 回归通过，220 个登记状态的 CPU 路径/初态预检通过。
3. 同快照、同 launcher 的微波炉启动 9599_120 已 COMPLETED 0:0，实际执行 490 tick；正式开/关两局已提交为 9600，尚无新源码完整任务成功结论。
4. 4db4ea4 盒子批 9579 的首三局均原生成功：init0 / 1 / 2 为 2 / 4 / 4 次决策，408 / 442 / 434 tick；其余未完成，不作类别通过。
5. Codex3 继续物理复验与分阶段诊断，Codex1 核源文件和分母，Codex2 按保存上下文和匹配 judge 版本使用标签接口。未训练、未冻结，确认排除继续有效。

## 源码与机器合同

| 项 | 确切值 |
| --- | --- |
| 快照 | `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_panel_joint_room_20261018_184ba1d7` |
| commit | `184ba1d7eddf7f703f1e6efe79acc1dbf068b4cd` |
| 归档 SHA256 | `3a7b24e7571d1dff9549d4df68875853db452e8e9a9c9a051bc9da1284fe1f1e` |
| 入口 | `scripts.probe_bounded_feasibility:episode` |
| 解释器 | `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python` |
| schema / legal / judge | `bounded-skills/3` / `public-request-legal/2` / `libero-private-task-progress-rules/12`，均无变更 |
| schema SHA256 | `df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa` |
| manifest | `results/bounded_skills/feasibility_20261017/preparation/original20_manifest_chunk_v3_panel_joint_room_20261018.json` |
| manifest SHA256 | `3507b5bafc30f276bee87206811ae698ee6eb7dd27c060b4a8655d61b11f1027` |

只改非水平表面既有可行接触路线的选择。终点关节余量优先，再用路线最小余量打破平局；不改变阈值和公共字段，水平表面逻辑不变。CPU 假设与旧完整失败详见 `progress_late_microwave_20261018.md`。

9599_120 只作启动证据：一组决策执行 move_to 437、descend 38、set_gripper 15 tick；后续 nudge 因 `predicted_anchor_changed` 零 tick 截断。墙钟 146.648 秒，`status=startup_physical`，不是完整任务结果。正式 9600_120 / 140 使用相同快照和原登记状态；启动不并入成功率分母。

本轮已交 Codex1/Codex2：共享 COORDINATION 追加偏移 `6902032420–6902037200`，4780 字节，SHA256 `a8b24d9d8ec021f4be0a3db07c8da9875afc128bbe20d05c4ff9b174bc9ec300`。回执为 `reports/coord_panel_joint_room_append_20261018.json`。

## 仍开放的具体问题

盘子 9576_160 / 161 的中间私有诊断，分别捕获 11 / 9 个保存状态，恢复残差均小于 1e-8。初次接触后的前几次 nudge 中盘子几乎没沿目标方向移动；后来重接近会改变盘子位置和高度，不能把所有 `contact_surface_motion_ambiguous` 一律算作验证器漏判。诊断只作私有标签，零控制，不进运行时。

同状态 CPU 又检查了“预先闭合”和“增加 direct 接近路线”两种几何假设；保留原闭合/整路碰撞/IK 筛选，并要求接触点与接近方向一致时，所需 left 分支仍不可行。没有部署这两种未提供可行方案的假设。原正式物理回合继续保留。

另一个吞吐限制已明确：冻结公开请求里某个 descend 是 blocked，前缀换到另一接触点后其预测路线可行，`legal_after/2` 仍不会凭空解除原 blocked。这是当前公开合同的保守限制，不能在 oracle 或训练标签一侧单独放开。当前 schema / contract 未改，任意前缀标注同样遵守它。

原 ec89f74 上限批的 r11 只计同源完整结果与同身份补回：46 / 220 已完成，38 成功，0 execution_error。`reports/original20_support_interim_r11_20261018.json` 保留各类 Wilson 区间、未完成状态、完整回合和来源。新修复源的盒子、门、盘子不混入这个分母。
