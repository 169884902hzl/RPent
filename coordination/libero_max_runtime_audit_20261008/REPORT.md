# LIBERO-MAX 接入只读审计

此报告只读代码，没有跑 MAX、读取策略成绩或把 MAX 用例用于训练。MAX checkout 为 `a1e3cef258b3e00487db5282aef4e36010aaf401`；技能确认作业优先。以下代码位置均相对本仓库。

| 核对项 | 代码位置 | 当前结论 |
| --- | --- | --- |
| 脚本运动中止和观测 | `robots/libero/tools.py:333`；`robots/libero/v5_runtime.py:2152` | `move_to` 每步更新本体/环境观测并检查原生终止，但不重新分割实体，也没有环境变化中断条件。单段最多 80 控制步；`move` 可再执行最多 8 个平移中间段和最后一段，即上限 720 控制步，不能把 80 当整项技能上限。 |
| π0.5 接触中止 | `robots/libero/tools.py:151`；`robots/libero/v5_runtime.py:1793` | 每块重新做 π0.5 推理、块末更新图像/本体；整块通过 `chunk_step` 执行，客户端不能在块中取消。4499 实测每块 5 控制步；具体上限应随实际 checkpoint/服务配置登记。公开停止回调在块后检查，未启用回调时不会每块重新分割场景。 |
| 完整子任务 | `robots/libero/v5_runtime.py:3311` | `vla_subtask` 使用同一逐块循环；它允许多块连续执行，planner 在整个宏动作结束前不会重选。π0.5 的逐块图像观测不等于 planner 或缓存实体刷新。公开 endpoint 回调的采样频率另受配置控制。 |
| 目标缓存与发现延迟 | `robots/libero/v5_runtime.py:262`、`:2767`、`:2928`、`:3344` | 感知只刷新请求的类别；抓取前保存静止目标，放置会继续用缓存。没有 TTL 或全场景变化检测，外部移走缓存目标后发现时间没有固定上界，可能一直使用旧目标。漏检缓存会标记 `cached_perception`，但这不能证明位置仍然有效。 |
| 相机移位与真值标定 | `robots/libero/tools.py:975`、`:1035`、`:1128`、`:1171`；`robots/libero/env_server.py:267` | world map 直接使用服务返回的 `extrinsic_cam2world`。实际 RLinf `libero_env.py:664` 转交 worker 的 simulator camera metadata；MAX `libero_backend.py:246` 改相机模型位置/姿态。必须单独登记该标定来源：动态读取可能得到移位后的真实标定，不能当作机器人自己估计。worker 的矩阵计算仍需在接入包中逐文件固定并核对。 |
| 光照、主题、噪声 | `robots/libero/v5_stove_measurement.py:153`；`robots/libero/v5_runtime.py:287` | 灶台红色比例依赖固定通道强度/比例/差值和测量支持面；光照与颜色变化可影响判定。SAM 用同一开放词表和 RGB 查询，没有此三类扰动的准确率证据。当前只能确认缺测会保留 unknown，不能宣称鲁棒或已证明必定失败。 |
| 脚本避障 | `robots/libero/tools.py:333`；`robots/libero/v5_runtime.py:2558` | 原始 servo 是轴向裁剪后的直达 delta；harness 会按已测家具边界抬高/平移，属于局部净空规则。没有通用碰撞规划、未测新障碍物检测或动态重规划，不能称为避障规划器。 |

## 接入方案

依据 `external_readonly/libero_max_audit_20261007/docs/RUNTIME_INTEGRATION.md` 和 `scripts/run_xvla_persistent_shard.py:221`：Plus/PRO 分进程、相同 init/策略种子、Dynamic 在事件之前逐控制步重放 Base 动作，保留初态和动作前缀一致性检查。X-VLA 在 `:289` 选择前缀重放，`:314` 以后才从新观测重新推理；本 harness 还必须记录所有 script、hold、release 控制步，不能只重放 π0.5 块。

最小实现由环境 worker 包装 `CosmosInterventionEnv`，保持标准 `step/chunk_step` 合同，并保存 Base 的控制流和 harness 内部快照：实体 ID/感知缓存/held/目标缓存/回执/卡片步/失败计数。恢复 Dynamic 时先恢复同一前缀内部状态，再接收当前公开观测。事件私有元数据只给诊断账本；不能用事件类型、目标新真值位置或成功谓词替 planner 清缓存、选动作或终止。缓存失效须来自新鲜 RGB-D 测得的实体变化；若要统一事件通知，需先登记所有对照的通知合同。

相机对照应仅冻结发生移位的固定外部相机开局标定；腕部相机正常随机器人运动的运动学不能被误当作 MAX 相机漂移。MAX 也可能修改 FOV，需同时记录内参版本，不能只冻结一个矩阵便声称已消除标定优势。

预估实现 1–2 个开发日：worker/逐控制步前缀适配约半天，内部状态重放及两条实际配对启动约半天，相机标定开关和显式逐局汇总约半天至一天。这个估算不包含 Plus/PRO 依赖安装或 GPU 排队。160 对、两组共 640 回合；相机 20 对的附加标定对照再增加 40 回合。GPU 时间待同源实际两对启动测量后按中位数/P90估计，不用现有 LIBERO 结果虚构 MAX 耗时。

抽样仍待登记：按 8 类事件每类 20 对，在任何策略结果读取之前冻结 case ID、抽样种子与 manifest SHA。最终须保留未触发事件、正常任务失败及四种配对结果；按 Base/Dynamic 成功率、配对差值与 bootstrap 95% 区间报告。MAX 的 PRO/Plus 用例及文本与训练、手册、memory 完全隔离。最多占 2 卡，不挤占技能确认。

本报告没有宣称 MAX 接入、160 对抽样或物理评测已完成。
