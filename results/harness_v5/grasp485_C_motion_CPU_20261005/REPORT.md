# C 完整指令的抓取后运动核对

已运行 CPU 分析：显式读取 3550 的 C 分片 0、3、6、9、12、15，共 600 条完整试次；600 个 `choices.jsonl` 的 SHA 均与原始 ledger 一致。没有新物理试次、模型调用或训练行，未改原始真值标签。

**结论：碗、瓶子的 C 轨迹没有抓后释放证据；摩卡壶存在一次被搬到灶台并释放的证据。** C 已有 π0.5 提前停止，却用的是末端运动和开度启发式，不能保证在选中物体抓起时停止。盒类主要是完整多物体指令造成的低层目标偏移，不能称作 decider 选错。

|类别（各100试次）|原始持续抓取真成功|public pick success|最终 XY 位移中位/P95 cm|最终 body-origin 升高中位/P95 cm|双指抬升→开夹爪失去手指→最终支撑代理|
|---|---:|---:|---:|---:|---:|
|瓶子|98|100|1.08 / 4.11|8.27 / 10.81|0|
|碗|99|100|1.80 / 3.68|6.66 / 9.61|0|
|盒子|68|100|0.84 / 3.67|6.91 / 11.79|0|
|平底锅|2|83|约0 / 约0|约0 / 约0|0|
|摩卡壶|50|97|1.05 / 21.54|3.70 / 7.35|1|
|杯子|94|100|4.60 / 7.68|6.93 / 8.41|0|

位移来自仿真 body-origin，只用于这次诊断；不是感知坐标，不进入运行时。最终位置是技能结束、私有0.5秒真值保持之前的位置；public stop 后可能还有验证失败触发的5cm试抬，块期间位置与最终位置分别保存在逐例证据中。平底锅、摩卡壶各100试次含50个官方初始状态各重置两次；这些不是独立确认批。

## 真实停止机制

冻结源码 `source_v5_grasp459_bound_safe_retry1_20261005/robots/libero/tools.py::pi0_pick`，第210–289行，SHA `fc3be390a4d7beb2a40c322e27931edeb83a55f195250a3f2ede2bb29b60f865`：每个动作块后检查 EEF 相对初始下降≥10cm、从最低点抬升≥5cm、当前夹爪开度在[0,6cm)内。满足即停；它不读选中物体的测量抬升或持续接触。580/600试次由此启发式返回 success；平底锅17和摩卡壶3为预算失败（摩卡壶另1次在第160块恰好满足启发式，不能计成预算失败）。

冻结 probe 第158–175行明确给 C 添加 `pick up the {选中测量类别} first, then {原版完整任务}`，SHA `71fa44f83ea6b47724e5631ef8702eb7499335ac802bc8d0345ad115803a0db1`。标准有限技能的 `complete_skill` 在技能执行时暂时屏蔽 native terminated；600条 public pick 都记录 terminated=false，不可据此推断任务从未物理完成。源码函数原文与哈希保存在 `report_v3/summary.json`。

## 关键逐例证据

1. 摩卡壶：`moka_pot_libero_10_t2_s40_rpent_start_bound_full160_trial90`，逐例文件第491行，原 prompt：`pick up the moka pot first, then turn on the stove and put the moka pot on it`。第43块双指接触，中心比初始高3.37cm；第63块夹爪开度7.58cm、无任何手指接触，接触几何为 `flat_stove_1_collision_burner`，XY 已移动23.80cm。块期间最高中心升高12.71cm、最大XY移动24.63cm。最终XY移动24.32cm，物体稳定支撑在灶台，π0.5继续跑到160块且public success=false。**存在输运并释放到指令所述表面的证据；不重判为抓取成功，也不宣称整条指令已经满足。** 原始持续抓取真值false不变。choices SHA `b5208dd48f9be68e445bc4586b0ea6fe8c27f575935f0cbcc9f41febe357b296`。
2. 杯子反例：`mug_libero_10_t9_s4_rpent_start_bound_full160_trial14`，逐例文件第515行。第35块中心升3.48cm时只有单指和桌面接触，开度8.01cm；随后物体继续接触桌面，最终无手指且最低几何仍在原支撑面。没有双指抬起证据，这是推移/倾倒风险，**不能称为“抓后自行放置”**。原始真值false。choices SHA `b7cf8fc30829b3a2979a8af109099a8acf064c5b9b25f39c6b7c7d42d9579e60`。
3. 盒类：`box_libero_10_t1_s0_rpent_start_bound_full160_trial0`，逐例文件第201行。选中 butter，prompt=`pick up the butter first, then put both the cream cheese box and the butter in the basket`；cream_cheese在第13块有双指接触＋中心抬升代理，最终中心升14.77cm。该样本是π0.5低层目标偏移；不是仅凭XY判放置，也不把代理升级为完整几何持续抓取真值。choices SHA `9edc761dfb2b2489ae5ab3e69587238a7a018a48ad958175e8436d096b3a12e3`。

完整逐例 `report_v3/trials.jsonl` 含全部600试次的块级选中物体XYZ、开度、手指/支撑接触、初始/最终位置、public stop结果、原始回执和原始持续真值保持记录。块边界采样可能漏掉动作块内部的短时释放，因此“没有证据”不是证明从未发生。body-origin升高、双指或单指接触代理均不能替代已登记的最低碰撞几何离原支撑≥3cm、无原支撑接触、持续0.5秒手指支撑真值。

## CPU 实际命令与哈希

在 `gpu5880-ts:/public/home/sunyihan/rpent_libero_eval` 执行（直接CPU，无Slurm新作业）：

```bash
.venv/bin/python scripts/diagnose_v5_grasp485_C_motion.py \
  --frozen-source source_v5_grasp459_bound_safe_retry1_20261005 \
  --ledger results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part0/episodes.jsonl \
  --ledger results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part3/episodes.jsonl \
  --ledger results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part6/episodes.jsonl \
  --ledger results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part9/episodes.jsonl \
  --ledger results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part12/episodes.jsonl \
  --ledger results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part15/episodes.jsonl \
  --output results/harness_v5/grasp485_C_motion_CPU_20261005/report_v3
```

- script SHA：`8e7ad1137cd519ff6f07d262cd4200de6d0900f9e8629f4bae6d55edfabc133d`
- summary SHA：`a24bacb0d508bf7d8501c4be36d9fb59324d590c06c58eb361fe17b920c8206f`
- trials SHA：`06b51d495d0a38f713acbe6ca8feede75867eada574fb6d66e920451a3f6b383`

局部CPU开发时遇到未命名MuJoCo接触几何和旧probe内联函数的问题，已修复；最后一次完整600试次命令exit0。先前CPU中间报告保留于远端，不改变任何3550产物。仅诊断，不构成训练准入或行为冻结。
