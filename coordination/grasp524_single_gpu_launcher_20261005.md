# Codex3 child：grasp524 单 GPU launcher 完成

按 parent 明确授权仅补 owned launcher，不提交、不推送；parent 负责预回执、archive/source 同步、GPU 预约、实际 Slurm 提交和 COORD 更新。

`scripts/run_v5_grasp524_saved_queries.sbatch` 固定 1 GPU / 8 CPU / 90G / 2h，无 ReqNodeList、ExcNodeList、依赖或数组。远端解释器固定 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`，checkpoint 固定 `assets/sam3/sam3.pt`。

`GRASP524_SOURCE` 必须显式提供已经同步的独立 snapshot。脚本在该目录 `cd`，设置该目录为 PYTHONPATH，用 `-m scripts.probe_v5_grasp524_saved_queries` 从 snapshot 模块运行。提交前自动核验 snapshot 中薄 runner 的文件 SHA `f93cc4a81f95bc9e16832f4cd7463bda979f1030c7a242c1b118268e1e4af8bc`，以及固定 min8 manifest SHA `b932876ebced88c224c5772c44b0e7a03b2fc7b31435025b1c2444e1d38eb977`。不从任意当前 checkout 或 artifact 扫描选择代码/输入。

输入 8 个已保存原版视角 / 24 个预登记 query，输出：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp524_missing_points_CPU_20261005/query_job<SLURM_JOB_ID>`
日志 `results/slurm-<SLURM_JOB_ID>.log`。薄 runner 继续核 RGB/world SHA，逐实例保留 score/mask/测量/可复算拒因。无环境重放、机器人动作、private truth 请求或 runtime/旧标签修改。

launcher 已同步远端同名 scripts 路径，`bash -n` 退出 0，SHA `36a3b1cace7fa02fbf83b61fc61066f41524a10c294aa78570841f374af113fb`。尚未提交作业，不能宣称 GPU/SAM 诊断已运行或通过。

parent 完成预回执和 archive 同步后可执行（snapshot 值由 parent 固定后记录）：

```bash
GRASP524_SOURCE=/public/home/sunyihan/rpent_libero_eval/<EXPLICIT_SNAPSHOT> \
  sbatch --parsable scripts/run_v5_grasp524_saved_queries.sbatch
```

未添加节点限制或依赖，未修改现有作业。全部完成后 parent 记录实际 job id/source commit/archive SHA/输出及结果。
