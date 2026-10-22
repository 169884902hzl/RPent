十五条历史采样/回放差异逐条保留，历史分数不改。新源码的实际整局回放另列，不把CPU复现称为物理修复结果。

| 局 | 恢复预算 | 当前结论 | 依据或修改 |
|---|---:|---|---|
| libero_object_swap_t1_s40 | 0 | 已修记账 | 63d2f0a3：predicted_anchor_changed且0控制仅触发重新决策，不消耗动作恢复预算。 |
| libero_spatial_task_t2_s40 | 0 | 原归因不成立；尚无已验证的通用感知修法 | 四条原始控制逐条精确重放，完整sim_state/native_data逐字节一致；交还前和交还后持续夹持均False，双指接触0/11。公开完成先误报，不能归因制动丢抓取。 |
| libero_object_task_t3_s40 | 0 | 改默认整句预算；物理效果待新批 | 91ff4112：仅uncapped默认mode=task从24块改为原版已用104块/520控制；显式cap和其他模式不变。不同种子下的独立失败并不由此保证消失。 |
| libero_goal_swap_t1_s40 | 0 | 未解决 | 公开测得抬离4.336cm和相对运动0.723mm，但私有双指0/11。原版日志FP26中22缺双指；去机器人自身像素的离线检验无优势，未部署，也未用D2调阈值。 |
| libero_goal_task_t2_s40 | 0 | 已修记账 | 87978ba5：observe回执为no_effect/no_measured_scene_change，不消耗动作恢复预算（腕部扫描可以有控制步）；真实失败动作照常计数。 |
| libero_10_swap_t1_s40 | 0 | 改默认整句预算；物理效果待新批 | 91ff4112：仅uncapped默认mode=task从24块改为原版已用104块/520控制；显式cap和其他模式不变。不同种子下的独立失败并不由此保证消失。 |
| libero_goal_task_t2_s40 | 1 | 已修记账 | 87978ba5：observe回执为no_effect/no_measured_scene_change，不消耗动作恢复预算（腕部扫描可以有控制步）；真实失败动作照常计数。 |
| libero_goal_task_t3_s40 | 1 | 未找到原版证据支持的通用修改 | 该独立种子23/24块后停止；原版标定的5块/5mm保留，不按此D2失败放宽阈值。 |
| libero_10_task_t2_s40 | 1 | 原归因不成立；尚无已验证的通用感知修法 | 四条原始控制逐条精确重放，完整sim_state/native_data逐字节一致；交还前和交还后持续夹持均False，双指接触0/11。公开完成先误报，不能归因制动丢抓取。 |
| libero_goal_swap_t2_s40 | 2 | 原归因不成立；尚无已验证的通用感知修法 | 四条原始控制逐条精确重放，完整sim_state/native_data逐字节一致；交还前和交还后持续夹持均False，双指接触0/11。公开完成先误报，不能归因制动丢抓取。 |
| libero_goal_swap_t4_s40 | 2 | 改默认整句预算；物理效果待新批 | 91ff4112：仅uncapped默认mode=task从24块改为原版已用104块/520控制；显式cap和其他模式不变。不同种子下的独立失败并不由此保证消失。 |
| libero_goal_task_t1_s40 | 2 | 已修记账 | 63d2f0a3：predicted_anchor_changed且0控制仅触发重新决策，不消耗动作恢复预算。 |
| libero_goal_task_t2_s40 | 2 | 已修记账 | 87978ba5：observe回执为no_effect/no_measured_scene_change，不消耗动作恢复预算（腕部扫描可以有控制步）；真实失败动作照常计数。 |
| libero_goal_task_t3_s40 | 2 | 已修诊断器选择；物理效果待新批 | 4d6cd9ba：第二次请求有合法fail0的新种子，却重复fail1的base，触发循环后候选消失。优先最少公开失败历史，不改循环阈值/候选或模型。真实请求CPU回归已通过。 |
| libero_10_task_t2_s40 | 2 | 原归因不成立；尚无已验证的通用感知修法 | 四条原始控制逐条精确重放，完整sim_state/native_data逐字节一致；交还前和交还后持续夹持均False，双指接触0/11。公开完成先误报，不能归因制动丢抓取。 |

原件：

- 历史15条：[逐次分类](replay_gap15_compact.json)。
- 精确交还前后复核：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022/CPU_handoff_private_r3/compact_conclusion.json`。
- 真实重试请求：`CPU_variant_unavailable15_before_loop_requests.json`；提交内复现fixture为 `vla_retry_before_loop_20261023.json`。
- 至少六条native整局漏计：[原端点审计](native_endpoint_audit_summary.json)。原生整局完成与私有持续夹持分别记账，不互相覆盖。

补充原版 train 及自扰动训练域日志的公开判据离线核查（CPU11549，285个有计量端点，另3缺计量保留）：原判据 TP77/TN168/FP26/FN14，一致率85.96%。15mm相对位移收紧到10mm变为TP75/FP25，只去掉1个误报却新增2个漏判；空夹爪上界加2mm变为TP63/FP22，去掉4个误报但新增14个漏判。要求相对误差不超过手部位移一半，只去掉1个误报，仍有25个误报。连同先前去机器人像素实验，这些对照未找到能可靠区分持续双指夹持与非双指跟随/错误跟踪的公开判据；未部署阈值修改。此处只是已保存端点的分类敏感性，不能冒充改变停止时机后的物理结果。逐端点及分类Wilson区间见[公开抓取判据核查](public_hold_guard_sensitivity.json)。重复状态的端点区间不代表类别泛化。
