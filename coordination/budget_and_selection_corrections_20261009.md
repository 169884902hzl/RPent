### Codex3｜10-09 01:xx PDT：预算修复与选择批继续

用户确认 `vla_task` 纳入冻结候选。开发中的新合同为：

- `vla_task_v1` 默认启用，和拆分技能并列，24候选上限不变；读取当前公开任务指令，不读取PRO任务文件。
- `vla_task` / `vla_subtask` 已执行但环境未原生成功时，回执 `verification=task_not_completed`、`failure_reason=task_not_completed`，计入失败。原公开子任务验证保留为 `subtask_verification`，不混同整个任务完成。
- `vla_task` 一次失败后从候选删除，直到公开测量出现场景变化；其他宏仍按两次失败规则。
- `env.execution_budget` 只返回执行步数与已登记上限，和物理分支恢复使用同一预算计数。无物体/关节真值或任务谓词。
- 状态增加 `budget remaining_sim_steps=... max_sim_steps=... src=public_action_counter`；候选增加 `estimated_sim_steps` 和估计来源。冷启动使用配置技能步数估计，随后使用本局过去执行回执的中位数；估计不保留或扩大实际预算。
- 每次执行保留 `sim_steps_used`；每局汇总 `skill_step_consumption`。`budget_exhausted`父类保留，子类互斥为 `sim_step_budget_exhausted`、`decision_budget_exhausted`、`other_budget_end`。

Codex2：这是未冻结的新格式，不能直接重渲染旧行补足缺失测量。入口仍为 `robots.libero.v5_state.serialize`，新增可选 `execution_budget` / `candidate_costs`。源码与真实启动验证完成后交确切快照和SHA。

已完成的旧专家链：同源码启动4779+正式4780，176/200，Wilson95 [0.827657,0.918020]，Spatial50、Object45、Goal47、Long34；成功176、预算11、无候选12、超token1。对历史177：旧成功→失败10、新成功9。它与 `vla_task` 专家194/200是不同配置，分别保留。
产物 `/public/home/sunyihan/rpent_libero_eval/artifacts/expert_cached200_closed_20261009_r1/`，manifest SHA256 `0c4a2f6259a87a93b8da02e3c8915b92e692c8d085c9b95c0b76165a36387f2d`。
绑定过滤4791_0+4798_[1-3]四局均物理失败，不能写绑定已修好。

微波炉4797_0有实际控制，关闭真值true、公开verified；执行后回执脚本的Python字符串换行转义导致exit1。已改raw字符串，两段内嵌Python通过compile；r2十份CPU预检exit0，实际启动4811_0已提交，无绑定，等待可用卡。
r2 index SHA256 `6ec3e4d518005e81dc501d9dd3fb5278cd7e1ceca5f980077fe1dfa40f8308c5`，wrapper SHA256 `7d314477218be875a1a608342551846bccb5269871b37721eb2355bfc5d049fa`。

摩卡壶选择4803：6片实际运行、2片等待限流。调度器拒绝增加运行中4803_0–5的时限（Access/permission denied）；等待中的6/7已延至12h。原两小时计划偏短，已完成记录保留，未完成部分按开发接续，不重复已完成状态。启动4794_0物理失败保留，并计入100选择分母；不是确认批。

更正上一份抽屉诊断：`goodFeaturesToTrack`第5位置参数不是mask，r1统计162可测/88身份不符和“69前板点零位移”不成立，作废但保留产物。改为关键字`mask=`，加入mask外纹理回归，5项通过。r2为180时刻/360相机对应，35可测、7身份不符；这是CPU公开图像对应，还未获得技能验证资格。
r2逐次SHA256 `89f8bcbc9c656102ebe721a839d8b9a08e1c2aeef49fe4b416afb828b2b87803`，tracker SHA256 `fef4de6b7a4d5d9476e779f61cb7d27d03b261cc18d43bb1c26a0b1084bd0946`。

全部门槛称内部门槛；所有确认布局和种子永久排除训练。新扰动池将预登记与680100–689999和9200000–9200999不相交的种子。尚未冻结，不提交最终评测或冻结后训练采集。
