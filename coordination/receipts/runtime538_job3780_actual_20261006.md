# Codex3：3780 实际提交

预回执c7cc6cb已推送并追加远端COORDINATION，8片CPU预检均通过后提交3780。新20局：原版10 + D2开发init41 10；每片1GPU，array0-7%7，无依赖，无ReqNodeList/ExcNodeList。当前3734剩1原生片，释放后提高到8。

实际命令：`SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime538_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime538_smoke20_20261006/preparation sbatch --array=0-7%7 --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_runtime538_20261006/scripts/run_v5_runtime536_smoke20.sbatch`。

输出：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job3780/part0..7`。源码commit b5ab18a、source-only archive e5961ddb4d38295b0de90e7c30cea2e148cae5edb7c7b30d5f313f3fe894c535；manifest ce6f73e509f631c2e460d47752b45c2220f29e95209e0de086883b5f11d836eb；v5@750权重b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb。预算不变，未冻结、未训练、大批技能仍待冒烟质量结果。

摩卡壶当前五种不同原版选择方法的物理证据：reset纯抓取短句63/100、高10cm中心短句40/100、高10cm测量handle短句17/100；完整转移子任务中心/handle接近，期间持续抓持41/100与31/100（最终On子谓词34/100与21/100单列，不冒充持续夹持）。选择批每100名义尝试对应50官方初态各重复2次，不是独立确认。3685独立确认持续抓持60/100，不能宣布通过；本轮继续明确指定的腕部精修、融合handle yaw、完整原版子任务三法选择，报告相关重复状态。标准不降低。
