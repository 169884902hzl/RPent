# 原版 90 状态执行修复重测

90 个原版 train 子任务状态全部闭合，450 次分叉无程序退出错误。
自有技能 48/180，请求 initial_pose 的 π0.5 为 146/270（部分实际回退原地）；重复状态不能作为独立整局成功率。
本批只替换新请求上下文上的 self / initial_pose 测量，旧 in_place / full_task 标签不能搬到新上下文。
已写入 Codex2 共享登记；消费者核验为 47 ok、23 unknown、20 ceiling_outside。407 次尝试可绑定到原请求，43 次仍保留 unknown；6 个状态有绑定覆盖问题。

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

实际调用口径：请求 initial_pose 不代表实际 initial_pose。24 个已绑定的 π 分支实际执行了 in_place 回退；标签按实际 candidate 参数统计，后续修复将补测受影响的 8 个状态。不得把全部270次称为已执行回开局姿态。

正式包和数据 SHA、消费者 SHA、替换范围见 `C2_delivery.json`。
