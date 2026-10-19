# 原版失败修复、离线并行与 D2 启动

1. 原版固定源 ec89f74：109 成功 / 136 个完整物理回合 / 220 登记，84 未完成；不是完整 220 局成绩。真盒子 20/20 单列。
2. 微波炉新路线源码 6958aefe 已推送；关门保存状态的完整路线 CPU 检查通过，实际关/开结果待 9891 startup 和完整复验。
3. 离线并行源码 16fdece3 已推送，47 项 CPU 测试通过；可选运行时 spawn 条件规划源码 7ffe2118 已推送，50 项 CPU 测试通过。三个真实保存状态的上下文、标签和选择逐字节相同，完整 oracle CPU 耗时降至原来的 54–66%；整回合仍待实测。
4. D2 启动检查改为先真实调用 call_vla，避免先耗尽一个完整自执行分支；源码 2a869b26，13 项相关测试通过。四类交还条件尚未实际测齐，正式 40 局未提交。
5. Codex3 继续 GPU 启动、失败修复和 CPU 提速；Codex1/2 已收到加锁 COORDINATION 通知。node02 被高优先级 rf 占用，未动其作业；未训练，确认状态永久排除训练。

## 源码与测量

| 变更 | commit | 证据 |
| --- | --- | --- |
| 通用非水平面板 joint-guided Cartesian 路线 | 6958aefe1ef60c8b9f92e029f308762fdadb81f7 | reports/joint_guides_cpu_20261019.json；291 passed / 226.48s |
| CPU 离线前缀可选 workers=4 | 16fdece350735430e24398df61a321f694681d0e | 47 passed / 82.36s；reports/offline_parallel_labels_CPU_20261019.json |
| D2 startup 直接探测 VLA 物理链 | 2a869b26f45b0671a70aee66136d19cbc08023be | 13 passed / 0.31s；只影响 startup 顺序，正式 self+3VLA 分叉不变 |
| 运行时可选 spawn 条件规划 | 7ffe2118dca7a74c7455b89a1ef85c9b48dcd64e | 50 passed / 96.75s；reports/runtime_spawn_oracle_CPU_20261019.json |

所有改动逐文件 add 后提交，普通推送到 user-fork/harness-v5。当前公共 schema/legality/private judge 为 3/2/13。旧记录不覆盖，不把跨源 CPU 检查当作同源标签或物理成功。

## 微波炉：根因和原判据下的新路线

9611 关门 row1 的原 16 条路线均 IK 拒绝，但各自独立接触端点 16/16 可解；开门 row20 的接触端点 0/16 可解。另 72 种入口路线为 66 IK 拒绝、6 碰撞，无通过路线。不能把独立端点解当作连续可达。

新提案只用公开当前关节、静态机器人链和同一测量接触点，按关节距离排列数值 IK 解，再转为 Cartesian 引导经过点。完整扫掠碰撞、局部连续 IK、夹爪几何、力、速度、预算均不变；只有原薄面板路线全失败才补采。关门原保存状态找到 49 个接近点和 10 个接触点，CPU 15.066 秒。`move_to` 和 `descend` 分别执行同一计划的前后段。代码没有关节执行命令，也没有私有物体坐标。

快照 `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_joint_guides_20261019_6958aefe`；归档 SHA256 `871aca20ae186821543721917c091795273cea3b8b3fabd9e234ec1b1a43ff7c`；manifest SHA256 `099800fe542a89646159d3ecb13d5d12ff739607fbc77661d2b837cb1121e5d0`。入口 `scripts.probe_bounded_feasibility:episode`，解释器远端项目 `.venv/bin/python`。真实 startup 为 9891_120；关/开完整复验应核对 manifest 下标 120/140。

## CPU 并行：实际接口配对

| 同一保存状态、同一前缀 | 串行秒 | 4 进程秒 | 完整上下文和标签字节差异 |
| --- | ---: | ---: | ---: |
| 碗 9248_0 | 15.308 | 7.538 | 0 |
| 杯 9544_124 | 29.773 | 11.833 | 0 |
| 微波炉 9611_120 | 14.530 | 6.351 | 0 |

此表是完整 `annotate_prefix` 接口，含状态复制、上下文与 oracle 标签计算及进程开销，不是 GPU 回合或完整 planning.request 加速。候选后果探针的独立数据为 16.500→6.389、28.348→10.313、13.485→5.527 秒，不能混为一张测量表。精确轨迹缓存最多约省 0.18 秒，未引入。

Codex2 的入口：`python -m scripts.label_bounded_prefix --state STATE.pkl.gz --state-sha256 SHA --request REQUEST.json --prefix PREFIX.json --output LABEL.json --workers 4`。必须使用匹配源码的可信测量快照；旧记录只有仿真状态时仍无法补全 unknown。条件可接受标签与实测成功标签保持分开。进程隔离只用于 CPU 冻结快照，不能直接在初始化 CUDA 的运行时 fork。

## 队列和下一项

唯一监控同时管理原版、杯子和三个 startup，600 秒核 sacct；启动参数见 reports/monitor_restart_spawn_20261019.json。当前 cup9791 在普通优先级队列；微波炉9891、D2 startup 在其后等待，spawn9967 明确等待9928和9891。没有 release 历史 held 作业。D2 新源已完成 40 状态 CPU 身份预检，9928_0 替代未运行的 9817_0，收据 reports/hybrid_d2_2a869b26_startup_submission_20261019.json；正式 40 局仍须实际 VLA 调用、准备姿态与四种交还条件证据。

## 完整 oracle CPU 条件规划配对

| 同一保存请求 | 串行秒 | spawn4 秒 | 上下文、标签、选择、请求 SHA |
| --- | ---: | ---: | --- |
| 碗 9248_0 | 35.255 | 23.331 | 一致 |
| 杯 9544_124 | 60.415 | 33.248 | 一致 |
| 微波炉 9611_120 | 14.939 | 8.112 | 一致 |

源码 7ffe2118 默认单进程；可选 prefix_consequence_workers=4 用 spawn，不能从初始化 CUDA 的进程 fork。仅并行前缀条件后果，初始接触计划和初始请求枚举仍串行。表中计入进程开销，尚无整回合墙钟改善的物理证据。

快照 /public/home/sunyihan/rpent_libero_eval/source_bounded_spawn_planning_20261019_7ffe2118，归档 SHA256 bcf8d24823c63e72335ee2c661b9c7799669b7effc27c3c0019807c89f28ed97。同源 w1/w4 的220状态 CPU预检均通过，收据分别为 reports/chunk_v3_spawn_w1_20261019_preparation.json 与 reports/chunk_v3_spawn_w4_20261019_preparation.json。先完成9967的真实启动再提交配对。
