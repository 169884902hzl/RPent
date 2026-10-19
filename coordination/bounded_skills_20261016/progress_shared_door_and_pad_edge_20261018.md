# 10/18：公开门身份修复、盒子复测及五项答复

1. 10:05 的五项均有结论：profile 已定位主要函数；碗 init2 双臂修复成功；CPU 前缀接口可补有匹配上下文的位置；候选目录顺序无语义；详细回执保留最近 3 条。
2. 微波炉身份分裂已在六个保存请求上复现并修正：同一当前门面因文件 SHA 不同被当成两个实例。CPU 274 项通过，逐相机 ID 补充检查 14 项通过；物理关门效果待测。
3. 盒子 5e1c8fc 的两状态完整结果为 1/2；init1 失败保留。ee42501 的同 launcher 启动 9509_1 已执行 193 tick，完整复测 9510 已提交，尚不作成功率结论。
4. 旧源微波炉关门 9504_120 与旧盘子 9248_19 均已失败关闭；盘子新源和微波炉开门仍未关闭。新旧源分别统计，不冻结、不训练。
5. Codex3 继续同状态物理复测和类别上限；Codex1 核分母与 SHA；Codex2 使用匹配源码及保存上下文的前缀接口。

## 一次决策的耗时在哪里、能怎么缩短

函数 profile 原件为 `reports/profile_saved9024_120_CPU_20261018.json`；前十五项、调用数及解释在 `progress_prefix_judge9_and_door_identity_20261018.md`。代表请求 46.782 秒，主要嵌套项为 `_surface_contact_plan` 18.913 秒、`_cloud_and_ik` 17.987 秒、`SmoothMotion.prepare` 14.917 秒；累计项不能相加。单次 refresh 5.821–7.481 秒，原来的 35–40 秒是一次决策中重复刷新累计，不能误报成单次分割。

同捕获的分割像素、去机器人点云、目标扣除、同位姿 mesh 检查可以缓存，已有几何和请求一致性证据。跨捕获的移动障碍不能沿用。当前 IK 共用 last_solution 和暖启动，逐候选独立进程会改变数值，未启用。固定输入后的双视角纯几何可以独立计算，但没有保序实测速比，不能宣称已经实现并行加速。RPC 的客户端 profile 尚未隔离 SAM kernel。

完整盒子 init0（9507_0）互斥主线程时间：规划/后果 103.683 秒、分割 53.264 秒、实体测量 56.447 秒、深度 0.654 秒、图像/状态传输 11.190 秒、步进/渲染 8.122 秒、oracle 本身 0.088 秒，总墙钟 249.743 秒。无 π0.5。oracle 内的预测规划已归规划，不重复计入决策。

## 碗、离线标注、顺序、回执：直接答案

碗 spatial0/init2 是公共持物下沿被误当静态障碍，新旧规则共同受影响。同命令 9022_2 两臂均原生成功、260 步；新规则 3 决策/356.706 秒，旧规则 5 决策/435.904 秒，不再归为 chunk 新规则回归。

`robots.libero.bounded_offline_labels.annotate_prefix(state, request, prefix)` 不执行仿真、不请求 RPC。legal 来自公共 `legal_after`；acceptable 来自 oracle 在前缀预期回执成立条件下的预测状态，**不是物理分支成功标签**。匹配的 judge10 实际请求三个 oracle 位置 legal/acceptable/selected 零差异，另一合法 nudge 前缀可标。Codex2 可以补具有精确匹配测量上下文的新 unknown；历史 26 请求/59 unknown 缺少该上下文，仍为 unsupported，不能借用另一状态补。

spec 明确候选目录数组顺序没有语义；模型端可置换，但候选 ID 及其字段必须一起移动。决策里的 ID 序列仍决定执行顺序。源端保留最近 3 条详细回执，不按任务目标筛历史。公共合同仍为 bounded-skills/3、public-request-legal/2。

## 微波炉：根因、代码修改和证据界限

9504_120 已关闭：16 决策、770 仿真步、1639.635 秒，failure_phase=perception。实际推进过门，之后接触与身份丢失，不是“完全没有推动”，也没有关好。仅诊断的原始状态恢复显示关节从 -1.50155 到 -0.79601 rad，释放后约 -0.78934，所有采样 task_success=false；私有关节不进入运行时。

`v5_fixture_parts.measured_microwave_parent_groups` 原来要求同一当前门点云的文件 SHA 完全相同。在 row2/3/7/8/9/10，e98/e54 两个父实体的门面实际重合，但 SHA 不同，旧逻辑全部返回空集合。新逻辑用当前独立测得门像素的点集 IoU：1 µm 数值相等、去重后至少 60 点，IoU≥0.7，沿用类别 mask 的关联阈值；原父实体的间隙、高度和尺寸限制继续生效。六次原始请求的 IoU 依次为 0.833464、0.808856、0.731375、0.735577、0.769176、0.743755，新逻辑全部识别同一组。

`MeasuredScene._consolidate_microwave_parents` 保留最先建立的父实体及门 ID；当前测量别名可以刷新原门的几何、各相机点云和 object_id，不让在接触中的原绑定悬空。旧帧、仅仅接近但不重合的点、重合不足和重复像素不足均不建立新身份。该修复只管感知身份，没有新增完成判据。

证据：`reports/microwave9504_shared_surface_CPU_20261018.json`、`reports/microwave9504_shared_identity_replay_CPU_20261018.json`、`reports/shared_door_identity_cpu_validation_20261018.json`、`reports/microwave9504_private_progress_CPU_20261018.json`。

已普通推送 harness-v5，commit `452e7751cc73a60d21e70660726b278a86522392`。不可变快照 `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_shared_door_20261018_452e775`，archive SHA256 `27797b90f32d9f0d62e22fba0c59ccc03e27fa04d54e6498fe4d9ae3c12b6e26`。入口 `scripts.probe_bounded_feasibility:episode`，解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。schema SHA256 `df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa`；登记状态/任务未改，CPU preflight 退出 0。物理启动仍须同快照同 launcher 通过后才放完整数组。

## 盒子与盘子：物理结果分开保留

| 同一原版状态 | 旧 ec89f74 / 9472 | 5e1c8fc / 9507 | 新决策 | 新仿真步 | 新墙钟秒 |
| --- | --- | --- | ---: | ---: | ---: |
| cream-cheese init0 | false | true | 2 | 409 | 249.743 |
| cream-cheese init1 | false | false | 8 | 291 | 436.240 |

开发失败子集上改善 1、退步 0，不据此估计类别总体。init0 的实际 chunk 长度 [3,4]，全部 7 动作 verified。init1 没有可行 grasp plan，最后无选项。ee42501 增加完全落在公共指垫边界内的 2 mm 接触单元（中心距前边界 1 mm），原候选和完整闭合/路线/IK 检查保留；不改间隙、力、速度或预算。CPU 260 项通过，严格全开度回归 8 项通过。9509_1 是 193 tick 的真实启动证据，不是完整任务结果；9510 才是完整 0/1 两状态复测。

盘子 9502_160 保存状态的私有 forward/contact 诊断没有发动作，恢复误差均为 0。row2/19 的指尖接触法向 z 分量为 0.9797/0.9475，主要仍为上表面；row3、5、10 无指尖接触，最近距离分别约 0.136、4.286、33.968 mm。公开 RGB-D row3 的 15 条有效轨迹近零位移，确实没有推动。不能用这份接触诊断生成控制坐标。

刚体光流仅是诊断：3 mm 残差、至少 8 inlier、70% 支持时，盘子首次运动 4/11 不支持刚体拟合；后一次静止 14/15 支持。微波炉首次 10/16 不支持，第二次 20/26 支持。腕部缺少有效角点，未部署为运行时验证器，未降低阈值。证据 `reports/plate9502_contact_private_CPU_20261018.json`、`reports/contact_feature_tracks_CPU_20261018_r2.json`、`reports/contact_rigid_tracks_CPU_20261018.json`。

## 原版上限的固定快照

ec89f74 / 9248 在 16:57:08 PDT 捕获的已完成前缀为 25/32；注册 220 状态未跑完。修复源不混进此分母；can 类此前登记名为 box，已按实际 alphabet-soup 罐子纠正，不能代替真实盒子。

| 类别 | 成功/已完成 | Wilson 95% |
| --- | ---: | --- |
| bowl_transfer | 4/4 | [0.510,1.000] |
| can_transfer | 4/4 | [0.510,1.000] |
| container | 4/4 | [0.510,1.000] |
| cup_transfer | 2/3 | [0.208,0.939] |
| drawer_close | 4/4 | [0.510,1.000] |
| drawer_open | 2/3 | [0.208,0.939] |
| microwave_close | 0/1 | [0.000,0.793] |
| microwave_open | 0/1 | [0.000,0.793] |
| plate_push | 0/2 | [0.000,0.658] |
| stove_off | 2/3 | [0.208,0.939] |
| stove_on | 3/3 | [0.439,1.000] |

原件 `reports/original20_support_interim_r4_20261018.json`。这是未完成前缀的描述区间，不是类别准入。两个已关闭的独立对照仍为 π0.5-only 215/220、v5 专家不用 vla_task 197/220，保留各自固定源与分母。

资源控制器持续检查 aggregate 并发与 Codex2 队列，只用 node02/nice500；不动保护或旧 held 作业。开合与盘子仍在开发修复阶段，摩卡壶和 spatial 的 v5 旧结果不冒充本技能包结果。确认状态永久排除训练。
