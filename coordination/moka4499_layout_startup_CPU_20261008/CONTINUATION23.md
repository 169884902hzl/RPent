# 4499 后剩余 23 态 CPU 前检与提交参数

同一份 immutable launcher 的 8 片 CPU 前检全部 exit 0。正式运行前缀另外在 CPU 上执行，真实启动 contract、manifest、源码与排除 guard 均通过；没有 GPU、没有物理试验、没有新作业提交。

报告：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka4499_layout_startup_CPU_20261008/remaining23_r1/report.json`

SHA：`55fbe82e97faf8cb6d4be04bc12e6af94a7eeba5b1826d40d3f47fa0341c9aef`

注意：原 pinned CPU preflight 先分片未过滤的 24 态，本次 8 片合计检查全部 24 态。正式 runner 的逻辑是先排除、再分片。本次单独核对了实际 23 态的文件/状态 SHA 和正式映射，不能将原 CPU 列表直接当正式列表。

| 片 | 正式状态 |
|---|---|
| 0 | 580101、580109、580117 |
| 1 | 580102、580110、580118 |
| 2 | 580103、580111、580119 |
| 3 | 580104、580112、580120 |
| 4 | 580105、580113、580121 |
| 5 | 580106、580114、580122 |
| 6 | 580107、580115、580123 |
| 7 | 580108、580116 |

所有状态名均带 `moka_layout_` 前缀。580100 保留首局结果，不重跑。

以下命令仅供父代理在 COORDINATION 登记后提交；本子代理未执行。`%8` 是原 launcher 的并发上限，父代理可按预约和空卡数调度，不改源码、状态或预算。

```bash
env \
  -u MOKA_TRANSFER_EXCLUDE_CASES_FILE \
  -u MOKA_TRANSFER_EXCLUDE_CASE_NAME \
  MOKA_TRANSFER_STARTUP_PREFLIGHT=0 \
  MOKA_TRANSFER_PREFLIGHT_ONLY=0 \
  MOKA_TRANSFER_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_placement582_r2_20261008 \
  MOKA_TRANSFER_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill24_CPU_20261008/preparation_r2/moka_layout24.json \
  MOKA_TRANSFER_MANIFEST_SHA=58d59c72890b2511e2c933ded040bf0cb850c9f7735b7668381db0c249986c93 \
  MOKA_TRANSFER_STARTUP_CONTRACT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill24_CPU_20261008/startup_preflight/4499/probe/contract.json \
  MOKA_TRANSFER_STARTUP_CONTRACT_SHA=4b957eeff612e730e0e3b582259482b0bb982a70ed6daf85eccac070b9d7611d \
  MOKA_TRANSFER_EXCLUDE_CASE_NAMES=moka_layout_580100 \
  sbatch --parsable --array=0-7%8 \
  /public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill24_CPU_20261008/preparation_r2/run_moka_layout24.sbatch
```

输出仍沿用 pinned launcher 的路径：

`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill24_CPU_20261008/smoke10/job<ARRAY_JOB_ID>/part<0–7>/probe/`

`smoke10` 是继承的目录标签，实际是 23 个注册布局，不是十态，也不是百态资格批。

CPU 命令：

```bash
python3 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka4499_layout_startup_CPU_20261008/preflight_remaining23.py \
  --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill24_CPU_20261008/preparation_r2/moka_layout24.json \
  --contract /public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_layout_skill24_CPU_20261008/startup_preflight/4499/probe/contract.json \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka4499_layout_startup_CPU_20261008/remaining23_r1
```
