# 抽屉恢复遗漏与物理验证进度

1. 10:05 五项已有直接答案：函数级 profile、碗 init2 共同失败修复、CPU 任意前缀接口、候选顺序无语义、最近三条详细回执。详见 `progress_prefix_judge9_and_door_identity_20261018.md`。
2. 抽屉恢复遗漏已在 CPU 修复：失去接触拟合并清空 active 后，无已验证持物的闭合夹爪仍可选既有开夹爪恢复。旧终态请求的 legal 不变，acceptable 从空变为该 open 选项；物理修复尚待验证。
3. 源码 `3df760d0c3a4347d1e8737f7392708e657c8977a` 已普通推送 harness-v5；269 项 CPU 回归、220 个登记初态的路径预检通过。私有 judge 升为 13，公开 schema / legal 不变。
4. 固定 ec89f74 上限批已完成 49/220，原生成功 40；新源盒子 9579 首三局成功。盘子 9576 两局均完整失败，旧源同状态也是 0/2；新源微波炉 9600 两局仍在执行，不能宣称类别通过。
5. Codex3 继续同状态物理复验；Codex1 核源码与分母；Codex2 仅用匹配源/judge 的保存上下文标注。未训练、未冻结，确认状态永久训练排除不变。

## 抽屉根因与 CPU 复现

旧源 ec89f74 的 `9248_192`（drawer_open_libero_goal_t0_s17）失败：10 次决策、1114 tick、765.443 秒，最终无剩余公开选项。接触失败之后 `active=None`、`held=None`、`plans={}`，夹爪开度约 0.01748 m。公开 `set_gripper(open)` 仍合法且没有近期失败。旧 oracle 却要求 `active == source.id` 才能重新张开，因而遗漏恢复动作。

新规则删除这项绑定依赖，保留“无已验证 payload”和闭合夹爪条件，不丢弃已验证持物。单元测试覆盖 active 匹配、清空、其他实体，以及有/无持物、开/闭夹爪。

冻结旧终态上下文的 CPU 对照耗时 0.805486 秒；judge12 的 acceptable 为空，judge13 的 acceptable 为既有 `set_gripper(open)`。请求 SHA `9f3ee2246abfee3eb0dd42ec8a9550b2d8bd3e85076afd95bf7ed2f677b30040`，legal 列表逐项相同。该对照跨源码，只作根因诊断，不作同源训练标签或物理结果。

- 原始终态诊断：`reports/drawer9248_192_terminal_CPU_20261018.json`
- 修复对照：`reports/drawer9248_192_recovery_CPU_20261018.json`
- 测试：`reports/lost_binding_recovery_cpu_20261018.json`，269 passed / 1 warning，198.09 秒。warning 是当前环境缺 pytest-timeout 插件；没有测试失败。
- 原状态在当前 manifest 中的索引为 117，提交前按完整 case 名核对，未沿用旧 manifest 的索引 192。
- 同快照同 launcher 的启动作业为 `9602_117`，待首次物理请求后再启动完整复验。启动不计任务成功率。

## 快照与版本

| 项 | 确切值 |
| --- | --- |
| 快照 | `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_lost_binding_20261018_3df760d0` |
| commit | `3df760d0c3a4347d1e8737f7392708e657c8977a` |
| 归档 SHA256 | `6311080244a5ea0559bc10b4b27dd12049efc2383f4cadb21e41929a124eb7c3` |
| 入口 | `scripts.probe_bounded_feasibility:episode` |
| 解释器 | `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python` |
| manifest | `/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/feasibility_20261017/preparation/original20_manifest_chunk_v3_lost_binding_20261018.json` |
| manifest SHA256 | `88012bf2ac0332df79000f0f8ae45ce4b312334de40c6372375539cda884ff19` |
| schema / legal / judge | `bounded-skills/3` / `public-request-legal/2` / `libero-private-task-progress-rules/13` |
| oracle 源码 SHA256 | `c6057acd0056d940b1c03235c2d54a27e3750161e16f8a8936f0af45db70cc89` |
| schema SHA256 | `df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa` |
| contract SHA256 | `7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c` |

## 固定旧源的类别结果

`reports/original20_support_interim_r13_20261018.json` 保留每局记录、失败阶段、chunk 截断、决策次数、仿真步数、墙钟和区间。只统计固定 ec89f74 及同身份补回，不混入后续修复源。

| 类别 | 成功/完整回合 | Wilson 95% 区间 |
| --- | --- | --- |
| 碗转移 | 6/6 | 61.0–100% |
| 罐转移 | 6/6 | 61.0–100% |
| 放入容器 | 5/5 | 56.6–100% |
| 杯子转移 | 3/5 | 23.1–88.2% |
| 抽屉关 | 6/6 | 61.0–100% |
| 抽屉开 | 4/6 | 30.0–90.3% |
| 微波炉关 | 0/1 | 0–79.3% |
| 微波炉开 | 0/1 | 0–79.3% |
| 推盘子 | 0/2 | 0–65.8% |
| 灶台关 | 4/5 | 37.6–96.4% |
| 灶台开 | 6/6 | 61.0–100% |

旧 manifest 的 box_transfer 实际是罐；真实盒子另在 9579 运行，不拿罐的成绩充盒子。9248_54 是开火，1 决策 / 665 tick / 100.979 秒；9248_53 是关火，5 决策 / 1503 tick / 355.788 秒。

## 盘子的 CPU 几何限制

4db4ea4 的 9576 已关闭：0/2，Wilson 95% 区间 0–65.8%。逐状态对照见 `reports/plate9576_closed_paired_CPU_20261018.json`。旧源同状态也是 0/2，改善 0、退步 0、共同失败 2。

| 状态 | 旧决策/步数 | 新决策/步数 | 新墙钟秒 | 新终态 |
| --- | --- | --- | --- | --- |
| plate_push_libero_goal_t5_s0 | 69 / 10000 | 26 / 2438 | 2519.376 | 无剩余公开选项 |
| plate_push_libero_goal_t5_s1 | 93 / 10000 | 32 / 3024 | 3351.675 | 无剩余公开选项 |

两局汇总 failure_phase 都是 verification_error，但这不是已证明的验证器漏判：前期私有零控制复查显示盘子几乎没随 nudge 移动，后续重接近才产生位移。真实接触不足与公开测量不确定均保留；缩短失败回合不算提高成功率。

闭合夹爪 + direct 接近 + 向内倾斜接近的组合检查仍未得到需要的 left 路线；该方向只有原垂直接近。33.042 秒的 CPU 输出保留在 `reports/plate9575_inward_rim_closed_direct_CPU_20261018.json`。未部署，没有降低碰撞/IK 门槛。之前的闭合手指侧面、direct、倾斜等检查及完整失败均保留。障碍点只能确认来自较高的公开测量表面，尚未从图像核定具体物体，不能猜成柜体。

资源仅 node02 / nice500；唯一控制器替换为本轮抽屉启动监控，原仿真作业不取消。Codex2 没有普通 GPU 作业时借第 4 卡，出现排队后限制替补并发至 3；用户 c5/c6/rf 与旧 held 作业未动。
