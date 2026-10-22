# 原版 90 状态执行修复重测

90 个原版 train 子任务状态全部闭合，450 次分叉无程序退出错误。
自有技能 48/180，回开局姿态 π0.5 为 146/270；重复状态不能作为独立整局成功率。
本批只替换新请求上下文上的 self / initial_pose 测量，旧 in_place / full_task 标签不能搬到新上下文。
消费者核验和正式交付尚在进行。

源码树 `9716b68c434c19519a8247b2ef69ce516fe9849c`；作业 11258 三片均 COMPLETED 0:0。

| 类别 | 方法 | 成功/尝试 | Wilson 95%（重复试次口径） | 零控制次数 |
|---|---|---:|---|---:|
| bowl_transfer | call_vla | 19/30 | 45.5%–78.1% | 0 |
| bowl_transfer | self | 16/20 | 58.4%–91.9% | 0 |
| box_transfer | call_vla | 12/30 | 24.6%–57.7% | 15 |
| box_transfer | self | 4/20 | 8.1%–41.6% | 0 |
| container | call_vla | 15/30 | 33.2%–66.8% | 15 |
| container | self | 8/20 | 21.9%–61.3% | 0 |
| cup_transfer | call_vla | 17/30 | 39.2%–72.6% | 0 |
| cup_transfer | self | 20/20 | 83.9%–100.0% | 0 |
| drawer_close | call_vla | 15/30 | 33.2%–66.8% | 15 |
| drawer_close | self | 0/20 | 0.0%–16.1% | 0 |
| drawer_open | call_vla | 19/30 | 45.5%–78.1% | 9 |
| drawer_open | self | 0/20 | 0.0%–16.1% | 0 |
| microwave_close | call_vla | 23/30 | 59.1%–88.2% | 0 |
| microwave_close | self | 0/20 | 0.0%–16.1% | 0 |
| microwave_open | call_vla | 26/30 | 70.3%–94.7% | 3 |
| microwave_open | self | 0/20 | 0.0%–16.1% | 6 |
| plate_push | call_vla | 0/30 | 0.0%–11.4% | 30 |
| plate_push | self | 0/20 | 0.0%–16.1% | 0 |

逐状态、每次种子、停止原因、控制步数、原件 SHA 见 `closed90_raw_summary.json`。
已关闭确认批不重跑、不改判；本批未执行训练。
