# Codex3 runtime550 已提交 job4186

预回执 3f6a4da 已先推送并写 COORDINATION。20 局，8 分片，每片 1 GPU，无依赖和节点绑定。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job4186/part0..7/{original,development}`。SOURCE550、manifest 与 CPU 预检 SHA 见同名 JSON。

```bash
env SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime550_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime550_smoke20_20261006/preparation sbatch --parsable --nice=0 --array=0-7%8 --job-name=libero-runtime550-smoke /public/home/sunyihan/rpent_libero_eval/source_v5_runtime550_20261006/scripts/run_v5_runtime536_smoke20.sbatch
```

当前仅开发冒烟，未冻结、未开始训练或采集；后续立即核对首物理记录、失败日志与全部约定指标。
