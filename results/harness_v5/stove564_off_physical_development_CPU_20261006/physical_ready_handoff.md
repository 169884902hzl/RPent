# stove564 off20 implemented handoff

实际 `/tmp` launcher 的 0–7 八分片逐引用和原版状态预检全部通过；两端三项 CPU 合同回归通过。真实源码 server `--help` 导入通过，无仿真/GPU启动。

独立 server 在每个已执行 5-action chunk 后写私有评分，公开返回原样。评分读取异常保留在独立 ledger，不改变动作；固定 cell 全部执行后才按错误评分使 probe 非零。on setup物理失败仍执行 off，最终按 setup true/false 分层。

固定为原版Goal7 init0–4 × 四条件的20个配对开发cell，40次contact、6400chunks、32000controls、6440chunk评分行；非确认批。公开精修量不到时保留 unmeasured 并照常执行固定prompt，不走private fallback。fusion显式开启。

manifest SHA256：`a82da4b18a83db73b9cb26458ba9aceed8b5729f1092d3467baf6d0f496184e2`。计划产物：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off20_original_20261006/probe_job<ARRAY_JOB_ID>/part<SHARD_INDEX>`。

登记回执后由root提交，实际命令：

```bash
sbatch --export=ALL,STOVE564_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_stove555_20261006,STOVE564_PACKET=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off_physical_development_CPU_20261006,STOVE564_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off_physical_development_CPU_20261006/off20_probe_manifest.json,STOVE564_MANIFEST_SHA=a82da4b18a83db73b9cb26458ba9aceed8b5729f1092d3467baf6d0f496184e2,STOVE564_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off20_original_20261006 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off_physical_development_CPU_20261006/run_off20.sbatch
```

解释器：`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`；immutable source：`/public/home/sunyihan/rpent_libero_eval/source_v5_stove555_20261006`。

所有源码与metadata逐引用SHA见 off20_probe_manifest.json；八预检证据见 launcher_cpu_preflight/probe_jobCPUoff20_final/preflight_part0.json 至 preflight_part7.json。大权重只核对显式路径、字节数，未在每个CPU预检重算完整权重SHA。

没有修改shared runtime/verification、旧source555或旧设计manifest；没有提交GPU、写COORDINATION或push。当前物理执行尚未验证，开发故障由owned probe继续定位修复。

源码commit：`3b621c69b5a2aacd73ecba8392ec8b7d07e7c95d`。owned source archive：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off_physical_development_CPU_20261006/off20_owned_source_3b621c6.tar`，SHA256 `3d34f87eacd02564f4d512e9cfc5f6b6af0ed7be74c518bf4e6400bcf0b9894a`。预检汇总：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off_physical_development_CPU_20261006/preflight_aggregate.json`，SHA256 `b333a6e310e3f084849f07c40820832caf7aca5fe517de90638968b2d42869ee`。

私有评分异常保留 private_scoring_error（unknown标签/基础设施类），动作进程不受其值或错误影响；收完cell后按异常评分判 probe_error并非零，不计为模型物理成绩。
