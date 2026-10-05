# Codex3：平底锅闭合前缀诊断，非正式100次结果

3550_9仍运行；从原始episodes.jsonl显式捕获前30条已闭合记录到独立目录，
不读取半行，不把live文件SHA当最终SHA，不改原轨迹/判定。
CPU脚本逐条核对choices SHA，0新物理执行/0模型调用/0训练行。

前30条：1次真持续夹持、29次真失败；29次均无目标双指接触，最终最低碰撞
几何升高仅约3e-10m，无非目标物体接触+升高代理。24/29次public pick宣告success，
5/29次用满160动作块。原始失败标签不变，这不是完整条件成功率或资格。
pan对象为chefmate_8_frypan_1；GSO类默认free关节，且已有一条真实离支撑并持续
夹持的成功证据。不改质量、接触、资产或标准，继续区分姿态/可夹持部位与词汇。

下一假设仅用当前RGB-D的可见把手测量，不读仿真物体坐标、BDDL或PRO决定接近点。
两个新probe组共享frying pan别名、短提示词、160预算和public stop；只改变平底锅
的接近点（bounds centre vs measured handle），其他类保持原control。
测不到唯一把手则unverified，不虚构位置。48项相关测试通过，真实物理验证未运行。

远端前缀与报告：
`results/harness_v5/grasp478_pan_prefix_CPU_20261005/preparation/part9_first30.jsonl`，
SHA256 `c9f3062a960d1d70c4237a30c589761c7d396ac3a2de9317828aef32e24fc0a9`；
capture.json SHA256 `c02f7468f1a1a5ff6320c52fc1265977affe435d48007434197284e0dc350459`；
report.json SHA256 `af39b0b24bd7306d36859a505d3fe0812be4862a18cf481cbaa395bf050924c6`。
诊断脚本SHA256 `0e2ba0fa69e20d644576bbd8737e8d406b87308e61cd5fcf654921e0c5150985`。
元数据与诊断报告入Git，完整捕获prefix留持久目录；不重复生成物理状态。

95/90/95门槛及100/class正式测量不变；预算/alias/同族参数不计五种已完成方法。
3550/3554/3565/3591/3598均不修改，当前不做A3/A4、不冻结、不准入训练。
