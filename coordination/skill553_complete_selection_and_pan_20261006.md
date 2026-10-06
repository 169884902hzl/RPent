# Codex3 开合完整选择批与平底锅确认结果（不授冻结）

4128八片全部COMPLETED0:0，1200/1200注册条目完整；真实首次接触786（before均false），到达端点619。414条绑定/setup缺失全部保留。两方法按drawer close/open、microwave close/open、stove on/off逐类真值及Wilson见正式summary。旧SOURCE544有610条短块，628800请求步实际301449；100条stove_off first前native latch；新完整5步预算不可与之冒充单因素比较。

公共验证TP199 FP8 FN0 TN38，541次unmeasured（真420/假121）。全known一致237/786=30.15%；measured条件一致96.73%不替代全分母，不隐藏unmeasured。代码错误0，当前最大类是414绑定/setup缺失，已执行失败167。正式路径 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill549_live_CPU_20261006/20261006T134800Z/job4128/ ，reportSHA cdb013ac1d9e70236db1836b1a39f9b12c453b5e9448cc45c85dda3c0f76c668，complete_evidenceSHA 5df3d029063ceabaa510956c9c1a768852ae14eeaf8695ca9cadd59941897b43。

4148平底锅独立确认100首次物理已全部完成：truth98成功/2失败，Wilson92.999–99.450%；TP65 TN2 FP0 FN9，unmeasured24，一致率下界67%，即使把24未测全算一致上界也仅91%，未达95%。infra0。原判全部保留，不重跑改善资格。最小修复是主视角测锅身/腕部测把手的同捕获跨视角绑定；5d812cf开发开关已CPU检查20通过，仍待选择池物理验证，之后另独立100确认。报告原版本SHA c8d1df1ad191c9c2881d5029db8dc14457a9c9a882986bc6e8d9f864533474eb；源位置 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_runtime546_monitor_CPU_20261006/observed_1352UTC/pan_confirmation。

统计修复只补从first_receipt.error读取旧零物理AttributeError，不改原字段和物理标签；修后pan仍98/2，报告 b2ea4b6a20e3d7f297a10cdf1caa6ee5d179054080c5dff0b3522bcc1b9ad7f1，独立旧开发错误2、infra0。

用户门槛保持：各类首次成功≥90%、总体≥95%、验证器一致≥95%。全技能未过门槛，所以不提交集成资格、不冻结、不开始新训练和采集。Codex1/Codex2请据显式产物核验。
