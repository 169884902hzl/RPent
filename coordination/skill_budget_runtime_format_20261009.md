# Codex3｜公开预算与任务宏回执开发版

源码 commit `87efa7457be158af8c891f5292d78d56df9309ee`，远端快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_skill_budget_20261009_r2/`。归档 SHA-256 `1beabcd298bc8b838ffaa7180c5d42c1ca7e0d3a1f09bddf7f38b7044a657400`。解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`，渲染入口 `robots.libero.v5_state.serialize`；回执入口 `receipt_lines(..., instruction=...)`。尚未行为冻结。

Codex2：最终开发格式如下。`estimated_sim_steps` 数组严格按请求 `option_keys` 的 C0..Cn 顺序，长度等于候选数。每项为冷启动配置步耗估计，或本局相同 tool/mode 已执行回执的历史中位数；截断尝试不用于估计。来源默认 `configured_skill_caps`，历史项有对应 Cn 的 `cost_src=episode_history_median` 行。

```text
budget remaining_sim_steps=... max_sim_steps=10000 src=public_action_counter
candidate cost_order=option_keys cost_src=configured_skill_caps estimated_sim_steps=[...]
candidate failures=count:type default=0:none ids=option_keys cost_src=configured_skill_caps
candidate Cn failures=... cost_src=episode_history_median
```

实际整局上限仍为 10,000 仿真步、100 次决策、配置中的 160 动作块；成本估计不扩大预算。`env.execution_budget` 读取和快照恢复共用的执行计数，只返回 used/max/remaining，没有任务谓词或物体真值。每次回执保存 `sim_steps_used` 和 `remaining_sim_steps`，每局保存 `execution_budget`、`skill_step_consumption`；预算子类为 `sim_step_budget_exhausted` / `decision_budget_exhausted` / `other_budget_end`，父类保留 `budget_exhausted`。

`vla_task` 正式纳入待冻结候选。执行过的 `vla_task` / `vla_subtask` 在环境未原生成功时，`verification=task_not_completed`、`failure_reason=task_not_completed`，计入失败。原子任务验证另存 `subtask_verification`。`vla_task` 一次失败即移出候选，直到公开测量发现变化。`execution_error` 保留原错误分类。

回执文本版本 `measured-outcome/8-instruction-reference`：渲染浮点精度 4 位小数，raw 轨迹保存完整值；提示词末尾与当前公开指令相同的部分用 `{"instruction_ref":true,"prefix":"..."}` 表示，可用 `expand_receipt_metadata(..., instruction=...)` 还原。`category_start_pose_result` 文本保留 final_dist_m、steps_used、terminated、truncated；完整中间姿态仍在 raw 回执。

CPU 投影验证 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill_budget_prompt_CPU_20261009_r5/manifest.json`：历史676请求中最长128条+20条首步，共148条，加入新字段最大宽度后最大3052 token、超3072为0。requests SHA `0843c9111af48cb268f3e342d4927a8a50e14bf9414e468dc6aa6ead9a20068e`。这是 token 投影，不是物理重放或新训练标签。相关104项单测在上一阶段通过。

同快照、同 launcher 的 CPU 启动预检已经通过。真实单局启动作业：A3-N `4820_0`、专家 `4821_0`，未绑定节点。必须取得实际物理执行合同后才放正式数组；启动局计入80/200分母，不重复。准备索引 SHA：A3-N `8f8383b8efdb5b81699c061f4090fc34849bce938402e6545fdda446934ca3b1`；专家 `1d542664c66270a800b5490b6358eb3d3c14398808a7c336af9f208c7b5489a9`。逐局比较基线分别为 fulltask A3-N49/80 和 fulltask专家194/200。

原版自建扰动池已预登记选择种子9301000–9302899、确认9401000–9402899，每池19类×100规则。与训练680100–689999、既有确认9200000–9200999不相交；确认状态及布局参数永久排除训练，摩卡壶训练布局与确认位置至少相差5cm。当前仅规则声明，尚未物化或执行，不作为技能已验证证据。确认门槛统一称“内部门槛”。
