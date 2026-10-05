# Codex3 抓取失败字段与确认汇总口径（494，2026-10-05）

已只读核对当前`probe_v5_grasp449_20261005.py`、`summarize_v5_grasp449_20261005.py`、`prepare_v5_grasp493_moka_comparison.py`及491的最终`report_v2`。未改probe、runtime、summarizer、493 manifest或任何旧记录；无新Slurm、物理动作、模型请求或训练行。本项是字段合同核对，不是行为冻结。

## 先纠正491预算用语

491已推送回执中的“真正预算失败3/5/7”指的是**技能stop标记：public `pi0_pick.chunks_used >= max_chunks`且`success=false`**，不是互斥的物理终止类别。将它直接当作3/5/7个物理失败是不正确的。

|条件|public技能budget stop|其中最终持续抓取真成功|其中最终持续抓取真失败|
|---|---:|---:|---:|
|C|3|2|1|
|B|5|1|4|
|BA|7|1|6|

交叉结果从491已核SHA的300条`report_v2/trials.jsonl`直接复算；原始truth、成功数50/42/58、FP/FN及分母均保持不变。491原产物保留，主代理在共享COORD追加本勘误。public stop与最终保持处于不同时间点，后续试抬与夹持可以改变最终物理结果。

## 字段是否足够

|需区分的事项|现有证据|能得出的结论|具体限制|
|---|---|---|---|
|contact未调用|`contact_approach_measurement.pose=null`、`visible_handle_not_measured`/`visible_rim_not_measured`、无`rpent_pick_result`、空`contact_samples`、0执行VLA动作|明确的stage早退可以记“contact未调用，前置测量未通过”|仅有字段缺失不能证明未调用：异常可以发生在进入contact之后、证据赋值之前|
|contact调用并执行|非空`contact_samples`或`motion_evidence`中的`vla_act_chunk`、`executed_vla_actions>0`；返回的`rpent_pick_result`|至少执行过一次动作块；返回结果和chunk数可核对|`contact_prompt`在调用之前赋值，仅有prompt不能证明π0.5执行过；推理RPC失败和0动作返回需单独保留|
|低层未抓到目标|块边界`contact_samples`中选中物体的手指/双指接触、body-origin位置；最终私有保持的finger/clearance|可记“未采样到目标抬升/最终无手指支撑”等诊断类别|每5个动作一步块边界才采一次；不能据此断言块内部从未短暂抓住。body-origin升高不能替代最低几何真值|
|抬起不够|最终`sustained_hold.truth.checks`的`clearance_m`、`finger_contact`、`touching_original_support`|能精确报告**最终保持**有手指支撑但最低几何离支撑不足3cm|没有试抬前的最低几何快照，不能确认“不足”发生在contact阶段还是后续试抬/夹持阶段|
|试抬过程中失持|最后contact块的接触代理；`stable_visual_grasp.trial_lift_motion`的逐步接触；两帧测量；最终保持|可列“试抬中接触丢失代理”及其时间顺序|缺立即位于public stop、trial lift结束、两帧各自时刻的同步最低几何/原支撑/手指私有快照；不能可靠区分“先真抓住后试抬失持”和“先前就没满足真值”|
|视觉FN|`truth=true`且`visual_verified=false`；旧300的post measurement/opening，新stable两帧`before/after/camera/source_step`及`unverified_reason`|能精确计FN，并拆缺测、centre/lower不足、开度、freshness或近夹爪检查失败|新`passes_lower_rise_and_aperture`实际是多个条件的合取，单一false不说明是哪一项；可从已保存输入复算多数项。缺测不自动等于遮挡|
|持续条件FP|`truth=false`且`visual_verified=true`，最终保持的全体checks|能精确拆最低几何clearance、连续手指、原支撑接触、持续时间不通过，分别给计数|不同持续条件可同时失败；不得相加后称互斥终止类别。最终真值不等于之前每一个相机帧的真值|
|预算用尽|返回的`rpent_pick_result.chunks_used/max_chunks/success`|可精确标注public接触技能预算stop；和最终物理truth做交叉|末块满足stop且success=true只算“用到上限”，不是budget stop。整局步数上限与技能块数是不同预算，当前ledger没有清晰的整局实际步数stop字段|

现有300条491正式记录全部返回contact结果，因此能完整算最终真值、FP/FN及技能budget标记；不能补出缺失的阶段性持续真值。在493新版本中，使用测量把手可能新增“stage测量不可用，contact未调用”的行，应作为前置覆盖/执行路径结果显式报告，不说成π0.5低层抓取失败。

## 需要主代理决定是否补的最小诊断字段

本任务不改probe。若要严谨归因“试抬失持”，下一份独立源码中至少需要以下**私有诊断标签**；不得进入状态、候选或控制逻辑：

1. contact入口/返回/异常的phase事件，以及`contact_started`和执行动作数。当前`evidence["rpent_pick_result"]`、`stable_visual_grasp`在整段helper正常返回后才赋值；试抬或视觉RPC中途异常可能使已经完成的contact结果和部分帧不被保存。
2. public stop之后、5cm试抬之前的同步私有快照：目标最低碰撞几何、原支撑接触、手指接触、sim_time；试抬结束再保存同样字段。已有body-origin和原始全接触日志不能完整还原那一时刻的最低几何。
3. 两个视觉验证帧各自时刻的同样私有快照。这样才能区分相机测量漂移、试抬失持、两帧间物体滑落和后续0.5秒私有保持中的滑落。

仅保存单帧私有快照仍不构成0.5秒持续抓取真值；阶段快照用于因果定位，最终登记真值继续原样报告。若需要“contact阶段已达0.5秒真值”的判断，必须事先登记保持测量时刻及其物理干预，不可把诊断保持偷偷插进当前固定实验。

## 后续失败分类分三条轴

1. **物理结果/主原因**：基础设施与真值未知单列；contact前置未通过；contact后最终物理失败按最终真值条件归因；最终持续抓取成功。需要阶段快照才能升级“试抬失持”的精确因果类别。主类别互斥，组合条件另列。
2. **验证器结果**：TP/TN/FP/FN/unknown。FN不是新的物理失败；FP也不能从物理失败数里删掉。
3. **执行路径标记**：contact是否进入、执行块/动作数、public是否提前success、是否用到上限、是否budget stop、trial lift完成、相机缺测/不新鲜、开度/近夹爪检查。此轴可以和物理结果重叠。

现行summarizer的`failure_counts`混有物理失败、visual FN和visual FP，本来就不是互斥分区；不能按该字典相加生成“总失败数”。`grasp_attempted`只检查回执tool是grasp/regrasp，未执行contact的把手前置早退也会计入，因此它不能单独证明已执行100次首次抓取。分别列“注册场景数/类型化抓取请求数/contact已进入数/至少一个动作块执行数/已知完整真值数”。

## 确认汇总指标与边界

每个已锁定物体类别配方，应在预登记、与探索批不重合的原版初始状态上确认；每类≥100次首次抓取。确认数据不与探索包混算，不以后验类别赢家拼接宣布通过。

应报告：planned、recorded、完整真值数、unknown和基础设施错误数、实际首次contact执行数、唯一原版状态数、与探索批重合数及逐状态身份/哈希；逐类真实成功数/已知真值分母、Wilson95%CI；全包实际配比和成功率；逐类与总体TP/TN/FP/FN、agreement；FP/(FP+TN)、FN/(TP+FN)各自分母（分母0时为null，不写0%）。

门槛继续按用户指定的点估计：**确认批总体真成功≥95%、每类≥90%、验证器一致率≥95%**，Wilson区间用于报告，不擅自改成区间下界门槛。完整确认不得有未运行/未知真值记录被隐式删掉；未执行或缺测等原始结果保留，基础设施故障不能写成模型0分。未完成批的已知真值成功率可作中间统计，但不能触发通过。类型化请求数不等于物理首次contact次数，未达到要求的实际次数需明确写“确认未完成”，不删前置失败来改分母。

当前summarizer的`meets_user_grasp_gate`只检查known=planned、名义grasp_attempted≥100、点估计阈值；**没有检查purpose为确认、每类≥100唯一新状态、与探索批零重合或配方已锁定，也没有校验每条choices SHA**。它可以为探索包输出qualifying_conditions；该字段不得直接当正式确认资格。它按condition分组，单一moka探索包的qualifying仅代表该类别，不代表全部六类的整体配方过线。

493明确`purpose=original-only moka discovery`，每arm50个官方init各reset两次，是300次探索试验；所有数据留在探索侧。新probe仅在case携带`state_sha256`时校验原版bddl/init资产哈希及状态字节哈希，这为未来确认提供身份校验，但本身不验证与探索集合不重合。正式确认应显式用`(suite, task, original asset revision, state_sha256)`身份审计，不能只用seed编号推断新状态。

## 本次证据与读取身份

读取时源码SHA（尚未冻结）：

- probe：`3e656bd8e972b7bacb8884efca6c72393c27be8be6330165bc8238feadcb530e`
- summarizer：`621c27361c120edc8dda5fb0f4666d837be486769e989f2872618d41366f8c09`
- 493 preparer：`49af437cb537fd6ac3e2c718aa9f8e30c327b2035b97fa4ce62d98cebbabaee3`
- 491逐例数据：`results/harness_v5/grasp491_moka_CPU_20261005/report_v2/trials.jsonl`，SHA `fe2d18badd844db79ee38709f362747271fecb9ae6de70f58ce229be314fa07d`。

预算交叉复算实际CPU命令：在本机repo用`.venv/bin/python`显式读取上述491逐例文件，按`public_stop.budget_failure`与`true_sustained_grasp_unchanged`交叉Counter，300行；结果为C真成功/失败2/1、B1/4、BA1/6。没有重新跑物理或更改任何标签。

已随后按主代理新增授权实现独立前缀脚本：`scripts/diagnose_v5_grasp494_prefix.py`。它只对能确定的最终物理条件、原始视觉标志与技能stop做三轴统计，明确把`trial_lift_loss_causal_label`保留为不可识别；不补造阶段性真值。主代理负责下一份源码和正式确认汇总实现；共享COORD勘误、commit和push由主代理统一处理。

## 3616固定前50条探索前缀实际结果

采集时间：**2026-10-05 19:06:09 UTC（12:06:09 PT）**。从`grasp490_pan_retry1_20261005/full_job3616/part0`和`part1`的原ledger各一次读取字节，取最后完整换行内的**最前50行**，另存新目录；不按结果筛选、不动态追读，不更改原ledger。读取时原片分别已有60与59条闭合记录，后面的10与9条不进入本固定前缀。100/100已闭合choices SHA通过，100/100完整私有真值已知。

|探索条件|固定前缀真成功|Wilson95%CI|原始视觉标志一致率|FP/真失败|FN/真成功|contact实际执行|contact前置拒绝|public技能budget stop|
|---|---:|---|---:|---|---|---:|---:|---:|
|original_pan_name160（centre）|43/50（86%）|73.81–93.05%|100%|0/7|0/43|50|0|0|
|original_pan_handle160|32/50（64%）|50.14–75.86%|98%|0/18|1/32|42|8|0|

物理主类别：centre为43真成功、3最终无目标抬升/手指支撑、4有手指但最低几何clearance不足；handle为32真成功、8把手前置测量未通过而没有调用contact、10最终无目标抬升/手指支撑。未判定“试抬失持”，因为阶段性私有快照缺失。

执行轴：centre的50次和handle的42次实际contact均public early_success；其中最终真失败分别7与10次。8次handle没有public contact stop记录，不记成budget stop。两组执行/基础设施错误均为0。

原始标志一致率98%包含8条contact未调用且原始`visual_verified=false`的TN；它不是8次已执行的视觉验证正确。仅供路径诊断的contact执行子集为handle32/42真成功、TP31/TN10/FN1/FP0，一致41/42（97.62%）。**完整方法分母仍然是原注册前50场景，主成功率仍32/50，不删8个前置失败，不用32/42替换。** 两种口径均不能替代正式100/arm，更不能用于确认准入。

产物：`results/harness_v5/grasp494_live_prefix_CPU_20261005/preparation/`保存两个原始固定前缀；`report/summary.json`保存读取时间、raw-read SHA、prefix SHA、原文件字节数、已闭合行数和三轴统计；`report/trials.jsonl`保存100条简洁分类，不dump运动轨迹。

- 原part0读取SHA：`a4f7daf6203a245f1fd160d4c64f9d64e94781d5b2b73f4d5ce075575deb65a7`；固定50行prefix SHA：`23f23feb7014d64ab42fc90bdeabe4961f5d5a125c1458049349189372841ab0`。
- 原part1读取SHA：`7ee0822234b09a195070f6b252b50816f91f23fc19b5513313cc1a0f027ec562`；固定50行prefix SHA：`e3a50b588a494321dd8d5cd93bc7dc9cb55c95b467c7869e2e825cbea62edcb3`。
- 脚本SHA：`bc657282926ac7c1deb327e03c7c346b318d5a3be518dac2870e3e05d2f0800f`。
- summary SHA：`b575bbb8d44f7435cf4c680159dd8009d10dbfa68229571c12799ebb347bc582`。
- trials SHA：`713d9f6e139eff8d4045ed8d442c75910d306f0cba3fe5f5498a1d7238d78fdb`。

在`gpu5880-ts:/public/home/sunyihan/rpent_libero_eval`实际执行，exit0：

```bash
.venv/bin/python scripts/diagnose_v5_grasp494_prefix.py \
  --ledger results/harness_v5/grasp490_pan_retry1_20261005/full_job3616/part0/episodes.jsonl \
  --ledger results/harness_v5/grasp490_pan_retry1_20261005/full_job3616/part1/episodes.jsonl \
  --prefix-rows 50 --expected-per-arm 100 \
  --output results/harness_v5/grasp494_live_prefix_CPU_20261005
```

独立前缀工具已运行和核对；原版新初始状态确认、100/arm全量汇总、共同运行时接入与冻结仍未由本CPU任务完成。未读取PRO/密封文本，未修改现有作业，未提交或推送。
