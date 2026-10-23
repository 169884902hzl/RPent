原版整句自检 106/110，推盘子和盒子各 10/10；不能把子任务分叉的失败归因于这两个原版任务本身不可完成。
A1 组合诊断在同完整初态下使登记目标 3/36→13/36、原生整局 3/36→10/36，但公开锚点通用版的优势尚未建立。
新执行树的 N1 为同完整初态 24/30→24/30，N2 的旧 132 试次为 62→62，均零翻转；155 状态回归尚在运行。
模型闭环已完成 D2 10/40 和原版登记六臂 4/6，Codex2 服务已停；六臂实际是三初态各 K1/K4，完整初态不支持严格 K 配对解释。
新通用版 D2 恢复 1 档已登记，待 155 回归全闭合评估后提交；本文件仍是进度，尚非最终结果。

| 用户问题 | 证据入口 | 当前结论 |
|---|---|---|
| A1 在 12 局实际做了什么，H1–H5 如何区分 | [逐局分析](A1_HYPOTHESES12.md)、[实际工具参数](A1_12_usage_table.md)、[组合72](A1_joint72_table.md) | 24 次 π 调用 / 336 个实测块；缺逐控制步 ledger 和完整 A1 初态，不能排除 H4。单因素未解释差距，预定位/搬运组合有局部改善。A1 绝对坐标只用于诊断，未进通用执行或训练。 |
| 通用修法有没有退步 | [N1 与 C7](measured_v7_N1.md)、[N2](measured_v7_N2.md) | 旧方法零翻转；新 measured_anchor 的 N2 为 5/36，22 次预定位失败。155 状态仍在运行。 |
| 十五条采样/回放差异 | [逐条表](REPLAY_GAPS15.md) | observe / 零步版本变化记账已修；原生整局与持续抓取分开；4 条“交还丢抓取”的旧归因被精确恢复否定。公开抓取误报仍无可靠通用修法，未用 D2 调阈值。 |
| 原版自检、零控制步状态重测 | [自检](original_selfcheck_table.md)、[87 次补测交付](zero29_C2_delivery.json)、[155 原上下文交付](regression155_C2_delivery.json) | 原版 29 状态 / 87 次已交；155 包 1126 绑定 / 39 unknown context，不复制旧标签。 |
| 模型、oracle 和 A1 比较 | [模型逐局](model40_paired_table.md)、[前版 oracle](ORACLE_RETRY40.md) | 模型 10/40，前版独立回放 23/40、采样 28/38 + 2 unknown，A1-M 28/40；完整初态未认证相同，不全归因于模型选择。 |
| 留出位置选中但未测的候选 | [75 次补测 manifest](onpolicy25_return75_manifest.json)、[逐项核对](onpolicy25_return75_metrics.json) | exact 旧请求 25 位置 / 75 实测已交 C2，只评测，不训练。 |
| 炉灶 165 组缩减 | [manifest](stove165_compact_manifest.json)、[逐请求](stove165_compact_per_request.jsonl) | 原冻结 schema6；正文 token 中位 8605→3269、最大 13574→4094，不含 chat wrapper。原 106 快照及前缀映射保留，无新物理标签。 |
| 原版失败整句能否接下个目标 | [CPU见证](PARTIAL_PROGRESS_ORIGINAL_CPU.md)、[真实首chunk](original_partial_handoff_functional_r2.json) | 两个 [True,False] 端点正确跳到 g1:pick；首 move_to 均碰撞筛查拒绝、0 新控制，只证明私有续接/请求生成，不能称物理继续成功。 |

执行源码快照分别登记：原 A1 组合 `8a07e44a9467fcd0b3aad5793dcee63df53c7e35`；模型 D2 `7f87b8ef1a16c554f4380d073eea1a499fa027e7`；公开锚点 v7 回归 `efa57340221c82cb359d72514c7062edb34de599`；新私有进展诊断 `2db200134ea6689e36a66e8aee6f45daa8270b4e`。后两者公开执行代码逐 blob 相同，仅私有阶段续接口径不同。

schema7 SHA256 `546299a6f4d956ddc6a249edc5e64bb532a135e1199e345b222c687611b72182`；contract SHA256 `a0fef7407efb67b4f9cde557cfa09ffcf3964eaaf9eaabad9f671d4e5b900f0b`。普通根包和旧模型仍为 schema6，未迁移旧标签为 v7。

所有确认状态永久排除训练；PRO、D2 只评测。新原版采集显式配置 SHA256 `4cd2fbcd5ab4a4a837eedc79864509554bdd9b484f7769cc3ded40c751f5f9b0`。原生成功、私有持续夹持、登记目标进展分别保留，未覆盖旧失败。所有 Wilson 区间须按对应分母阅读，重复试次不能当作独立布局。
