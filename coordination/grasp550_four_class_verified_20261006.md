# Codex3 四类已有首次物理确认核清

用户 10/06 队列第 5 项：核清已有记录，没有重复提交盒子 52 次或杯子 100 次，没有新物理执行。证据 commit `fe793d1e2872b4a173ce0cc5370af2a8216443b3` 已推送。唯一 canonical 400 状态来自 manifest SHA `dfa8c31e0568d52e9ffb19ca4d7d338284eb08460aa6424e523d9fe012a67ac9`，分源和原始 infra 记录均保留。

|类别|真值成功/失败/未知（分母100）|成功率下界–上界|TP/TN/FP/FN|验证器一致率下界–上界|known 真值成功 Wilson 95% CI|
|---|---|---|---|---|---|
|瓶子|96/4/0|96%|95/2/2/1|97%|90.16–98.43%（96/100）|
|碗|98/2/0|98%|96/1/1/2|97%|93.00–99.45%（98/100）|
|盒子|99/0/1|99–100%|98/0/0/1|98–99%|96.26–100%（99/99 known）|
|杯子|93/6/1|93–94%|92/5/1/1|97–98%|87.40–97.19%（93/99 known）|

盒子/杯子各 1 个物理后诊断缺失，永久保留 unknown；各 1 个公共验证 unmeasured；不以重跑或插补获得更好成绩。杯子还有 1 个初始零物理 env-meta 故障及一个单列 private-binding 开发错误。unique canonical infra：盒子 1/100、杯子 2/100（不是 3）；两个方向误判如上 TP/TN/FP/FN。

四类合计 386 成功 / 12 失败 / 2 未知，成功率描述界 96.5–97%。四类各自点估计下界和一致率下界满足登记门槛；这不代表六类总体资格，平底锅与摩卡壶仍待物理结果。没有将四类的 Wilson 区间下限当额外准入门。

远端报告 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_runtime546_monitor_CPU_20261006/four_class_existing_confirmation/report.json`，SHA `06e94061fc6e59214ce1b8f66b98444b432278f505e236c0e9af709cf54d153d`。400 行首次物理 ledger SHA `fd13c81d66e94141cd030fddef679d08ce5f217aa35deaaab23f3d47047683f0`，2 行零物理 ledger SHA `7e214f6a630b108526134fa967ae70e941950686c04b2617c2b87c2340f8f917`。producer/index 和逐源统计在同目录，index SHA `a5a331851f80a9123ef1b1ba127fb0927e4e67b75845a886ce4879dc32a6bdc7`。

原正式报告及 receipt 均未覆盖。此交付给 Codex1 核验，Codex2 可据此保留测量标签的 unknown 分支；不授权训练。
