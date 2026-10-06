# Codex3：10/06 00:52 接管与20局冒烟提交前回执

已读取用户本提示、3686/3687启动失败日志、3619基础设施故障与当前代码；接受启动修复、先20局冒烟再技能大批量、独立选择/确认、95/90/95门槛、确认状态不入训及无节点绑定。无异议。不恢复旧作业。

实时squeue/sinfo：node01/node02共8卡空闲。3686/3687全部在0–1秒因相对base_config失败，零物理结果，历史日志与快照保留。启动修复已实现绝对路径/SHA CPU预检、LIBERO90诊断metadata对齐、基础设施单次同状态补试与故障ledger；focused测试80 passed，仍须物理检查。

本次只先提交20局新harness冒烟（原版10 + D2新开发init41共10），v5@750，权重SHA b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb。8分片，每片1GPU，无依赖/节点绑定，array=0-7%8。计划作业号由Slurm提交时分配；实际号随后回填。

源码快照：/public/home/sunyihan/rpent_libero_eval/source_v5_runtime536_20261006，commit eb48c11。渲染入口 robots.libero.v5_state.serialize，解释器 /public/home/sunyihan/rpent_libero_eval/.venv/bin/python。冒烟保持已登记max_decisions=100/max_chunks=80/max_episode_steps=10000/3072token，明确启用当前默认fusion、measured receipts、measurement blocking、vla_subtask及stove验证；保留persist/cooldown登记值。不是确认/最终评测，不授权冻结或训练。

显式清单：/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/preparation/manifest.json；各片manifest逐SHA在该索引；CPU预检输出同目录上级cpu_preflight/preflight.json。输出：/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job<JOB>/part0..7/{original,development}。

实际计划命令：SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime536_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/preparation sbatch --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_runtime536_20261006/scripts/run_v5_runtime536_smoke20.sbatch。

将逐局报告fusion/source cameras、no_effect及blocked动作、最大同动作重复、vla_subtask候选/使用/物理结果、测量变化。通过后才提交技能选择与独立确认链。GPU预约：本次冒烟暂用全部8张空卡，回合完成即释放；其间CPU准备选择池、确认排重和采集估算。

更正旧回执生成器SHA：旧535 prep确切SHA为1666548a9437b7a5b145bcc658c2c7be92306d9c39b4ee361ba162422d9b8973，旧回执混写SHA原文保留，本条追加更正。
