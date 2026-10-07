# 实际运行时 fixture identity 单局包

源码接线 commit `a5e7aeae9829a6626be138f5695a8e91b33b5044`，23项窄CPU测试通过。`fixture_fragment_alias_v1` 默认False；验证包明确True。cabinet查询在同一capture里补独立drawer SAM测量，随后在scene owner清理通过同volume、独立current drawer、唯一更高current parent要求的别名。状态、候选、专家绑定共用这一场景；不生成新几何，不换已有ID，不新增状态字段。

默认refresh已有当前主相机SAM mask；持久mask文件需`record_sam_masks_v6=True`，本包明确开启。家具派生band不当作独立drawer证据。alias历史只记录已有公开测量和mask引用，供诊断；不进入状态文本。

4533原公开frame+actual SAM masks的CPU证明：实际`MeasuredScene.canonicalize_fixture_fragments()`使旧绑定None变为原有measured top e104；移除e107及派生e110/e40/e86，保留实体对象/数值不变。报告：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_runtime_identity_r1/saved_public_runtime_reproduction.json`
SHA `91ddb0c0035145f519976a800ff3cfed624806cbd6ed6db300df060702682064`。

不可变源码：`/public/home/sunyihan/rpent_libero_eval/source_v5_place_runtime_identity_r1_20261008`。archive为同base下`source_code.tar`，SHA `395859fe3394f3984c348980fe77597a8ce0a84deb672ec92ef169b01adc3df6`；475个显式源码文件已逐项核SHA。解释器为`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

同launcher从`/tmp`执行CPU分支exit0，核对1个官方state SHA、manifest/source/producer/依赖。报告：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_runtime_identity_r1/same_launcher_CPU_preflight.json`
SHA `3c6d2814ea49f857c80d1bb2af8b1be99ed6c1ec61ec18c485d875e682e82f44`。

实际GPU runner为`probe_place_runtime_identity.py`→`original_placement_trace(observe_runtime_only=True)`→原版`probe_v5_skill501_original.main()`。观察器不加capture、query或cleanup，不增加robot controls；场景原生refresh中的新开关负责查询与唯一身份。它与r2开发trace干预不同；r2运行中快照及确认配方没有修改。

由root预约和预回执后执行以下命令；本子代理0GPU提交。输出为`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_runtime_identity_dev_20261008/case0/job<Slurm实际号>`。1GPU、无节点绑定、无依赖；沿原case0官方task25/init2、setup、160完整5步块、strict6阈值。访问过的开发状态永久不入训练；不是确认批，不授资格。

```bash
env PLACE_TRACE_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_place_runtime_identity_r1_20261008 \
  PLACE_TRACE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_runtime_identity_r1/registered/case0_runtime_identity_t25_s2.json \
  PLACE_TRACE_MANIFEST_SHA=3eb0eacbfb00a993d7da55f4e7af1750c43a56fcfc5378fbaf51078e765f85ce \
  PLACE_TRACE_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_runtime_identity_dev_20261008/case0 \
  sbatch --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_place_runtime_identity_r1_20261008/coordination/drawer_public_identity_hold_CPU_20261008/run_place_runtime_identity.sbatch
```

launcher SHA `26a391e2a05b5a30516d1a7aa0be294073e6f6df34ec510743fa35574ebd3ca6`；manifest SHA见上。实际物理验证尚未完成，不能把CPU绑定证明或r2的4536成功写成默认harness修复通过。

r2剩七局提交原回执不覆盖，独立`submission_mapping_v2.json`从各manifest补case字段，SHA`2e5469a8ca79e7cd6e2624fe8e8f2096009959c9d9c471d8dd7d5ef1db191f2b`。监控只沿显式episodes/attempt/public index读产物；空的运行中ledger记为待写完，不当作基础设施或模型失败。目标控制步数单独核算，不把setup counter当place执行证据。
