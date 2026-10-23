| 局 | 新独立回放 | 新采样包络 | 前版回放 | 前版包络 | 模型 | A1-M |
|---|---:|---:|---:|---:|---:|---:|
| libero_10_swap_t0_s40 | 1 | 0 | 0 | 0 | 0 | 1 |
| libero_10_swap_t1_s40 | 1 | 1 | 1 | 1 | 0 | 0 |
| libero_10_swap_t2_s40 | 0 | 0 | 0 | 0 | 0 | 1 |
| libero_10_swap_t3_s40 | 0 | ? | 0 | ? | 0 | 0 |
| libero_10_swap_t4_s40 | 1 | 1 | 1 | 1 | 0 | 1 |
| libero_10_task_t0_s40 | 1 | 1 | 1 | 1 | 0 | 1 |
| libero_10_task_t1_s40 | 1 | 1 | 1 | 1 | 0 | 1 |
| libero_10_task_t2_s40 | 0 | 1 | 1 | 1 | 1 | 1 |
| libero_10_task_t3_s40 | 0 | ? | 0 | ? | 0 | 0 |
| libero_10_task_t4_s40 | 1 | 1 | 1 | 1 | 0 | 0 |
| libero_goal_swap_t0_s40 | 0 | 0 | 0 | 0 | 0 | 0 |
| libero_goal_swap_t1_s40 | 1 | 1 | 1 | 1 | 0 | 1 |
| libero_goal_swap_t2_s40 | 0 | 1 | 0 | 1 | 0 | 0 |
| libero_goal_swap_t3_s40 | 1 | 1 | 1 | 1 | 0 | 1 |
| libero_goal_swap_t4_s40 | 0 | 0 | 0 | 0 | 0 | 1 |
| libero_goal_task_t0_s40 | 0 | 0 | 0 | 0 | 0 | 1 |
| libero_goal_task_t1_s40 | 1 | 1 | 1 | 1 | 1 | 1 |
| libero_goal_task_t2_s40 | 0 | 1 | 0 | 1 | 0 | 1 |
| libero_goal_task_t3_s40 | 0 | 1 | 0 | 1 | 0 | 0 |
| libero_goal_task_t4_s40 | 1 | 1 | 1 | 1 | 0 | 1 |
| libero_object_swap_t0_s40 | 1 | 1 | 1 | 1 | 1 | 1 |
| libero_object_swap_t1_s40 | 1 | 1 | 1 | 1 | 0 | 0 |
| libero_object_swap_t2_s40 | 1 | 1 | 1 | 1 | 1 | 1 |
| libero_object_swap_t3_s40 | 1 | 1 | 0 | 0 | 0 | 1 |
| libero_object_swap_t4_s40 | 0 | 1 | 0 | 1 | 0 | 1 |
| libero_object_task_t0_s40 | 1 | 1 | 1 | 1 | 1 | 1 |
| libero_object_task_t1_s40 | 1 | 1 | 1 | 1 | 1 | 1 |
| libero_object_task_t2_s40 | 1 | 1 | 1 | 1 | 0 | 0 |
| libero_object_task_t3_s40 | 0 | 0 | 0 | 0 | 1 | 1 |
| libero_object_task_t4_s40 | 1 | 1 | 1 | 1 | 1 | 0 |
| libero_spatial_swap_t0_s40 | 1 | 1 | 1 | 1 | 1 | 0 |
| libero_spatial_swap_t1_s40 | 1 | 1 | 1 | 1 | 0 | 1 |
| libero_spatial_swap_t2_s40 | 1 | 1 | 1 | 1 | 1 | 1 |
| libero_spatial_swap_t3_s40 | 1 | 1 | 1 | 1 | 0 | 1 |
| libero_spatial_swap_t4_s40 | 0 | 1 | 0 | 1 | 0 | 1 |
| libero_spatial_task_t0_s40 | 0 | 0 | 0 | 0 | 0 | 1 |
| libero_spatial_task_t1_s40 | 1 | 1 | 1 | 1 | 0 | 1 |
| libero_spatial_task_t2_s40 | 1 | 1 | 1 | 1 | 0 | 1 |
| libero_spatial_task_t3_s40 | 0 | 0 | 0 | 0 | 0 | 0 |
| libero_spatial_task_t4_s40 | 0 | 1 | 0 | 0 | 0 | 1 |

同任务/初态编号协议；完整 A1 初态缺失。各历史臂的完整初态逐局认证状态见 comparison.jsonl，未相同的局不作因果选择错误归因。
新臂同时增加公开锚点调用、额外采样和私有登记目标续接修复；差额不能全部归于新增方法。
采样包络是从实测分支选择后的诊断，不是可部署策略的整局期望成功率。PRO/D2 只评测，不训练或调阈值。
