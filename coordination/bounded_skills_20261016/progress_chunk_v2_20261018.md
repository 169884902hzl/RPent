Codex1/Codex2：10/17 23:10 PDT 补充指令已实现协议 v2，进入原版仿真启动检查。本轮未训练。

源码：harness-v5 `77ee4fff6213c5dd0aaf0431c7bb18fb66897282`，已推送 user-fork/harness-v5。
规格：`/home/agilex/cobot_magic/rpent_libero_eval/SKILL_PACKAGE_SPEC.md`，SHA256 `90633f58a6fa6f57c07485e5e4a11d08c4bb40e9a0b6d6b1b282e1ca326d6c5f`。
唯一 schema：`/home/agilex/cobot_magic/rpent_libero_eval/rpent/skill_package/schema.json`，版本 `bounded-skills/2`，SHA256 `2af1ac62f759f540c5d96a0f1c6328982f414c0c2b560e80ea98a430a2ef601c`。
5880 快照：`/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v2_77ee4ff_20261018`。归档 SHA256 `530486fe43e1fdf546716dc72c05daf1f8b32341b48ba53f06187c9d92000f78`。
渲染/执行入口：`robots.libero.bounded_skills:MeasuredSkillAdapter.request`、`prefix_context(request, prefix)`、`execute`；仿真入口 `scripts.probe_bounded_feasibility:episode`；解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

主要变化：
- 静态终点仅 observe/call_vla/finish/ask_help。descend、夹爪、lift、lower、release 和接触 nudge/rotate 可有后缀。
- candidate.required 新增 expected_receipt；receipt 新增 expectation_checks。代码给出位置/姿态、闭合宽度范围、抬升 3cm 与持物、放开、接触位移的条件。执行后逐步核验，缺测或不满足就丢后缀。原生成功优先。
- public prefix_context 给出 prefix、predicted_robot、条件后果 candidates、assumptions。预测不是测量；后续手部/载荷碰撞与 IK 按前缀预测状态重算。运行时按新测量复核，未知锚点不得引入。Codex2 MODEL_IO_SPEC 第2节旧“需要抓取新结果就静态截断”需随用户修订更新；合法图不得来自 oracle 答案。
- 私有 oracle_labels 和 oracle_position 已在同一 schema 定义。字段对齐 rule_acceptable / measured_success / measured_failure / judge / evidence，含精确 request_sha256 与有序 prefix；输出 private_oracle_labels.jsonl，绝不进公开 request。规则枚举各未完成目标的当前进展选项、同源所有可行接近和不超过所选幅度的同向接触增量；不是逐个备选的实测成功。
- 最终集合 `(rule_acceptable ∪ measured_success) − measured_failure`；实测正负冲突拒绝。后续位置使用各自预测前缀，不能复制 root 标签。
- 平滑报告已补接缝平移/转动加速度最大跳变、最大参考 jerk/上限比；不再新增 jerk 连续性要求，保留现有 C3。速度/力/预算没改，待分类墙钟与超步数证据决定是否调速。

CPU：原聚焦集 215 passed；之后针对变动复测 32 passed；最终 chunk/motion 19 passed（分母有重叠，不相加）。Ruff 致命错误检查、bash -n、CLI import/help、diff --check 通过。新原版 manifest 220 状态 CPU 预检通过；原始 case、BDDL、state SHA、预算和永久排除登记均未改。manifest `/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/feasibility_20261017/preparation/original20_manifest_chunk_v2_20261018.json`，SHA256 `9fce1751a2cbd617c6507e66a4e036b38d7d88c2b04d958f356384dc7b9f7297`。

启动与正式配对：同一快照、同一 launcher，先实际到 first_physical_request，再放正式数组。正式配对仅比较 chunk 截断规则：oracle_k4 与 oracle_k4_legacy（legacy_chunk_boundaries_v1），两组共用 v2 测量、回执检查和几何代码，均禁 π0.5；历史 v1 结果另外保留。按状态、BDDL SHA 配对，报告真实动作/决策分布、按技能截断原因和分母、成功率、Wilson 区间、分类墙钟、仿真步数与超限次数。

资源：仍只 node02、nice500；本项目三通道，每条 throttle=1，合计≤3。Codex2 8280 已运行使用第4卡，不借卡。旧 held 不 release；c5/c6/rf 未改。先 oracle 上限，再两个技能对照，再 K1/K4 平滑度，最后分叉。

现有旧规则结果刷新（不是 v2 物理资格）：9cacb71 抽屉开 init0–8 为 9/9；a4d51ef 盒子 init4 成功（6决策/415步/322.36秒），init5 失败（8决策/317步/497.99秒）；e6b0b47 杯子双物体任务失败（18决策/1987步/1528.88秒，第二物体阶段碰撞阻挡）。已登记 precontact 五对闭合：改善2、双失败3、退步0，另两对微波炉待结果。不能把重复状态加成独立样本。

启动已提交 `8284_24`，等待正在运行的 `8173_32` 自然结束，未取消任何运行任务。后续旧8173普通排队分片已改为等8284；只有同launcher产生物理请求并正常完成，才提交新规则正式配对。23:40 PDT squeue 截图：本项目 node02=3、node01=0，Codex2 作业另列。证据 `coordination/bounded_skills_20261016/reports/resource_latest_node02_cap3_20261018.{json,png}`。
