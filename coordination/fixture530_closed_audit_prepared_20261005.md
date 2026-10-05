# Codex3：3679/3682 闭合记录汇总代码已准备

已接受实际链：stove523=3679、源码source_v5_stove523_fullchunks_original_20261005(commit5ae83634)；fixture526=3682、源码source_v5_fixture526_original_direction_20261005(commitfe702b9)。不重复提交、不改已有作业、不触共享runtime/probe501；物理结果有真实闭合记录后才汇报。

独立CPU入口 `scripts/summarize_v5_fixture530_closed.py`，SHA `149b50926fe4e95fac3900de5444229d02997c035b07f20a8ea6310936858d24`。5 focused CPU tests和compile通过。只读显式manifest/选定shard ledger/producer身份及这些文件内的artifact引用。闭合prefix必须显式开关且保留未完成分母；空ledger或半行拒绝，不预填结果。

核对真实5-control chunk、scope与motion trace的一致性、raw native成功步数及external trunc；requested/opposite双私有谓词单独记录，新达成/已有保持/已有毁坏/未知互斥。公共判定调用producer源码快照里的现有measured_fixture_endpoint/measured_stove_endpoint，校验其模块SHA与实际producer一致；分别给双端点混淆、两个方向误判、unknown覆盖与Wilson区间。小规模开发重复/样本量限制显式说明，不作为确认门槛。

全量命令（在相应记录闭合后执行，非已运行成绩）：

```bash
cd /public/home/sunyihan/rpent_libero_eval
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_fixture526_original_direction_20261005 .venv/bin/python scripts/summarize_v5_fixture530_closed.py --manifest results/harness_v5/fixture526_original_direction_20261005/preparation/fixtures_direction.json --manifest-sha256 df08c26b7d161ef254233d61d36eaf50c919b1fcfd8a4f50edb6745bfc54d111 --job-root results/harness_v5/fixture526_original_direction_20261005/probe_job3682 --shard 0 --shard 1 --shard 2 --output results/harness_v5/fixture530_closed_original_CPU_20261005/fixture3682_full
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_stove523_fullchunks_original_20261005 .venv/bin/python scripts/summarize_v5_fixture530_closed.py --manifest results/harness_v5/stove523_fullchunks_original_20261005/preparation/stove_control_fullchunks.json --manifest-sha256 14e3dbde9930393a0961ec3a6c181859f800a78b725947dbc9a8fe7061445812 --job-root results/harness_v5/stove523_fullchunks_original_20261005/probe_job3679 --shard 0 --shard 1 --shard 2 --shard 3 --output results/harness_v5/fixture530_closed_original_CPU_20261005/stove3679_full
```

中间统计只指定确有闭合记录的shard并加 `--allow-closed-prefix`，使用另一个独立输出目录；每次保留旧报告。0新训练行，不读取PRO/人工/密封数据，无新Slurm作业。
