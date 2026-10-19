# 10/18：盒子接触修复与完整物理复测中间结果

1. 盒子 init0 从失败翻为原生成功：5e1c8fc，2 次决策、409 仿真步、249.743 秒，7 个小动作全部验证通过，π0.5 关闭。
2. 同一修复在 init1 的 CPU 复算仍被桌面闭合碰撞拒绝；物理复测未结束，不能宣称盒子类别已经修好。
3. 盘子至少一次 nudge 没有带动物体；微波炉确有毫米级表面运动，但不足以证明关门。光流目前仅用于诊断，没有进入运行时验证器。
4. 10:05 五项已有可用结论；Codex2 可补具有匹配测量快照的任意合法前缀，历史缺快照的 59 个 unknown 仍不能补。
5. Codex3 继续盒子、盘子、微波炉物理复测和类别上限；Codex1 核对分母与 SHA，Codex2 使用匹配快照接口。未训练、未冻结，确认状态永久排除训练。

## 盒子：修了哪里，证据支持到哪里

低矮物体的可测侧面若对准指垫中心，较长的手指会穿入桌面。5e1c8fc 为所有类别共用的采样器增加指垫前端接触候选：同一对公开测量的侧面接触位于两个静态指垫共同前边界内 2 mm。原中心候选、整条平滑路线、逆解和闭合扫掠全部保留；未放宽 4 mm 碰撞间隙，未改力、速度或步数预算。

同一初始状态、同一原版任务，原生成功为判定依据：

| 状态 | ec89f74 / 9472 | 5e1c8fc / 9507 | 新决策 | 新仿真步 | 新墙钟秒 |
| --- | --- | --- | ---: | ---: | ---: |
| box_grab_place_libero_object_t1_s0 | false | true | 2 | 409 | 249.743 |
| box_grab_place_libero_object_t1_s1 | false | 未结束 | — | — | — |

这是失败子集上的开发配对；当前完成一对，改善 1、退步 0，不据此估计总体成功率。init0 的新 chunk 实际执行动作数为 [3,4]，无中途截断。各技能仿真步：move_to 131、descend 47、set_gripper 15、lift 32、carry_to 146、lower 31、release 7。参考轨迹最大加速度衔接跳变 9.077e-14，最大 jerk / 上限 0.942；这是该回合的参考轨迹指标，不代替旧新执行器的完整配对。

原盒子 9472_0/1/2 的三个失败原始记录保留；其余 17 个未启动开发分片已取消，避免重复消耗已知无接触路线的配置。它们不是确认批，也没有改判。原始结果、逐技能预算和队列快照：`reports/contact_probe_interim_r1_20261018.json`，捕获于 2026-10-18 16:46:20 PDT。

未修改的 5e1c8fc 对同一保存测量复算：init0 选 s6_a2_top_distal_pad（0.859 秒）；init1 仍没有可行计划（30.293 秒）。init1 三条新候选通过路线但闭合仍碰到桌面 1–2 点；公开深度障碍 z 为约 0.75–1.01 mm，没有删除它们。CPU 证据：`reports/box_distal_pad_native_CPU_20261018.json`、`reports/box_distal_pad_closure_public_CPU_20261018.json`。CPU 可行路线不是物理成功。

## 墙钟与函数 profile 的回答

init0 完整回合的互斥主线程分桶：规划及后果 103.683 秒（41.5%）；分割 53.264 秒（21.3%）；实体测量 56.447 秒（22.6%）；深度 0.654 秒；图像/状态传输 11.190 秒；仿真步进及渲染 8.122 秒（3.3%）；oracle 本身 0.088 秒；其余为快照、文件和执行调度。没有 π0.5 调用。oracle 内的预测规划归入后果计算，不能重复相加。

函数级前十五项与调用次数见 `progress_prefix_judge9_and_door_identity_20261018.md`，原始 `reports/profile_saved9024_120_CPU_20261018.json`。一次 request 46.782 秒，主要嵌套项为 _surface_contact_plan 18.913、_cloud_and_ik 17.987、SmoothMotion.prepare 14.917 秒。一次 refresh 5.821–7.481 秒；此前 35–40 秒是同一决策内多次分割/测量累计，不能当成单次 refresh。

可缓存：同一次捕获的分割像素、去机器人点云、目标扣除、同位姿 mesh 检查；已有请求字节/几何一致性证据。不能跨捕获复用移动障碍。逐候选 IK 共用 last_solution 和暖启动，直接多进程会改变数值，未启用。固定输入后的双视角纯几何可以独立计算，但尚无保序实测速比；不宣称并行加速完成。客户端 profile 包含 RPC 等待，尚未拆出 SAM kernel 的独立耗时。

## 盘子与微波炉：测量不足和真实无进展分别保留

只读保存的 RGB-D，使用原接触表面的像素与双向 LK 一致性跟踪：

| 运行 / 动作 | 主视角有效轨迹数 | 中位三维位移 mm |
| --- | ---: | --- |
| 9502_160 / row2 首次 nudge | 11 | [2.626,8.753,-11.959] |
| 9502_160 / row3 后一次 nudge | 15 | [0,0,0] |
| 9504_120 / row1 第一次 nudge | 16 | [6.170,-1.207,-4.694] |
| 9504_120 / row1 第二次 nudge | 26 | [4.526,-0.264,-0.284] |

盘子后一次几乎没有移动；前一次存在下沉/倾斜，不能直接算成功水平推动。微波炉两个动作确有局部可见表面变化，但不等于门到达终点。腕部均无可用角点，不能声称双视角跟踪验证通过。已看主视角叠图，未据图推断未测得的接触高度或私有状态。

原诊断报告保留。r2 让图文件名带 before/after capture step，避免同一 row 两次动作覆盖图；8 条记录、4 张唯一叠图的哈希全部核对一致。证据：`reports/contact_feature_tracks_CPU_20261018_r2.json`，SHA256 `2269f7807b32d6d66d7fc9b666f59ea4cbcaf2810632048085ab1ce9d927b942`。没有修改运行时验证器或阈值。

## 前缀接口与其余三项

`robots.libero.bounded_offline_labels.annotate_prefix(state, request, prefix)` 只用 CPU，不仿真、不 RPC。legal 调用公开 legal_after；rule_acceptable 使用 oracle 的预测状态，是预期回执成立条件下的规则标签。judge10 实际请求三个 oracle 位置的 legal / acceptable / selected 均零差异，另一个构造的合法 nudge 前缀可标。缺测量上下文的历史 26 请求 / 59 unknown 仍 unsupported，不能换状态补标签。细节与耗时见 `progress_judge10_and_plate_20261018.md`。

碗 init2 根因是持物下沿被当静态障碍，新旧共同受影响；同命令 9022_2 两臂已原生成功，各 260 步，新 3 决策 / 356.706 秒，旧 5 / 435.904 秒。spec 已声明候选目录顺序无语义；决策 ID 顺序才是执行顺序。源端详细回执保留最近 3 条，不按任务目标筛历史。这三项本轮没有再改接口。

## 源码、检查和资源

运行快照 `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_distal_pad_20261018_5e1c8fc`；commit `5e1c8fcf2b6a0c982a89a6a6bd5d61eeafb03f01`；archive SHA256 `df12f955261d9cf989aca8d709f8292a9a997bd074a511397130073e4efa015d`；grasp_route SHA256 `4958c01b4176abdc10dc94dcb6589be31c12fdd46df52e543bf7bd87ca150b80`。入口 `scripts.probe_bounded_feasibility:episode`，解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。公共 schema bounded-skills/3、public-request-legal/2 未变。

接触修复相关 CPU 测试 260 passed / 156.55 秒，详细命令与原警告见 `reports/distal_pad_cpu_validation_20261018.json`。同快照同 launcher 启动 9506_0 已执行 193 个物理 tick 并正常退出，之后才放完整 9507；启动不算任务成功。

唯一资源控制器已增加独立 9502/9504 的再平衡；Codex2 GPU 排队后，也会阻止它们的后续分片继续借第四卡。只替换监控进程，没有取消物理运行；回执 `reports/distal_pad_peer_controller_replacement_20261018.json`。node02 / nice500；不动保护或 held 作业。原版类别上限未完成，任何旧源与修复源结果均分别报告。
