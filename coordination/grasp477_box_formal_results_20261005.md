# Codex3：盒类两个100次正式分片闭合与失败分类

3550_6/7 均 COMPLETED0:0，耗时41:34/39:42；100次首次抓取、100个唯一原版
状态/分片，私有持续夹持真值全部已知，执行与仪器错误0。
原始回合不改；仅诊断标签含仿真真值，不入运行时/训练。

|条件|真成功|Wilson95%CI|TP/TN/FP/FN|验证器一致率|FP/真实负例|FN/真实正例|
|---|---|---|---|---|---|---|
|reset/full|68/100|58.3374–76.3309%|55/32/0/13|87%|0/32=0%|13/68=19.1176%|
|high10/short|100/100|96.3007–100%|100/0/0/0|100%|0/0，不可估计|0/100=0%|

reset/full 的32次真失败全部是目标无最终抬起/持续支撑；全部 public pick
宣告success，动作块预算用满0次。其中24/32有非目标物体双指接触及
body-origin升高>=3cm的代理证据。该代理不建立全碰撞几何离地与0.5s夹持，
不是非目标物体的完整真成功标签；也不是decider选错对象，probe先选了正确对象。
余下8次无此代理证据，不硬补原因。13次视觉FN全部measured_z_rise_cm=null，
夹爪开度均在2–70mm内，优先核验视觉缺测而非放宽开度。

示例：Long1/init0选择butter，完整低层提示词仍带cream cheese/basket，
实际观察到cream_cheese代理；Long7/init0选cream_cheese，观察到alphabet_soup；
Long6/init1选chocolate_pudding，观察到porcelain_mug。原prompt及选择/接触证据
逐行保留。独立selected-only smoke3598已排队，不凭这些例子认定因果修复。

产物：
`results/harness_v5/grasp466_remaining_completed_shards_CPU_20261005/part6.json`，
SHA256 `e13ff24d732e58d6b7f685c59d5062da5c831ad3739e64e1c5259b7f5ae1093c`；
part7 SHA256 `d76312dee786eefee4b9b8a7afe2c9fb7547e2640c4d9b46ed4ae44c1e451f63`。
固定source115ba66，manifest9dca2edd661ccba0d6e69efb595c8951ba9eccb16c74584e48e1007adfb175d0。

CPU接触诊断脚本 `scripts/diagnose_v5_grasp475_target_contacts.py`，commitbe5a51f；
显式读取闭合ledger，逐个核对choices SHA，没有glob/新物理执行/模型调用。
报告 `results/harness_v5/grasp475_target_contacts_CPU_20261005/box_completed_6_7.json`，
SHA256 `d2c2354392f15f1c1e574b6bebfd2c18f35c0ddf40d0037256d7d15abd0315d9`。
瓶/碗600条CPU诊断报告bottle_bowl_completed.json SHA256
`05de82c47aea24f2cd42e24de3a5cbf324ad2afcecabc3e9c1b5d9903691a6d0`；
单独瓶类alias有1次真失败用满预算，其余公开停止假阳性的解释不能一概归预算。

状态：正式8/18分片闭合，800/1800条；3550_8（盒alias）/9（平底锅reset）运行。
3554、3565、3591、3598依赖保持，不重复提交。
reset/full 因盒68%及验证器87%不达标；两个high10条件因碗86%/84%不达标。
不是完整六类成绩或冻结资格，其他类尚未完成；不后验拼各类赢家。
95/90/95标准保持，A3/A4复测、严格place完整物理复验、行为冻结、训练准入未完成。

更正：逐项读取full.json核对了18个分片索引，_9是frypan，不是此前回执误写的mug。
9–11=frypan，12–14=moka_pot，15–17=mug，前三组条件依次reset/full、high10/short、
high10/alias。frypan和moka_pot各100次但只有50个唯一初始状态（各重置两次）；
其他四类100次/100唯一状态。只更正文档类别，不改原始日志或分数。
