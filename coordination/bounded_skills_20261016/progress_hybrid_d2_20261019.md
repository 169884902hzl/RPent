# 10/19 混合技能诊断：源码与启动状态

1. 已实现 D2 40 局的同状态自执行 / π0.5 三次分叉，以及独立的整局择优序列复跑；分叉源码 `e9aeaf9b` 已推送；启动修复 `2a869b26` 已推送。
2. 原版 ec89f74 批中间结果为 109/136 个完整物理回合，登记 220；84 个未完成，0 执行异常。不是完成的 220 局成绩。
3. D2 启动 9928_0（替代未运行的 9817_0）、杯子补采启动 9791_61 正常排队；尚无新源码物理成绩，正式 D2 40 局数组未提交。
4. CPU：31 项相关测试通过；新增“无匹配 call_vla 时不能执行别的动作”回归所在 6 项通过，两次计数重叠。40 个 D2 状态哈希均核对。
5. Codex3 继续物理 startup、失败修复和原版上限；Codex2 接收匹配源的私有分支证据。没有训练或冻结，确认状态永久排除训练。

## 身份和接口

- 规格：[SKILL_PACKAGE_SPEC.md](../../SKILL_PACKAGE_SPEC.md)，补充 `private-hybrid-call-vla-subtasks/1`。
- 入口：`scripts.probe_bounded_hybrid_d2:main`。
- 源码快照：`/public/home/sunyihan/rpent_libero_eval/source_bounded_hybrid_d2_20261019_e9aeaf9b`。
- 解释器：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。
- 归档 SHA256：`49c965a2796b743da2b7dfe6d9e893b01b8f7714a3796db8f16e8671aeb3cfbb`。
- 清单：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/hybrid_d2_20261019/preparation/D2_hybrid_manifest_e9aeaf9b.json`。
- 清单 SHA256：`0bd2a059ccd6f226ea3d00955587c0796bae8b03c940d9a1a63eb999eee24637`。
- 公共 schema / legal / 原私有 judge 保持 3 / 2 / 13。新 D2 私有 facade 不改变常规 original-only oracle 服务。

范围严格为现有 D2 八套件 task0–4 / init40；不读取 PRO 测试目标。目标条目可拆为 pick44、on22、in22、open2、close2、turn_on2；没有语法未覆盖条目。此项只证明既有规则能解析，不证明身份绑定、任务进度或执行上限。92% 任务成功率和 99% 逐次选择正确率均是目标指标，不作开发准入条件。

每个子任务保存物理状态、控制器、RNG、预算计数，以及公开缓存、持物和失败重试状态。四个分支从同一检查点和请求开始。每份私有分支汇总包含请求/前缀 SHA、首个候选 ID、public legal、逐次 choices/receipts、仿真步、墙钟、π0.5 推理次数、私有真值文件和端点 SHA。CPU 前缀上下文另存并哈希。没有匹配 VLA 候选时明确记 unavailable，不偷偷转成 oracle 动作。

每个 VLA 分支使用互不重叠的推理种子序列，服务端 `sampling_seed` 保存和恢复 RNG，不干扰普通请求。选择取观测成功率较高的方法，平局选自执行；缺测保持 unknown。两边失败保持任务失败。采样分叉包络和条件率乘积单列；整局实测从开局重新执行选定方法，并使用新的 VLA 种子，不拼接成功端点。共享 10,000 仿真步 / 160 决策预算。

## 已检验与未检验

`reports/hybrid_d2_cpu_20261019.json` 保存 31 项 CPU 测试命令和原始输出；另 6 项聚焦回归中新增 1 项。Ruff 对五个新改源码/测试文件通过，launcher `bash -n` 通过。D2 全 40 状态的 BDDL/init 身份已经 CPU 核对；诊断 launcher 与正式 launcher 相同。

尚未证明：实际 π0.5 调用、重新摆位、四种交还条件均真实触发，以及独立整局上限。因此没有报任何新的 D2 成功率或混合模型正确率。启动失败必须非零退出；现有原版任务继续保留失败并按源码分别统计。

## 原版失败诊断与耗时

杯子分层轮廓补采为独立源 8410d77b，先完成 9791_61 的真实启动，才放行 init1/init11 全回合。固定源原版结果见 `reports/original20_support_interim_r18_20261019.json`；真盒子 9579 的 20/20 单列，不把历史罐子类别算成盒子。

微波炉开门的终末表面接触 16 个姿态均被数值 IK 拒绝；当时并非完全失去门测量。追加保存状态的 CPU 分析，区分端点 IK 与整条路线的局部续解失败，不以全局端点解替代路线筛查。旧失败、别名诊断和真实公开实体身份分开。

现有函数级 profile 结论及已验证同捕获缓存仍见 `progress_prefix_judge9_and_door_identity_20261018.md`。代表请求46.782秒，主要是表面接触计划18.913秒、点云/IK17.987秒、轨迹准备14.917秒，累计值嵌套不可相加；单 refresh5.821–7.481秒。新的 CPU 隔离实测修正了此前笼统的并行限制判断：相同保存状态和前缀的候选后果在四进程下逐字节一致，碗 16.500→6.389 秒、杯 28.348→10.313 秒、微波炉 13.485→5.527 秒（候选数 76/106/63）。证据为 `reports/prefix_parallel_pair_CPU_20261019.json`。这是后果计算探针，不是完整请求或 GPU 回合加速；离线标注的可选并行路径正在验证，运行时仍串行。精确轨迹缓存仅节约约 0–0.18 秒，未采用。新 startup 实际运行后补同版本的请求时间，不把旧测量写成新提速成绩。

## 启动检查修复（2a869b26）

旧 startup 会先完整执行 self 分支，才进行第一次 VLA 请求；这会把服务链检查延后一个完整 oracle 预算。现在 startup 只执行一次匹配的 call_vla，必须同时记录实际推理次数和物理步数才通过；无物理请求明确返回 startup_no_vla_physics，由 main 非零退出。正式 self + 三次 VLA 分叉顺序不变。13 项聚焦测试通过，Ruff 对两份改动文件通过。

新快照 `/public/home/sunyihan/rpent_libero_eval/source_bounded_hybrid_d2_startup_20261019_2a869b26`；归档 SHA256 `35c61ee663b7cc3191741e1a29bcee9b03157f7742a173e1bcb524152b155b21`。manifest 的全部 40 个 case 和 BDDL/init 哈希与旧版一致，SHA256 `e6590dc0a901d5f3e551583d3df758eca9a4ad839cf873311727c90bebfa9ad4`。9928_0 普通排队、node02/nice500；唯一监控已切换到新收据。9817_0 在 PENDING Dependency 状态取消，未产生物理结果。四种交还条件仍无新增实测，正式 40 局未放行。

实际离线 annotate_prefix 接口配对完成：碗 15.308→7.538 秒、杯 29.773→11.833 秒、微波炉 14.530→6.351 秒，完整上下文和标签字节一致，证据 reports/offline_parallel_labels_CPU_20261019.json。默认单进程，workers=4 为 CPU 离线选项。

运行时条件规划的可选 spawn 路径已提交为 7ffe2118，默认 prefix_consequence_workers=1；同一保存请求的完整 oracle CPU 配对为碗 35.255→23.331 秒、杯 60.415→33.248 秒、微波炉 14.939→8.112 秒，前缀上下文、完整标签、选择、请求 SHA 和合法性审计一致。证据 reports/runtime_spawn_oracle_CPU_20261019.json。初始接触计划和初始请求枚举仍串行；该表不是整回合墙钟改善。实际 startup 9967_0 等待 D2 9928 和微波炉 9891 结束，完整物理配对未提交。
