# Codex3：平底锅公开lower边界与持续几何真值诊断

显式读取3550_10/_11两条完整ledger，共200次，逐条choices SHA核对；0新物理、0模型调用、0训练行，原标签不改。

B high10/short真成功8/100，原验证TP8/TN55/FP37/FN0、一致率63%。37个FP中37个body-origin升高≥3cm，37个hold窗口有手指接触，32个最终双指接触，7个仍碰原支撑，只有3个在hold窗口的任一时刻最低几何离支撑≥3cm，0个持续满足。证据支持“中心升高但最低几何未持续离支撑”，不支持把这些例子一律认作机械臂错检。

BA frying-pan别名真成功70/100，原验证TP70/TN10/FP20/FN0、一致率80%。20个FP中19个body-origin升高≥3cm，17个最终双指接触，20个hold窗口有手指接触，2个仍碰原支撑，2个曾达到最低几何离支撑≥3cm，0个持续满足。

离线反事实单帧lower-rise≥3cm＋开度2–70mm＋新可见测量，B为TP8/TN81/FP11/FN0（一致率89%），BA为TP70/TN25/FP5/FN0（一致率95%）。这只是已有post-skill测量上的离线计算，不是新在线验证器准确率，未执行额外试抬或第二帧，也未改变真成功率。单帧lower规则仍会误判；3565两帧试抬smoke保持原依赖，不能用离线统计替代真实物理验证。

示例trial3：公开中心升高5.52cm、lower升高3.027cm，实际最低几何在hold窗口最小clearance只有2.258cm；有真实手指接触，但不满足已登记持续真值。完整逐例公开/私有测量、原回执与choices哈希保留。

输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp484_public_lower_CPU_20261005/report.json`。

报告SHA256 `1f20528085748cf722a52f6cccf64fcb5b8e47ac0433fa89aeb642400620b00a`；脚本SHA256 `bf7f6cc9ae4ce042b8b3d3323d0e161f02869d4aa87ac12a1b20c74ac4303d4f`。运行命令：

```bash
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python /public/home/sunyihan/rpent_libero_eval/runtime_launchers/diagnose_v5_grasp484_public_lower.py --ledger /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part10/episodes.jsonl --ledger /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part11/episodes.jsonl --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp484_public_lower_CPU_20261005/report.json
```

95/90/95未达标；不修改当前正式数组、默认runtime、回执格式、训练或评测标准。
