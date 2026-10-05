# Codex3：3631私有绑定修复实际回执

325dfba已push，先append grasp507_private_binding_retry回执到远端COORD。实际命令：`cd /public/home/sunyihan/rpent_libero_eval && sbatch --parsable scripts/run_v5_grasp507_mug_private_binding_retry.sbatch`；返回3631，1GPU8CPU，无依赖、不绑定节点。输出`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp507_mug_private_binding_retry_20261005/retry_job3631/part3`，100个原注册mug状态，shard3/4。

实际入口：source_v5_grasp507_mug_private_binding_retry_20261005中由repo绝对路径.venv/bin/python执行`-u scripts/probe_v5_grasp449_20261005.py --manifest <原492/preparation/full.json> --shard-index 3 --shards 4 --output <上目录>`。source tar SHA `d15e3635c3f8b957c8b19ec71a3458ae412daf90f424feadb562eb09ce7f262a`，registration SHA `fa32a221426229aea7c6a2d88be0a9e20fd863d1f7fdc8f269ae1a7bd1728076`；公开配方/验证标准不改，仅补strict身份和私有XY关联。3619_3、3628的零调用失败保留，不改判、不记模型成绩。
