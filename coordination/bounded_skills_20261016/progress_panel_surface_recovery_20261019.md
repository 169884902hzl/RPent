# 微波炉表面路线遗漏：修复与复验

1. 10:05 五项已有回答，见 `progress_prefix_judge9_and_door_identity_20261018.md`；本轮继续原版技能上限，不训练。
2. f4400223 的表面路线修复已有 272 项 CPU 回归、220 状态预检和 9604_120 的 490 步启动证据；完整复验 9605_120/140 正在运行，尚无任务成功结论。无固定参考面时跳过主平面拟合的独立问题已在 f75b516d 修复，458 项 CPU 回归和 220 状态预检通过；新启动 9607_120 已提交，等待物理证据。
3. 同一终态原法向 16 条路线全失败；仅改变法向定向后，1/16 通过原筛查。此为跨源码 CPU 诊断，不是关门成功或训练标签。
4. 同状态抽屉恢复复验 9603_117 已原生成功：14 决策 / 1456 步 / 2004.666 秒，旧失败保留；这不是单项 oracle 消融。固定旧源原版批 r15 为 46/56 成功，登记 220；盘子仍为共同失败 0/2，微波炉仍未解决。
5. Codex3 继续同状态物理复验；Codex1 核源码、协议与完整分母；Codex2 仅用匹配上下文的 CPU 前缀接口，历史缺上下文的 59 个 unknown 仍不能补。

## 根因与证据

`9600_120`（184ba1d7）关门完整失败：19 次决策，1477 仿真步，2015.367 秒，汇总阶段为 planning_unreachable。终态仍可见门实体 e114，公开点云 19,360 点，不是单纯身份消失。

原竖直平面通过“门质心减父实体可见质心”确定法向符号。父实体可见质心靠近门面时，该符号不可靠；本例法向与“测得末端减门中心”的内积为 -0.162611 m，路线朝向了手的反面。同一保存上下文用原法向筛查 16 条表面路线，闭合碰撞 8、扫掠碰撞 5、数值 IK 失败 3；仅使法向朝测得末端后，1 条通过。

公开规划中还有一个独立遗漏：无把手测量时会尝试表面；有把手测量但把手路线全部不可行时，却清空计划后跳过表面。现在两种情况都允许已有的、完整筛查通过的表面接触，不承诺该接触能完成开合。

诊断不执行仿真、渲染、RPC 或 GPU。冻结上下文没有 live pixel cache；首次对照脚本在返回可行计划时缺 `_instance_cache`，已保留原脚本并修正，仅用相同捕获点云填充返回计划的像素成员。筛查仍使用原 FrozenScreens 图，没有删除障碍点。

- 原法向：`reports/microwave9600_surface_recovery_CPU_20261018.json`
- 朝手法向：`reports/microwave9600_surface_facing_CPU_20261018.json`，4.607 秒
- 原脚本：`scripts/microwave9600_surface_facing_uninitialized_v1_CPU_20261018.py`
- 修正脚本：`scripts/microwave9600_surface_facing_CPU_20261018.py`

## 验证范围

针对性回归 12 passed / 219 deselected，29.08 秒。覆盖父实体质心位于面两侧、无把手或把手路线被阻挡、表面路线筛查与关节余量选择。相关技能、chunk、离线标注的 CPU 回归 272 passed / 1 warning，218.25 秒；唯一 warning 是已有环境缺 pytest-timeout 插件。日志与源码文件 SHA 见 `reports/panel_surface_recovery_cpu_20261019.json`，未修改原始 pytest 输出。

| 项 | 确切值 |
| --- | --- |
| 源码 commit | `f44002235eefa806d7731b842566740aea2525c9`（harness-v5，已普通推送） |
| 快照 | `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_panel_facing_20261019_f4400223` |
| 归档 SHA256 | `079ad9f1bcd38d005236c7c46286b93e1b312159d7ee1edffc269cdc1a6a2bfa` |
| manifest | `/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/feasibility_20261017/preparation/original20_manifest_chunk_v3_panel_facing_20261019.json` |
| manifest SHA256 | `8e5f61b75a0c58be44770f8a892fd3af0c86a518cbacd9fbf8862c156eb2dc9e` |
| 入口 | `scripts.probe_bounded_feasibility:episode` |
| 解释器 | `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python` |
| 启动 | `9604_120` COMPLETED 0:0；startup_physical，1 决策 / 490 步 / 148.283 秒；不是任务成功率 |
| 完整复验 | `9605_120/140`；同快照、同 launcher，启动实际物理请求通过后提交 |
| 完整复验身份 | `microwave_close_libero_90_t33_s0` / `microwave_open_libero_90_t35_s0`，索引 120 / 140 |

公开 schema 保持 bounded-skills/3，legal 保持 public-request-legal/2，私有 judge 保持 rules/13。接口没有新增字段。源码行为修复与已有同源标注结果分开，不把旧上下文改记为新源训练标签。

## 上限批与未解问题

`reports/original20_support_interim_r15_20261019.json`：固定 ec89f74，46/56，登记 220，0 execution_error；截至 2026-10-18 21:15 PDT。此前 r14 的 43/52 原件保留；新增四局为三成功、一失败，不重写旧结果。

| 类别 | 成功/完整回合 | Wilson 95% 区间 |
| --- | --- | --- |
| 碗 | 7/7 | 64.6–100% |
| 罐 | 7/7 | 64.6–100% |
| 放入容器 | 7/7 | 64.6–100% |
| 杯 | 4/7 | 25.0–84.2% |
| 抽屉关 | 7/7 | 64.6–100% |
| 抽屉开 | 4/6 | 30.0–90.3% |
| 微波炉关 | 0/1 | 0–79.3% |
| 微波炉开 | 0/1 | 0–79.3% |
| 盘子推移 | 0/2 | 0–65.8% |
| 灶台关 | 4/5 | 37.6–96.4% |
| 灶台开 | 6/6 | 61.0–100% |

上述罐不是奶油奶酪盒子。真实盒子另分源统计。ee42501 的最后两局 9515_18/19 已完整原生成功，各 2 次决策、404 步，墙钟 256.954 / 244.016 秒，不能合入 ec89f74 或 4db4ea4 分母。

9515 的正式数组只登记剩余 18 局：完整结果 15/18，Wilson [60.8%, 94.2%]，0 execution_error；不要把它写成完整 20 局。新源 9579 暂为 3/20 完成，3/3 成功，Wilson [43.9%, 100%]。分别见 `reports/box_pad_edge18_closed_20261019.json` 和 `reports/box_transport20_interim_r2_20261019.json`。首次误用依赖额外注册字段的专用汇总器触发 KeyError，已改用现有通用逐登记索引汇总器重算，没有修改提交回执或原始记录。

盘子障碍点的同帧 RGB 叠图显示左侧柜体把手确为障碍，不能通过删点解决。抽屉 9603_117 已完整原生成功：14 决策 / 1456 步 / 2004.666 秒。与 9248_192 的完整 case/state/BDDL 身份逐项相同，改善 1、退步 0；pi0.5 两臂均关闭。完整结果、choices/summary/private result 的原路径与 SHA 见 `reports/drawer9603_117_closed_paired_20261019.json`。两臂源码 ec89f74 / 3df760d0 之间包含其他修复；因此这证明同状态开发复验成功，不是只改私有 oracle 的隔离消融，也不是抽屉类别通过。

微波炉开门 9600_140 已完整失败：27 次决策、1432 步、2809.683 秒，归类 perception。后者与关门的 planning_unreachable 分开诊断，不能认为此次路线修复已经解决开门身份问题。完整原始汇总为 `reports/microwave9600_closed_20261019.json`。保持原失败与源码身份，不宣称这些类别通过。

开门同源终态的 CPU 接口复算为 no_acceptable_public_option，2.015 秒；legal 仍有 29 项，acceptable 为空，门不在终态锚点中，见 `reports/microwave9600_140_terminal_CPU_20261019.json`。

另核对了真实主/腕视角的同帧点云叠图：capture9/15/19 的腕部“接受门”点云落在左侧固定控制面板；capture15/19 的主视角拒绝点云则覆盖真正的门框和把手。不是所有分割都错了，也不能仅靠继续跟踪把错误面板变成门。27 个请求/终态的公开测量审计记录 40 次 door_plane_not_measured、5 次缺双向视觉对应、4 次追踪通过、2 次独立视觉支持不足；这些是测量实例次数，不是独立回合。详见 `reports/microwave9600_identity_audit_CPU_20261019.json` 及六张 `microwave9600_identity_*_CPU_20261019.png`；已实际查看两视角图片。

源码 `moving_panel_points` 在没有独立固定参考片时直接返回原始点云，跳过已有 4 mm / 55% 主平面一致性拟合。正确的门框和凸出把手一起进入严格平面残差检查，错误的平坦控制面板却可通过。隔离 CPU 假设恢复了两个主视角平面：保留比例 65.86% / 60.67%；原始平面检查均失败。`reports/microwave9600_panel_consensus_CPU_20261019.json` 保留精确函数哈希与输入。仅允许原有拟合不等于测得运动；修复已在 f75b516d 提交并普通推送，458 项 CPU 回归通过（215.76 秒），针对性 5 项通过，220 登记状态预检通过。诊断 basis 升为 `/2-dev`，增加 `fixed_reference_available` 和 `motion_established=False`；缺固定参考面的开合终点仍为 unknown。

新源码快照为 `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_panel_consensus_20261019_f75b516d`，完整 commit `f75b516d4d57ee5f77cdb19db8b0082a4bc0490c`，归档 SHA256 `53deed46dffe5ee5a83795c366cb9bca8e7a4678afe90c0112c5780fb29ed1f6`；manifest SHA256 `7765c5a54055ade5e14582928d809884287ade63368cf6eedcb208a8a4e3afc6`。入口和解释器不变。CPU 原始收据为 `reports/panel_consensus_cpu_20261019.json`；共享 COORDINATION 已在新源码首次仿真前通知，append offset 6902141273–6902145105，SHA256 `06c8218d6a26150440ad8694c6f50a647de3a1d610c83d36bab9d03169273a32`。同快照同 launcher 启动为 9607_120；启动后才放完整复验，仍不能宣称门身份或开合成功已修好。

另一 CPU 对照表明，简单跨视角深度支持仍无法区分身份：真门对应另视角 127,273 / 101,977 像素，固定面板也分别有 3,135 / 2,267 个可见对应，四个都通过现有平面支持规则。因此没有部署“有跨视角对应就选这个门”，也没有调高像素阈值排除固定面板。见 `reports/microwave9600_panel_crossview_CPU_20261019.json`。门身份仍是独立未解问题。

资源：node02 / nice500；有 Codex2 GPU 排队时替补并发不超过 3，无时可借第 4 卡；唯一控制器持续查 sacct，用户保护作业和旧 held 作业不动。所有确认状态永久排除训练。
