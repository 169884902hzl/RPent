修复后的恢复预算1评测已全闭合：独立整局23/40，Wilson95为42.2%–71.5%；采样上限28/38，Wilson95为58.0%–85.0%，另2私有规则unknown单列。所有40局均有实际非零步整局回放。
旧oracle为21/40，新旧同任务/初态编号协议下2好0坏；完整历史物理初态没有认证相同，因此不是受控因果改进结论。模型10/40、A1-M28/40同表列出。

| 套件 | 新整局 | Wilson95 | A1-M |
|---|---:|---:|---:|
| libero_10_swap | 2/5 | 11.8%–76.9% | 3/5 |
| libero_10_task | 4/5 | 37.6%–96.4% | 3/5 |
| libero_goal_swap | 2/5 | 11.8%–76.9% | 3/5 |
| libero_goal_task | 2/5 | 11.8%–76.9% | 4/5 |
| libero_object_swap | 3/5 | 23.1%–88.2% | 4/5 |
| libero_object_task | 4/5 | 37.6%–96.4% | 3/5 |
| libero_spatial_swap | 4/5 | 37.6%–96.4% | 4/5 |
| libero_spatial_task | 2/5 | 11.8%–76.9% | 4/5 |

私有规则unknown：libero_10_task_t3_s40, libero_10_swap_t3_s40。这两局仍实际执行原生整句回放并计入40局整局分母；未编私有子任务标签。

本批采样成功、独立回放失败5局：goal_swap_t2、goal_task_t3、spatial_swap_t4、object_swap_t4、goal_task_t2。它们保留在逐局表中，不按采样结果代替回放得分。

[逐局同表](oracle_retry40_comparison.md)；[逐次引用与技能统计](oracle_retry40_cases.jsonl)；[完整汇总与源码](oracle_retry40_manifest.json)。源码快照fb9b386542e01d9eb510146decc6c284051dba8a；仅D2开发评测，不进训练。

补充：[首次回放起点比对](oracle_retry40_initial_comparison.json)在初始公开请求之后比较完整物理哈希，新旧0/40相同。这不是原始root pickle或模型/A1的初态等价检验，仍不作因果配对结论。
