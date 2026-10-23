v-next-b闭环已全部完成：D2为10/40，原版为1/6；两者均未超过只用π的18/40、6/6。
全部46臂在开跑前恢复与纯π相同的完整物理初态，每条请求显式human_available=false，运行选择不使用oracle。
合法集由4换成5，同时引入schema7人类能力字段、扩展候选编码和32k长度上限，因此差额不能只归于权重。

| D2方法 | 成功 | 95% Wilson |
|---|---:|---:|
| 只用π，失败重试一次 | 18/40 | 30.7–60.2% |
| v-next-a，旧合法集4 | 10/40 | 14.2–40.2% |
| v-next-b，合法集5 | 10/40 | 14.2–40.2% |
| 开局oracle独立回放 | 24/40 | 44.6–73.7% |
| A1-M | 28/40 | 54.6–81.9% |

| 场景 | 只用π | v-next-a | v-next-b | 开局oracle | A1-M | 决策数 | 仿真步 |
|---|---:|---:|---:|---:|---:|---:|---:|
| libero_10_swap_t0_s40 | 0 | 0 | 0 | 1 | 1 | 2 | 1072 |
| libero_10_swap_t1_s40 | 0 | 0 | 0 | 1 | 0 | 2 | 1083 |
| libero_10_swap_t2_s40 | 0 | 0 | 0 | 0 | 1 | 5 | 798 |
| libero_10_swap_t3_s40 | 0 | 0 | 0 | 0 | 0 | 3 | 459 |
| libero_10_swap_t4_s40 | 0 | 0 | 0 | 1 | 1 | 2 | 260 |
| libero_10_task_t0_s40 | 0 | 0 | 0 | 1 | 1 | 2 | 1230 |
| libero_10_task_t1_s40 | 1 | 0 | 1 | 1 | 1 | 1 | 331 |
| libero_10_task_t2_s40 | 1 | 1 | 0 | 0 | 1 | 3 | 558 |
| libero_10_task_t3_s40 | 0 | 0 | 0 | 0 | 0 | 2 | 131 |
| libero_10_task_t4_s40 | 0 | 0 | 0 | 1 | 0 | 2 | 256 |
| libero_goal_swap_t0_s40 | 0 | 0 | 0 | 0 | 0 | 2 | 152 |
| libero_goal_swap_t1_s40 | 1 | 0 | 1 | 1 | 1 | 1 | 101 |
| libero_goal_swap_t2_s40 | 0 | 0 | 0 | 0 | 0 | 2 | 992 |
| libero_goal_swap_t3_s40 | 1 | 0 | 1 | 1 | 1 | 1 | 176 |
| libero_goal_swap_t4_s40 | 0 | 0 | 0 | 0 | 1 | 2 | 166 |
| libero_goal_task_t0_s40 | 0 | 0 | 0 | 0 | 1 | 4 | 571 |
| libero_goal_task_t1_s40 | 1 | 1 | 1 | 1 | 1 | 1 | 166 |
| libero_goal_task_t2_s40 | 1 | 0 | 0 | 0 | 1 | 2 | 143 |
| libero_goal_task_t3_s40 | 0 | 0 | 0 | 0 | 0 | 2 | 128 |
| libero_goal_task_t4_s40 | 1 | 0 | 1 | 1 | 1 | 2 | 407 |
| libero_object_swap_t0_s40 | 1 | 1 | 0 | 1 | 1 | 2 | 95 |
| libero_object_swap_t1_s40 | 1 | 0 | 1 | 1 | 0 | 2 | 161 |
| libero_object_swap_t2_s40 | 1 | 1 | 1 | 1 | 1 | 1 | 129 |
| libero_object_swap_t3_s40 | 0 | 0 | 0 | 1 | 1 | 2 | 130 |
| libero_object_swap_t4_s40 | 0 | 0 | 0 | 0 | 1 | 2 | 532 |
| libero_object_task_t0_s40 | 1 | 1 | 1 | 1 | 1 | 1 | 100 |
| libero_object_task_t1_s40 | 1 | 1 | 0 | 1 | 1 | 26 | 2245 |
| libero_object_task_t2_s40 | 0 | 0 | 0 | 1 | 0 | 2 | 257 |
| libero_object_task_t3_s40 | 0 | 1 | 0 | 0 | 1 | 2 | 754 |
| libero_object_task_t4_s40 | 1 | 1 | 1 | 1 | 0 | 1 | 136 |
| libero_spatial_swap_t0_s40 | 1 | 1 | 1 | 1 | 0 | 4 | 372 |
| libero_spatial_swap_t1_s40 | 1 | 0 | 0 | 1 | 1 | 2 | 129 |
| libero_spatial_swap_t2_s40 | 1 | 1 | 0 | 1 | 1 | 3 | 481 |
| libero_spatial_swap_t3_s40 | 0 | 0 | 0 | 1 | 1 | 2 | 148 |
| libero_spatial_swap_t4_s40 | 1 | 0 | 0 | 0 | 1 | 2 | 536 |
| libero_spatial_task_t0_s40 | 0 | 0 | 0 | 0 | 1 | 12 | 1556 |
| libero_spatial_task_t1_s40 | 1 | 0 | 0 | 1 | 1 | 2 | 376 |
| libero_spatial_task_t2_s40 | 0 | 0 | 0 | 1 | 1 | 2 | 787 |
| libero_spatial_task_t3_s40 | 0 | 0 | 0 | 0 | 0 | 6 | 855 |
| libero_spatial_task_t4_s40 | 0 | 0 | 0 | 0 | 1 | 4 | 1261 |

| 原版臂 | 只用π | v-next-b | 停止原因 |
|---|---:|---:|---|
| bowl_transfer_libero_spatial_t0_s17_K1 | 1 | 0 | failed_chunk_recovery_budget |
| bowl_transfer_libero_spatial_t0_s17_K4 | 1 | 0 | failed_chunk_recovery_budget |
| box_transfer_libero_object_t0_s0_K1 | 1 | 0 | environment_reports_task_incomplete |
| box_transfer_libero_object_t0_s0_K4 | 1 | 1 | native_success |
| cup_transfer_libero_10_t4_s0_K1 | 1 | 0 | failed_chunk_recovery_budget |
| cup_transfer_libero_10_t4_s0_K4 | 1 | 0 | failed_chunk_recovery_budget |

原版6臂是3个独立初态分别按K1/K4运行，不能当作6个独立布局。新模型原版1/6的Wilson区间为3.0–56.4%，纯π6/6为61.0–100%。

原服务11688没有修改。原始120编码/16k请求产生的接口错误尝试全部保留，闭合重跑使用同一adapter；扩展编码保留前120项映射，增加136个验证为单token的字符，不删候选。只取消自有副本11709/11713。原件引用、每局初态SHA、实际服务版本及四段时延保留在paired_cases.jsonl与original6.jsonl。
