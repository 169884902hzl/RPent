# Stove568 逐块观测与分阶段恢复诊断

CPU 预检已通过，尚未提交 GPU 作业。源码 commit `eafe46c45ae116daa4d6cf2d0d9d2972f121c7df`。probe manifest SHA `532114119d4aaa72e46a92772a6f05710e30c4de0bb454f3c7c2de26c740cc09`。

4303 的 100 captures / 200 视角观测显示：agentview 的 true_off 2/2 和 neither 28/28 都是 red_fraction=0；腕部还存在 true_on 红色占比为 0 的样本。因此 red_fraction 不能校准官方 off endpoint，公共 stop 保持禁用。6400 执行块的 6440 私有评分缺少逐块同步 RGB-D，不能恢复首次变暗时刻。

本 probe 只运行原版 Goal7 init0–4 的 5 个 literal 状态，固定 on 160 chunks + off 160 chunks，不基于私有真值提前停止；每个 off 块后保存公开双视角 RGB-D 和 red features。恢复分别保存 after_contact、after_release、after_retreat，从而区分在哪个阶段丢失关闭状态。私有评分只用于后置诊断。on setup 失败仍完成固定 off 前缀并保留记录。

规模：10 contact skills、1600 chunks、8000 controls、1610 私有 chunk rows、800 公共 off observations、30 个双视角阶段 captures。array 0–4%8，每片 1 GPU，无节点绑定。

两端各 3 项 CPU 隔离回归通过；5 片实际 launcher 从 /tmp 预检、源码/manifest SHA 和每片原版 state SHA 全部通过。预检未启动仿真或 GPU 服务。

输出：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove568_public_red_recovery_original_20261006/probe_job<ARRAY_JOB_ID>/part<0..4>`。

实际提交命令（由 root 登记后提交）：

```bash
sbatch --export=ALL,STOVE568_PACKET=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove568_public_stop_selection_CPU_20261006,STOVE568_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove568_public_stop_selection_CPU_20261006/public_red_recovery_manifest.json,STOVE568_MANIFEST_SHA=532114119d4aaa72e46a92772a6f05710e30c4de0bb454f3c7c2de26c740cc09,STOVE568_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove568_public_red_recovery_original_20261006 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove568_public_stop_selection_CPU_20261006/run_public_red_recovery.sbatch
```

输入与产物均通过显式文件清单读取。不读取 PRO、人工文本或 sealed 数据，不生成训练行，不作为技能确认批。
