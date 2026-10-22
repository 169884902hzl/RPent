| 局 | π调用 | 实际动作块 | 同工具同提示重试下界 | 其他动作 |
|---|---:|---|---:|---|
| libero_spatial_swap_t4_s40 | 1 | [8] | 0 | {'move_to': 4, 'set_gripper': 1, 'release': 1} |
| libero_spatial_task_t0_s40 | 2 | [9, 8] | 0 | {'move_to': 4, 'set_gripper': 1, 'release': 1} |
| libero_spatial_task_t4_s40 | 2 | [8, 4] | 0 | {'move_to': 6, 'set_gripper': 1, 'release': 1} |
| libero_object_swap_t3_s40 | 2 | [8, 8] | 0 | {'move_to': 2, 'set_gripper': 1} |
| libero_object_task_t3_s40 | 1 | [16] | 0 | {'move_to': 1} |
| libero_goal_task_t0_s40 | 1 | [19] | 0 | {'move_pose': 1} |
| libero_10_swap_t0_s40 | 2 | [14, 14] | 0 | {'move_to': 10, 'set_gripper': 2, 'release': 1} |
| libero_10_swap_t2_s40 | 6 | [24, 16, 24, 20, 25, 22] | 1 | {'move_to': 14, 'set_gripper': 3, 'rotate_pitch': 1, 'release': 1} |
| libero_goal_swap_t4_s40 | 1 | [7] | 0 | {'move_to': 5, 'set_gripper': 1} |
| libero_object_swap_t4_s40 | 1 | [20] | 0 | {'move_to': 1, 'release': 1} |
| libero_goal_task_t2_s40 | 1 | [16] | 0 | {'move_to': 1} |
| libero_10_task_t2_s40 | 4 | [20, 8, 10, 8] | 1 | {'move_to': 11, 'set_gripper': 2, 'release': 2} |

旧记录保存动作块数，没有逐控制步 ledger；π的精确控制步数记为缺测，不用块数乘配置伪造。12局开局公开EEF误差均≤1e-9 m；没有A1完整积分/控制器/RNG快照，完整初态相同尚不能认证。
