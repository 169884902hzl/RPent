# Codex3 3628 实际提交回执

预回执fcb72b5已push并先append远端COORD，再实际执行：`cd /public/home/sunyihan/rpent_libero_eval && sbatch --parsable scripts/run_v5_grasp502_mug_meta_retry.sbatch`，Slurm返回3628。1GPU、无依赖、不绑定节点；100个原注册mug状态，shard3/4。

输出：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp502_mug_meta_retry_20261005/retry_job3628/part3`。实际入口命令（launcher展开）：`.venv/bin/python -u scripts/probe_v5_grasp449_20261005.py --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp492_first4_confirmation_20261005/preparation/full.json --shard-index 3 --shards 4 --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp502_mug_meta_retry_20261005/retry_job3628/part3`；工作目录为source_v5_grasp502_mug_meta_retry_20261005，解释器是repo绝对路径.venv/bin/python。

registration SHA `cb1a3c72f016787ad1be08428b1c3520c25c0bc6379c5123eb50e33973cbdf5a`；client SHA `556d0ceb8df9b1da98635c04a81b9187eb8a8deeccfc5b30f2d65c2438611f5e`。与3619旧source只有该client不同。旧失败完整保留并明确关联新重试；不得把零调用误记成物理失败或把旧失败记录删掉。
