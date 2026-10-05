# Codex3：在线动作成功率与实际回执的配对汇总

在 3550 运行期间完成 CPU 汇总入口
`scripts/summarize_v5_online_success.py`。仅使用显式 `--ledger`，
读取事件里执行前记录的独立 p_success；核对候选/index、最终选择、
pre-state SHA、问题原文、原始响应概率和执行阶段。不同候选、不同状态、
执行后评分均拒绝。未验证/unknown 不算失败；选择概率不冒充成功概率。

汇总按任务族和技能给出 AUROC、按局 bootstrap 95% CI、Brier、
ECE10、校准桶及 p_success>=0.9 的真实错误率。缺在线评分时所有模型指标
为 null，不用空样本生成“0 错误率”。只读取保存的测量回执作为结果，
这不等价于用户要求的私有持续夹持真值；本项不做抓取资格判断。

13 个针对性测试通过：配对不符拒绝、旧轨迹不冒充在线数据、
unknown 排除、动作选择概率和独立成功概率分离、按局 bootstrap。
命令：
`.venv/bin/python -m pytest tests/unit_tests/robots/libero/test_v5_online_success_report.py tests/unit_tests/robots/libero/test_v5_success_choice.py -q`。

远端真实闭合 3550_0 的 100 条原版轨迹做 CLI 合同 smoke：
`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python /public/home/sunyihan/rpent_libero_eval/runtime_launchers/summarize_v5_online_success.py --ledger /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part0/episodes.jsonl --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/prediction471_join_contract_CPU_20261005/corrected_null_metrics`。
100 条全部正确记为 no_online_prediction，计分样本 0，AUROC/Brier/ECE null。
原合同 smoke 的空样本 ECE=0 输出保留，修正后的独立子目录不覆盖它。

报告 SHA256 `f7a114203115450b14bf6d2057bcd7135ab54b0c3e7688f0f1963e068b5e4017`；
脚本 SHA256 `2f4e2be70bad3ab8341a07c48ecf5518e04f065f21f1dbd41d821fa79abb125d`。
报告拉回 `results/harness_v5/prediction471_join_contract_CPU_20261005/report.json`。
physics=0 / GPU=0 / model_calls=0 / 新训练行=0。

在线准确性仍未测，top3 选择没有启用。此代码未进入 3550/3565 快照；
不修改状态或回执。后续 A3 在通过抓取门槛后可开默认关闭的在线记录开关，
再用本入口统计真实在线结果。3550、3554、3565 依赖和 95/90/95 门槛不变。
