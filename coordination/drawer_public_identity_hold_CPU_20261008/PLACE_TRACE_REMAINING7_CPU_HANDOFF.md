# place trace r2 剩余7单局：同launcher CPU已通过

沿r2源码 `0eff8550d2c9cb73f778423d5945c1562c62898d`、原setup/reset/subtask/160-block预算与相同trace干预；不重跑case0。源码快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_place4311_public_trace_r2_20261008`，launcher `coordination/drawer_public_identity_hold_CPU_20261008/run_place_trace.sbatch` SHA `87a93437021427560babc47ceaf4da2b307265ec64fd2ad27240533523c8b847`。

7个manifest分别从 `/tmp` 用同launcher的CPU分支运行，source/archive/file/producer/manifest及官方state SHA均通过，7/7 exit0，每个state_hashes_checked=1。本子代理0GPU提交。公开绑定/额外观察干预的声明不变；6distinct已访问开发状态永久训练排除，旧4311原始记录不改。

固定报告 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/remaining7_launcher_preflight/report.json` SHA `76b183249c2e7ed27773e3f66bda16fc0496882c3fadd91234bcac7e2b51d101`；每一项有实际submission_env、launcher路径、stdout/stderr SHA及结果。由root预约/预回执后提交，job号由Slurm实际返回。

|case|manifest|SHA|输出|
|---|---|---|---|
|1|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/registered/case1_vla_subtask160_t25_s4.json`|`64d476653f73224937759c0287fee268c92fa0b1cacb12686df049a211aff7bb`|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_dev_20261008/case1_r2/job<JOB>`|
|2|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/registered/case2_vla_subtask160_t24_s3.json`|`ec5c5f1d0ec4444a5aa57f5491ad541e2cdc4dc0c6497ff3edd3edc5f535f58d`|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_dev_20261008/case2_r2/job<JOB>`|
|3|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/registered/case3_current160_t10_s2.json`|`27ccf30426c03241f88a8b84ac2fcfa26aae63bde1745a9bc084c818edddbeb3`|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_dev_20261008/case3_r2/job<JOB>`|
|4|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/registered/case4_vla_subtask160_t10_s2.json`|`01053570f1f016c1703ebdb1f42b812caa5d4eafc940feb0b616717f1e703f12`|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_dev_20261008/case4_r2/job<JOB>`|
|5|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/registered/case5_current160_t25_s1.json`|`fc2975e9807a403d852b614774f70603e66c9a208a2fadd7923e48d7297a4ff9`|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_dev_20261008/case5_r2/job<JOB>`|
|6|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/registered/case6_current160_t25_s2.json`|`9b5649be8378c5e7cbc508fd15a33678f66d99122e96c9ffa7d5e632c5bb6756`|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_dev_20261008/case6_r2/job<JOB>`|
|7|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/registered/case7_current160_t25_s0.json`|`de79f748ee09683742369a5163dc4b9a17f88b19075346647b0d22c5b8342203`|`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_dev_20261008/case7_r2/job<JOB>`|

每局命令为report该项 `submission_env` 加 `sbatch --parsable <same_launcher>`。保留1GPU/no node/no dependency；GPU并发由root按实时空卡及预约调度，不增添串行依赖。
