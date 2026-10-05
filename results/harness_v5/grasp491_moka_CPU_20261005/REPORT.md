# 摩卡壶300次首次抓取：失败与验证器 CPU 核对

已实际执行CPU分析：显式读取3550分片12/13/14，各100条完整ledger，300/300 choices SHA通过；另核3565两条moka smoke的choices SHA。无新物理试次、模型调用、Slurm作业或训练行，原始真值和回执不改。

**下一种优先验证的不同方法是测量把手方向的接近；加预算不应优先。** 保持短抓取提示、160块预算及同一停止/验证器，对照只改变测量接近点。测量不到唯一把手就记录unknown，不能虚构几何。C的reset姿态＋选中物体单独短提示是已提交3598的另一项语义控制，应按其实际结果继续，不把本CPU诊断冒充100次对照。

## 完整结果

|条件|原始真成功|TP/TN/FP/FN|一致率|误报成功/真失败|误报失败/真成功|public success但最终真值false|真正预算失败|
|---|---:|---|---:|---|---|---:|---:|
|C reset＋完整任务|50/100|37/43/7/13|80%|7/50（14%）|13/50（26%）|49|3|
|B 高处＋短抓取提示|42/100|26/57/1/16|83%|1/58（1.72%）|16/42（38.10%）|54|5|
|BA pan别名条件|58/100|29/40/2/29|69%|2/42（4.76%）|29/58（50%）|36|7|

Moka在B和BA中实际提示均为`pick up the moka pot`，接近规则、stop和预算相同；frypan alias对此类别没有作用。100个配对试次：两者均成功24、均失败24、仅B成功18、仅BA成功34。58与42之间的差不能归因于别名，也不能算作另一种方法。每条件100试次来自50个原版task2 init各reset两次，不是独立确认批。

## 失败类别（互斥的诊断主类别）

|原始真失败的主类别|C（50失败）|B（58失败）|BA（42失败）|
|---|---:|---:|---:|
|持续有手指支撑但最低碰撞几何clearance不足3cm|35|1|2|
|未记录到选中物体抬升代理，且最终无手指支撑|11|46|26|
|手指支撑没有持续|3|10|9|
|记录到双指抬升→松开→稳定支撑的代理|1|1|5|

这里的“抬升代理”是块边界的body-origin升高和接触，用于根因诊断，不替代已登记的最低几何、原支撑接触及0.5秒持续手指支撑真值。最后一类不等于正确放置或整条指令完成。

真值条件本身可重叠失败：C 48/50 clearance不达标、15/50手指支撑不达标、15/50仍触原支撑；B分别56/58、57/58、54/58；BA分别36/42、40/42、34/42。B失败58次中，技能最后32次开度小于2mm，符合空夹爪或丢失物体风险；BA为19/42，C为0/50。public stop时低于2mm只有B6和BA5，说明技能内的后续试抬/夹持也改变了实际开度，不能只用public stop开度代替最终记录。

|数值（中位/P95）|C|B|BA|
|---|---|---|---|
|public块数|40 / 119|36.5 / 149|41 / 160|
|public stop夹爪开度mm|45.89 / 59.98|14.67 / 59.52|30.52 / 76.72|
|实际技能最终开度mm|22.95 / 59.80|5.73 / 56.83|17.96 / 57.66|
|body-origin最终升高cm|3.70 / 7.35|0.10 / 10.32|5.87 / 11.53|
|保持窗口最低几何clearance cm|3.05 / 6.84|约0 / 9.71|5.50 / 11.17|

几何和手指接触均为私有测量，不进入状态或控制。public停止与最终保持是真值不同时间点，public success但最终失败统计不能单独确定物体在哪个时间点掉落。低层选错目标的代理在C/BA真失败中为0；B有1次非目标双指接触和body-origin抬升代理，不能升级为decider选错。

## 视觉误判

- C的13个FN：11个目标仍可见但测量centre升高不足3cm，2个目标缺测；7个FP中6个是centre通过但最低几何clearance不通过，1个是centre通过但手指支撑不持续。
- B的16个FN、BA的29个FN全部是选中物体最终缺测/缓存不可见，不能仅凭缺测断言是夹爪遮挡；遮挡、检测漏检或相机视角原因仍需原图/掩码核对。
- B的1个FP最低几何clearance为2.99893cm；BA一个为2.94574cm，另一例缺持续手指支撑。按原始3cm门槛保留失败，不为边界样本改判。

## 3565两帧moka smoke：不是缺测

smoke真失败的C记录两帧都可见，lower分别升4.25cm与2.49cm；第二帧不通过，与真实minimum clearance1.97cm一致，属于正确拒绝。

smoke真成功的BA记录两帧也都可见，source_step为1与2。第一帧centre升11.23cm，但lower仅升2.88086cm，因此判false；第二帧centre仍为同一1.11914m，lower升9.91211cm，判true。第一帧bbox X宽17.25cm、第二帧6.40cm，第一帧lower0.934570m、第二帧1.004883m；真实保持minimum clearance9.19572cm，持续抓取true。**漏判的直接原因是第一帧可见表面下界不稳定，不是视角缺测或已证实的source_step复用错误。** 未读取原始掩码，暂不能断言混入了机械臂或背景；应先核对该帧掩码/测量点，再确定几何过滤或重新测量方案，不直接放宽验证门槛。

该FN的choices SHA：`0bfb97a8ccf42e6e808e5f632e45965d9b73a74a70e043328174b39a3a78c7f4`。正式报告保留两帧的完整测量字段、开度及原始回执，没有保存大段运动接触日志。

## 下一比较建议及边界

从主类别看，C主要是物体虽有支撑但几何抬离不足，B主要是没有抓到或未保持；仅增加动作预算难以解决大量public启发式提前返回。优先用当前视觉测量唯一定位moka把手、从把手方向准备接近，再发同样的短抓取提示，保持预算、stop和验证器一致，与centre接近对照各100次。这样改变的是可验证的接触几何，不是alias或同参数重跑噪声。没有可验证把手时记unverified/unknown，不造坐标。

另外完成3598的reset＋selected-only短提示对照，排除完整任务提示中的继续搬运因素；不把它与高处B相混。budget应作为后续单独控制；若下一方法仍在预算之前以假success退出，先修基于测量的停止/抓取验证，而不是只扩大块数。任何运行时改动仍需独立确认批，每类≥100、总体≥95%、各类≥90%、验证一致率≥95%；本报告不授予准入。

## 实际CPU命令与SHA

在`gpu5880-ts:/public/home/sunyihan/rpent_libero_eval`执行：

```bash
.venv/bin/python scripts/diagnose_v5_grasp491_moka.py \
  --ledger results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part12/episodes.jsonl \
  --ledger results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part13/episodes.jsonl \
  --ledger results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part14/episodes.jsonl \
  --smoke-ledger results/harness_v5/grasp464_clean_receipt_20261005/smoke_job3565/episodes.jsonl \
  --output results/harness_v5/grasp491_moka_CPU_20261005/report_v2
```

- 脚本SHA：`45d49a70de6da4b0e38b478dff6546987293e646ed00ae659a7af40cade4b0c7`
- summary SHA：`46ca9ffec97d8b6e720b13d05af84af6bcd2ba9c180af1b802128ce5b6b1f8eb`
- trials SHA：`fe2d18badd844db79ee38709f362747271fecb9ae6de70f58ce229be314fa07d`
- 3565 ledger SHA：`bf7b8ab4560cb34913127c17b3df3e39948634a1fe0533d3635c3a544019d2a7`

命令exit0，完整300正式样本和2条smoke核对已完成；把手、100次新条件和独立确认均尚未由本CPU任务运行。原始report中间版保留，不改旧物理记录。
