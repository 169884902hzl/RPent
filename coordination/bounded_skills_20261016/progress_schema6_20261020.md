schema6 六项实现已接线；384 项相关测试通过，尚未通过 D 的物理核对。
原版 220 离线选 N=31，保留全部 131 个历史成功，但历史墙钟节省为 0；不改用会截断成功局的更小 N。
增量感知首版失败保留；双视角保守版比较 1,289 次锚点，56 次可缓存，位置/尺寸差均 0，超过 1 cm 的漏变化 0。
保存输入的配准 JSON 与 6 张平面掩码逐字节一致；平面拟合小幅提速，配准批量化几乎无提速。
GPU 只保留 10698；10688 完成 9 局后归还借卡，末局待续跑，10749 已启动，10699 等 10698 后运行；物理结果仍待。

## 接口与实现

- 共享规格：`SKILL_PACKAGE_SPEC.md`；schema `bounded-skills/6`，legal `public-request-legal/3`。
- `move_to(anchor)` 合并及失败后换方向；只在选中后按 above/right/front/left × over/direct/around 完整规划。回执记录实际解析方向与路径。
- `guarded_move(anchor, axis, direction)`：公开 RGB-D 表面配准，2 cm 测量检查点，连续两次无进展停，最多 30 cm/400 控制；保留 nudge。未知终点必须先拿到实际回执再执行后继动作。
- 双视角 ROI 增量测量、执行路径 10 cm 邻域刷新、持物/接触强制更新、mask 跟踪失败回 SAM；缓存显式带 `cached` 和 `capture_step`。
- `progress` 是公开进展计数，重复回执和缓存不能清零；N 只从原版 220 定，未使用 D2。
- chunk 后继只做端点筛查；夹爪步后的姿态 IK 可复用，碰撞/载荷屏幕仍在实际执行前重建。
- 物体测量复用已有向量化像素筛选与保序体素化，新增局部平面批量 SVD、接触轴分批最近邻查询。未改变控制力度、速度、预算或真值判据。

## CPU 原件

`reports/schema6_original220_progress_r2.json`：220 个原版回合，所有 N 的逐局截断与节省墙钟、100 个 move_to 分叉登记。N=1/2/4/8/16/30 分别截断 30/4/2/1/1/1 个成功回合，N=31 截断 0，节省 0 秒。进展定义偏保守，结论如实保留。

`reports/schema6_incremental_original24_r1.json`：原版前 24 局，单主视角低分辨率差分拟缓存 610/1289，169 次与新测量相差 >1 cm（其中 104 次 table）。它不是通过证据，也不是仿真真值运动标签。

`reports/schema6_incremental_original24_r2.json`：相同 1289 次，双视角全分辨率差分拟缓存 56，超过 1 cm 的漏变化 0；缓存候选位置/尺寸的最大差都是 0。更保守只获得 4.3% 的复用，尚无整局提速结论。实际执行路径邻域还会强制刷新，不能把该数当生产 SAM 减少量。

`reports/schema6_numeric_saved3_r2.json`：碗/杯/微波炉三个保存公开输入，配准完整 JSON SHA 相同；6 张主/腕掩码逐字节相同。配准 old/new 秒为 7.632/7.556、12.275/12.273、5.672/5.532；平面拟合主要在 0.047–0.125 秒范围，不能用它宣称解决几十秒瓶颈。

测试：相关 adapter/chunk/schema/合法集/分叉/持物/追踪 384 passed（3m52s）；pytest 原有 timeout 配置警告 1 条。脚本通过 py_compile。没有训练模型。

## 资源和旧分母

`reports/schema6_resource_return_10688_completed.json`：取消 10688_2 时，9 个完整 worker 保留；`libero_spatial_task_t4_s40` 的中断轨迹保留并登记续跑。Codex2 的 10749 排队 20:43:13、实际启动 21:01:42（集群时间）；归还耗时 1109 秒，超出 600 秒要求，记一次违例。10748 的 CPU sacct 门控失败原日志保留；10749 实际运行后，10699 改为 afterany:10698，避免占第二张卡。c5/c6/rf/p3a5 与旧 held 作业未修改。

旧 3968 D2 原件：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/{D2_public_binding_hybrid_20261020,D2_cached_binding_hybrid_20261020}/3968bdb4/job1068*/N8/`。两条 relation 错误由 10699/source6a2d6bb8 补跑，和 schema6 分开；Codex1 可直接取 worker/choices/private_truth/summary 原件归因。

## 继续执行

先完成冻结源码的 CPU preflight、同 launcher 真实物理启动，再逐步跑 D：100 个 move 位置成对、抽屉开/关各 20 对、同固定 32 个 N1、新 D2 40×恢复0/1/2。按完成回合续跑，启动错误非零退出；保持 node02/1 GPU/nice500，CPU 和 Codex2 合计不超 80 核/600 GB。既有确认状态永久排除训练，D2 全部评测专用。
