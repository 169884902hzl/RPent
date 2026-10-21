严格 N1 的 32 个登记位置均闭合；任务指标仅含 30 个整局位置，另 2 个 VLA continuation pilot 单列。

基线 6a2d6bb8+D3：25/30；645c4d22：7/30。改善 1，退步 19。不能据此宣称精度不变。

| 每决策墙钟（秒，中位数） | 基线 | 645 |
|---|---:|---:|
| 感知 | 18.866 | 7.488 |
| 候选 | 63.403 | 9.268 |
| 决策（含 oracle 后续合法集） | 14.717 | 3.284 |
| 执行 | 4.327 | 1.084 |
| oracle 后续合法集（已含于决策） | 14.548 | 2.850 |
| 完整循环 | 104.276 | 21.131 |

实际循环数 111 / 257，各列中位数不可相加。整局中位 333.929 / 235.047 秒。每对完整积分、控制器和 RNG 初态均从实际保存的物理 pickle 独立重算 digest，并核对刷新前后不变。

| 类别 | 基线成功 | 645 成功 | 回合数 |
|---|---:|---:|---:|
| bowl_transfer | 7 | 6 | 8 |
| container | 8 | 0 | 8 |
| stove_on | 7 | 0 | 8 |
| libero_spatial_swap | 1 | 1 | 1 |
| libero_object_swap | 1 | 0 | 1 |
| libero_spatial_task | 0 | 0 | 1 |
| libero_object_task | 1 | 0 | 1 |
| libero_goal_swap | 0 | 0 | 1 |
| libero_goal_task | 0 | 0 | 1 |

完整逐状态、逐决策四段时延和源文件 SHA：
`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/schema6_20261020/cpu/N1_strict_645c4d22_C7_r3/`

11025 原始 cProfile 中 build_obstacles 为 6 次 / 2.598 秒，_cloud_and_ik 为 96 次 / 79.897 秒，_instance_pixels 为 48 次 / 58.447 秒。累计时间嵌套，不能相加；_cloud_and_ik 次数不等于障碍索引构建次数。

这份结果属于 645，不属于新 B2 D2 源。3f 仅保留 8 个闭合位置，因复现容器 lift 与灶台接触筛查回退而停止余下开发运行；不会把该部分结果叫成完整 32 状态提速。
