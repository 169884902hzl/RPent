10个已访问原版状态的开发smoke已准备。不是独立确认，不进入训练。

- Manifest：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/preparation/moka_original_public_placement_visited10.json`，SHA256 `259690ca59d4c021d9f1716761686b30a8b2648e58727b8c526f0151d7275294`。
- 入口：`scripts/run_v5_moka_transfer_public_smoke10_20261007.sbatch`，8片，最多8并发，不绑定节点。
- Source：`/public/home/sunyihan/rpent_libero_eval/source_v5_drawer571_20261006`，完整源码与archive identity保存于manifest.source_snapshot。
- 实际launcher从`/tmp`完成8片CPU预检，验证10个state原始bytes。真实runner入口`--help`加载成功。证据：`preparation/launcher_cpu_preflight_report.json`。
- Owned wrapper：`scripts/probe_v5_moka_transfer_public_20261007.py`。先保留公开实体绑定检查，再把完整原版句子传给SOURCE571的`execute_subtask`。执行采用完整chunk并调用公共严格放置验证；私有On标签只在执行前后记录，不作为停止条件。
- Smoke使用旧选择池原状态，原句为`put the moka pot on the stove`。新严格放置验证尚无物理证据；95/100旧选择只证明原版On结果，旧98/100是抓持判定一致率。
- 所有物理首尝试保留，不重跑物理失败。无GPU提交、无模型调用、无新训练行。

供主代理提交：

```bash
sbatch --export=ALL,MOKA_TRANSFER_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer571_20261006,MOKA_TRANSFER_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/preparation/moka_original_public_placement_visited10.json,MOKA_TRANSFER_MANIFEST_SHA=259690ca59d4c021d9f1716761686b30a8b2648e58727b8c526f0151d7275294 /public/home/sunyihan/rpent_libero_eval/scripts/run_v5_moka_transfer_public_smoke10_20261007.sbatch
```

五类已有确认按原来源分层汇总在`preparation/five_class_existing_confirmation.json`：成功485/500，一致489/500。两unknown保留。保守Wilson区间分别95.11–98.17%、96.10–98.77%；pan的100请求只有99原状态。该描述性汇总不证明一个新统一SOURCE已完成确认。

供当前best interim复用的五类完整profile及overrides：`preparation/five_class_profile_overrides.json`；pan562校准独立JSON：`preparation/pan562_grasp_measurement_calibration.json`，SHA256 `d4d977a5e5c23a23d80983ab34a4958373c6103035c2156ced24038204e4ca1c`。
