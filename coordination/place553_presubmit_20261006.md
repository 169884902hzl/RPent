# Codex3 place553 完整5步块修复选择预回执

接受用户10/06第0/2/4条，无异议。4199完整20局冒烟已完成，官方物理14/20、结构缺陷0，全部回合保留。本次40放置选择case、20不同原版状态×2方法；保持4177场景/顺序/提示/160chunks不变，只修实际每块5控制动作、native latch不提前截断；external10000步保持。不是确认或训练。

SOURCE553 f8e5faa，源码archive SHA 896327b831c282f6b5c6f74bae47da5c5d08a9faa8bb2dec7d8bd1afb7cffacd；6执行/统计文件已逐SHA固定。manifest SHA 82f102902091aeb74d25ff4c3205843208d2a8b9ad48e796dde360f605261424，launcher SHA a800ebae60df0c03061bfec2b40f2560d0d5c76847dafbab29c9cdc8200b63bc；8片真实launcher从/tmp的CPU预检通过，40/40官方state SHA，preflight report SHA b448006b700acd3a2f3b9ec38918280c03b48558d9c9d6462f1d59564178e44c。代码准备commit052e305已推送。

8片×1GPU，空卡8，无依赖/节点绑定，不取消旧链。Slurm在回执推送后分配作业号，立即登记。输出 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/place553_fullchunks_selection_CPU_20261006/physical_same40/job<JOB>/part0..7。

实际拟命令：

```bash
env PLACE553_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime553_20261006 PLACE553_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place553_fullchunks_selection_CPU_20261006/preparation/place553_same40_selection.json PLACE553_MANIFEST_SHA=82f102902091aeb74d25ff4c3205843208d2a8b9ad48e796dde360f605261424 PLACE553_SHARDS=8 PLACE553_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place553_fullchunks_selection_CPU_20261006/physical_same40 sbatch --array=0-7%8 /public/home/sunyihan/rpent_libero_eval/scripts/run_v5_place553_fullchunks_selection.sbatch
```

setup false、已满足保留、真正新增、未执行、null分别统计；原4177旧短块证据不改，不能拿本次选择授门槛。
