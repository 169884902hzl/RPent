# Codex3：统一测量技能smoke预回执

已读取12:20交接与skill500/501/505代码和manifest，接受原版技能探索→独立确认→专家190/200→新旧开发集共用候选再冻结的口径。无异议；当前未冻结，既有训练不改。新作业是开发smoke，不是确认/模型成绩/训练采集。

源码快照：`/public/home/sunyihan/rpent_libero_eval/source_v5_skill506_measured_20261005`，commit `d2c09c86a9fef9b3e0da4b3b2d8722b8c748cae0`；tar SHA `8dfb4c20e53a25b77d6bb8a24122148cbab5557947e71bb7a864a1e41fcd7dac`。包含默认融合、公共变化回执、全动作无效果阻断与完整vla_subtask执行；私有接触/关节/predicate只进单技能标签。原生终止latch仅在独立单技能probe scope里暂屏蔽，避免setup原任务先满足后反向操作零调用，不改变实际harness的坚持重试/原生终止规则。

从预注册parent各type/arm最前一个case选出20请求（不读结果）：开合12、放置4、平底锅/摩卡壶完整子任务4。manifest位于`results/harness_v5/skill506_measured_smoke_20261005/preparation/`：fixtures_smoke SHA `4b41dd0ce72b7694a20d0e1c95f299ac1caab77ae5f798ae0e3893cc11c65c37`；place_smoke SHA `37d3eac254090f553b9854846b922b359e3f83118626e3c0d18fcb2561c672c1`；grasp_subtask_smoke SHA `4ec7550ae488c9a77d3cf52694a8ad4ce49a8624478fc14db3b583e145163b02`。

计划提交：`sbatch --parsable scripts/run_v5_skill506_measured_smoke.sbatch`，数组0–4、每片1GPU，无依赖/无节点绑定。空卡当前都被独立技能分片使用，数组并发上限按全池8登记，Slurm只在实际有资源时启动；不取消运行中作业。输出`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill506_measured_smoke_20261005/smoke_job<jobid>/part0–4`，jobid返回后立即登记。解释器repo.venv/bin/python，模块scripts.probe_v5_skill501_original，max_chunks160、action_chunk5、max_episode_steps10000、标准原版资产。

3628元数据问题已解决，但随后在contact前暴露私有label目标binding问题，报target has no unique private diagnostic binding，chunks/action均0。原record/log保留，已立即定位第二层instrument故障，继续独立修私有绑定；不把零调用记模型失败，也不改已注册公开控制配方。
