Codex1 / Codex2：时间分解更新为14个闭合回合、7个同状态新旧chunk规则配对（source b6cf6d0）。5对均成功、2对均失败，无改善或退步成功翻转；剩余plate_push尚未闭合。开抽屉墙钟920.580/823.929秒（新/旧），退步96.651秒；保留，不把决策减少解释成稳定加速。完整加法分解见reports/wall_time_self_filter_pairs_20261018.{json,md}，不可叠加执行内感知和总感知。

CPU热点改动：complete_instance_boundary只在大图的稀疏新增边界重测邻域，小图和稠密新增区域保留全帧扫描。仍是同步四方向、同样双内点/深度连续性判据，mask及逐轮新增像素回执不变。20组合成+4组保存公开RGB-D逐像素与完整evidence均精确相同；299个相关CPU测试通过。真实1024图全部测量种子：主视角1.194→0.411秒，腕部0.141→0.104秒。诊断构造的半图种子8.619→2.719秒、5.973→1.809秒，分别标注为构造负载，不是原运行调用。小图64×80条带0.0132→0.0151秒，随机大图近持平，均如实保留。

证据：reports/boundary_frontier_CPU_validation_20261018.json、boundary_frontier_runtime_public_CPU_20261018.json、boundary_frontier_runtime_synthetic_CPU_20261018.json。尚无此性能改动的整局速度结果。schema仍bounded-skills/3，不改回执写法或测量门槛，不训练。

原版扩展批8870新增碗状态2已失败：lift后carry_to被两颗公开深度像素触发手指碰撞，后续扫描也被拒；状态3在lift途中被一颗手指附近像素挡住。正在逐像素核对归属，不删失败、不放宽碰撞门槛。关微波炉修复8991、新滚动接触修复8992 startup继续物理运行。node02按当前授权借用4卡，Codex2回来即降后续并发到≤3；保护其他项目与held作业。
