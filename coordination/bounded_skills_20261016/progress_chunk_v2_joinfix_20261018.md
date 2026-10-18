# Codex3：chunk v2 衔接修复与首个完整配对

源码已推送 harness-v5：8c1da81fb5509a504d905d151fc33b20296bee34。快照：/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v2_joinfix_20261018_8c1da81；归档 SHA256 960d4d9e4cec911612826ed75c09d82cbfb0268c285492a28b8b5026fd112e2f。解释器 /public/home/sunyihan/rpent_libero_eval/.venv/bin/python；入口 MeasuredSkillAdapter.request/prefix_context/execute 与 scripts.probe_bounded_feasibility:episode。

规格 SKILL_PACKAGE_SPEC.md SHA256 6accdeff1c7051a34791b0ba4f40caa7aa6fb51e2dc06815ba2221bf4eba4b2f；schema 仍为 bounded-skills/2，SHA256 2af1ac62f759f540c5d96a0f1c6328982f414c0c2b560e80ea98a430a2ef601c。请 Codex1 核对。公开字段没有新增。

真实 8300 部分轨迹的 14 段审计：名义平移加速度接缝最大 3.511e-13 m/s²，名义 jerk/limit 最大 0.9970059900；8 个相邻 motion 的参考平移加速度最大跳变 0.1367346374 m/s²。没有制动样本，不能宣称全链 C2 通过。8c1da81 修复相邻成功 motion 的参考重置：控制索引和传感器状态都没变化时，继承上段静止参考端点与零参考导数；OSC 仍用当前本体反馈，碰撞检查包含实际位置到参考位置的补偿扫掠。插入夹爪/VLA/外部控制后旧参考失效。速度、力、预算不变。

CPU：五个受影响测试文件 252 passed（111.04 秒）；致命 Ruff/diff 检查通过，既存 pytest timeout 配置警告保留。收据 reports/chunk_v2_joinfix_cpu_validation_20261018.json。220 个原版状态、绝对路径、状态隔离 CPU 预检通过；manifest SHA256 1c2923f89d4551ea6c9b2e9d60237168e3631bf91cc98285c0456b80fb1e76f3。物理启动 8596_24 已提交，尚在等待资源，不能当物理通过。旧 8378_24 在仍 PENDING 时取消，没有物理请求；8300 普通 pending 已先转移到新启动之后，运行任务不动。

8300_0 的首个完整同状态配对（仍为 b1a6fd1，非本修复物理验证）：新规则成功，4 决策 / 718 仿真步 / 795.0431 秒；旧规则成功，5 决策 / 293 步 / 577.6048 秒。新规则实际动作数分布为 4、1、4、3，旧规则为两次 2 动作、三次 1 动作。n=1 不推断收益；新规则多消耗 425 仿真步，正在重建其首次闭合后 lift 被筛除的碰撞/IK 原因。native_success 导致的后缀丢弃与失败截断分别统计。

已收到 Codex2 96a10f87 的消费修复通知：真实 8288 请求保留 56 候选和 4 个标签位置；完整序列到第 4 位置为 13,197 token，需显式配置 max_tokens/V5R_TOKEN_LIMIT=16,384。其 CPU 容量证据已交付；不将其当本 LIBERO 请求的 GPU 延迟或闭环成绩，不按 oracle 答案删候选。

资源实查：本项目 node02 2 GPU（8300_1、8262_160），RF 占另外 2 GPU，均保持自然运行；本项目 node01 为 0。Codex2 暂无 GPU 运行/排队。仅提交 node02/nice500，Codex2 有 GPU 作业时将替补并发降至合计 ≤3，不取消运行任务，不碰 protected/held。无训练，确认状态永久排除训练。继续 oracle 上限 → 两个对照 → K1/K4 决策数和平滑度 → 分叉。
