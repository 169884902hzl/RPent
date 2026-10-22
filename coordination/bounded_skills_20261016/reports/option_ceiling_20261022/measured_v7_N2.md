N2十二状态已全部闭合，132条旧方法逐次配对零翻转，完整初态零差异。新组合调用单列为5/36（Wilson 95% 6.1%–28.7%）。执行源码树efa57340221c82cb359d72514c7062edb34de599。

| 方法 | 原判据下成功 | 本轮同判据成功 | Wilson 95% |
|---|---:|---:|---:|
| full_task | 24/36 | 24/36 | 50.3–79.8% |
| in_place | 21/36 | 21/36 | 42.2–72.9% |
| initial_pose | 13/36 | 13/36 | 22.5–52.4% |
| self | 4/24 | 4/24 | 6.7–35.9% |

各行使用各自登记的子任务或整句判据，不能据此跨行排名。下面仅报告新增measured_anchor调用。

| 类别 | 成功 / 次数 | Wilson 95% |
|---|---:|---:|
| box_transfer | 0/6 | 0.0–39.0% |
| drawer_close | 3/6 | 18.8–81.2% |
| drawer_open | 0/6 | 0.0–39.0% |
| microwave_close | 0/6 | 0.0–39.0% |
| microwave_open | 2/6 | 9.7–70.0% |
| plate_push | 0/6 | 0.0–39.0% |

| 状态 | 旧方法：修前→本轮 | 新调用 |
|---|---:|---:|
| drawer_open_libero_goal_t0_s0_B2_d006 | 6/11 → 6/11 | 0/3 |
| drawer_open_libero_goal_t0_s0_B2_d006_layout11020608_prefix000 | 10/11 → 10/11 | 0/3 |
| drawer_close_libero_90_t0_s1_B2_d018 | 6/11 → 6/11 | 0/3 |
| drawer_close_libero_90_t0_s1_B2_d018_layout11020610_prefix000 | 6/11 → 6/11 | 3/3 |
| microwave_open_libero_90_t35_s0_B2_d009 | 4/11 → 4/11 | 2/3 |
| microwave_open_libero_90_t35_s0_B2_d009_layout11020612_prefix000 | 9/11 → 9/11 | 0/3 |
| microwave_close_libero_90_t33_s0_B2_d013 | 4/11 → 4/11 | 0/3 |
| microwave_close_libero_90_t33_s10_B2_d003_layout11020614_prefix000 | 6/11 → 6/11 | 0/3 |
| plate_push_libero_goal_t5_s0_B2_d065 | 3/11 → 3/11 | 0/3 |
| plate_push_libero_goal_t5_s10_B2_d002_layout11020616_prefix000 | 0/11 → 0/11 | 0/3 |
| box_transfer_libero_object_t0_s1_B2_d001 | 8/11 → 8/11 | 0/3 |
| box_transfer_libero_object_t0_s1_B2_d001_layout11020602_prefix000 | 0/11 → 0/11 | 0/3 |

新增调用的31条失败：预定位未完成22、无进展停止4、动作块预算耗尽5。全部保留，没有重跑换分数。区间按重复试次计算，不能当作36个独立布局的泛化区间。

原件：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022/measured_anchor_efa57340/CPU_N2/`。逐次、逐状态数据和分类汇总分别为paired_trials.jsonl、states.jsonl、summary.json。
