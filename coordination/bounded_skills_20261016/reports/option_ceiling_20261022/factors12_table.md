| 局 / 子任务 | 基线 | A1提示 | A1预算/停止 | RPen原语 |
|---|---:|---:|---:|---:|
| libero_spatial_swap_t4_s40 / g0:pick | 0/3 | 1/3 | 1/3 | 0/3 |
| libero_object_swap_t3_s40 / g0:pick | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_10_swap_t0_s40 / g0:pick | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_object_swap_t4_s40 / g0:in | 0/3 | 0/3 | 0/3 | 3/3 |
| libero_spatial_task_t0_s40 / g0:pick | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_object_task_t3_s40 / g0:pick | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_10_swap_t2_s40 / g1:pick | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_goal_task_t2_s40 / g0:on | 3/3 | 3/3 | 3/3 | 3/3 |
| libero_spatial_task_t4_s40 / g0:pick | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_goal_task_t0_s40 / g0:open | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_goal_swap_t4_s40 / g0:on | 0/3 | 0/3 | 0/3 | 0/3 |
| libero_10_task_t2_s40 / g1:pick | 0/3 | 0/3 | 0/3 | 0/3 |

以上是私有子任务判定，整局native单列在summary.json。Rpent原语对A1预算/停止臂比较；object_swap_t4的基线为0控制、目录不可用，原语3/3也包含了绕过该入口拒绝的差异，不能独归因于接触算法。A1的笛卡尔预备移动未在这四臂中改变，另做同状态配对。
