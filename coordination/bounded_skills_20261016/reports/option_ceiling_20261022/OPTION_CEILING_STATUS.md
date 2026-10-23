新通用版 D2 恢复 1 档的 40 局全部采样及独立回放闭合：回放 24/40（Wilson 95% 44.6–73.7%），采样包络 30/38（63.7–88.9%），另 2 局规则未覆盖。
A1 组合诊断在同完整初态下使登记目标 3/36→13/36、原生整局 3/36→10/36；通用版 D2 与前版完整初态 38 局不同、2 局缺失，且私有续接口径变化，不能把 23→24 全归于新增方法。
新执行树的 N1 为同完整初态 24/30→24/30，N2 的旧 132 试次为 62→62；155 状态的旧 1165 试次 460→461，1 好 0 坏，完整初态零差异。
模型闭环已完成 D2 10/40 和原版登记六臂 4/6，Codex2 服务已停；六臂实际是三初态各 K1/K4，完整初态不支持严格 K 配对解释。
四个 GPU 作业及 CPU 收尾全部正常结束；逐局记录、分类区间和 SHA 已整理，成功率和时延目标仍未达到。

| 用户问题 | 证据入口 | 当前结论 |
|---|---|---|
| A1 在 12 局实际做了什么，H1–H5 如何区分 | [逐局分析](A1_HYPOTHESES12.md)、[实际工具参数](A1_12_usage_table.md)、[组合72](A1_joint72_table.md) | 24 次 π 调用 / 336 个实测块；缺逐控制步 ledger 和完整 A1 初态，不能排除 H4。单因素未解释差距，预定位/搬运组合有局部改善。A1 绝对坐标只用于诊断，未进通用执行或训练。 |
| 通用修法有没有退步 | [N1 与 C7](measured_v7_N1.md)、[N2](measured_v7_N2.md)、[155逐状态](measured_v7_155.md) | N1/N2 旧方法零翻转；155 旧1165为1好0坏。新 measured_anchor 的 N2 为5/36，155为160/465登记结果；150次预定位失败。不同终止/真值口径分别保留。 |
| 十五条采样/回放差异 | [逐条表](REPLAY_GAPS15.md) | observe / 零步版本变化记账已修；原生整局与持续抓取分开；4 条“交还丢抓取”的旧归因被精确恢复否定。公开抓取误报仍无可靠通用修法，未用 D2 调阈值。 |
| 原版自检、零控制步状态重测 | [自检](original_selfcheck_table.md)、[87 次补测交付](zero29_C2_delivery.json)、[155 原上下文交付](regression155_C2_delivery.json) | 原版 29 状态 / 87 次已交；155 包 1126 绑定 / 39 unknown context，不复制旧标签。 |
| 新通用版 D2 上限与失败位置 | [最终40局](MEASURED_V7_D2_40.md)、[逐局同表](measured_v7_D2_comparison.md)、[全部子任务](measured_v7_D2_subtasks.jsonl) | 新回放24/40，采样30/38+2unknown；72子任务/936分支，双方全失败10处、部分判据未知1处；7局采样成功而回放失败。采样包络不是部署策略期望成功率或数学全局上界。 |
| 模型、oracle 和 A1 比较 | [模型逐局](model40_paired_table.md)、[前版 oracle](ORACLE_RETRY40.md)、[新40逐局](measured_v7_D2_comparison.jsonl) | 模型10/40，前版回放23/40、采样28/38+2unknown，新版24/40与30/38+2unknown，A1-M28/40；同任务编号下新旧2好1坏，完整初态未相同，不作纯选择错误归因。 |
| 留出位置选中但未测的候选 | [75 次补测 manifest](onpolicy25_return75_manifest.json)、[逐项核对](onpolicy25_return75_metrics.json) | exact 旧请求 25 位置 / 75 实测已交 C2，只评测，不训练。 |
| 炉灶 165 组缩减 | [manifest](stove165_compact_manifest.json)、[逐请求](stove165_compact_per_request.jsonl) | 原冻结 schema6；正文 token 中位 8605→3269、最大 13574→4094，不含 chat wrapper。原 106 快照及前缀映射保留，无新物理标签。 |
| 原版失败整句能否接下个目标 | [CPU见证](PARTIAL_PROGRESS_ORIGINAL_CPU.md)、[真实首chunk](original_partial_handoff_functional_r2.json) | 两个 [True,False] 端点正确跳到 g1:pick；首 move_to 均碰撞筛查拒绝、0 新控制，只证明私有续接/请求生成，不能称物理继续成功。 |

执行源码快照分别登记：原 A1 组合 `8a07e44a9467fcd0b3aad5793dcee63df53c7e35`；模型 D2 `7f87b8ef1a16c554f4380d073eea1a499fa027e7`；公开锚点 v7 回归 `efa57340221c82cb359d72514c7062edb34de599`；新私有进展诊断 `2db200134ea6689e36a66e8aee6f45daa8270b4e`。后两者公开执行代码逐 blob 相同，仅私有阶段续接口径不同。

schema7 SHA256 `546299a6f4d956ddc6a249edc5e64bb532a135e1199e345b222c687611b72182`；contract SHA256 `a0fef7407efb67b4f9cde557cfa09ffcf3964eaaf9eaabad9f671d4e5b900f0b`。普通根包和旧模型仍为 schema6，未迁移旧标签为 v7。

所有确认状态永久排除训练；PRO、D2 只评测。新原版采集显式配置 SHA256 `4cd2fbcd5ab4a4a837eedc79864509554bdd9b484f7769cc3ded40c751f5f9b0`。原生成功、私有持续夹持、登记目标进展分别保留，未覆盖旧失败。所有 Wilson 区间须按对应分母阅读，重复试次不能当作独立布局。

原版整句自检106/110，推盘子和盒子各10/10；每任务一个初态、十个策略噪声种子，不能称十布局。A1的12局缺完整积分/控制器/RNG初态，只能确认公开EEF摘要相同。新D2中两处开柜子子任务仍双方全0，公开抓取判据也仍有不一致；未用D2调阈值补分。

N1的决策循环中位32.22→31.41秒、整局158.49→153.45秒；碗8/8但整局中位199.18秒，未达≤5秒决策/≤60秒碗目标。四段时延及后继legal单列见N1报告；不把数秒差值解释成显著提速。

[最终manifest](measured_v7_D2_manifest.json)、[分类汇总](measured_v7_D2_delivery_summary.json)、[三判据分类区间](measured_v7_D2_rates_expanded.json)、[逐字节镜像校验](measured_v7_D2_mirror_manifest.json)、[作业闭合记录](measured_v7_D2_jobs_closed.json)保留来源和SHA。执行归档SHA256 `7a08e6f42ad4b452d68f3b463cde883c2e0aeb20fe8ba9340ce2791d511ebcb2`。CPU面板809通过、独立RGB-D4通过，固定10真实物理与π启动检查已通过；CPU证据见 [2db检查](measured_progress_2db20013_CPU.json)。本轮未训练；Codex2模型服务已停；旧held及其他项目作业未动。
