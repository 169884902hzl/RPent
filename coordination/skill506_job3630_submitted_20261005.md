# Codex3：3630统一技能开发smoke实际回执

预回执c784a89已push并先写远端COORD。实际命令：`cd /public/home/sunyihan/rpent_libero_eval && sbatch --parsable scripts/run_v5_skill506_measured_smoke.sbatch`，返回3630。数组0–4%8，每片1GPU，无依赖、不绑定节点；20请求，六类开合12、on/in4、pan/moka完整子任务4。现由Slurm在可用卡上排队/执行。

目录：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill506_measured_smoke_20261005/smoke_job3630/part0–4`。source commit d2c09c86a9fef9b3e0da4b3b2d8722b8c748cae0，tar SHA8dfb4c20e53a25b77d6bb8a24122148cbab5557947e71bb7a864a1e41fcd7dac；三个manifest SHA与预回执一致。实际入口为source目录内`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python -u -m scripts.probe_v5_skill501_original --manifest <已登记smoke.json> --shard-index <0/1/2或0> --shards <3或1> --output <对应part>`。

这是开发通路smoke，未做性能确认、未冻结、训练数据0。失败逐类定位修复，不仅记录后停止；原目录和全部记录保留。
