# Codex3：历史峰值停止的保存轨迹核对

CPU 显式读取 7 个 ledger：3491 / 3520 / 3545 的 90 次 smoke，
3550_0–3 的 400 次正式首次抓取。逐条核对 490 份 choices SHA，
其中 430 次使用 RPent public pick，60 次用其他停止逻辑，按队列分别报告。
重算 public pick 的逐 chunk 最低点和历史最高点，与保存的诊断值匹配。

仅发现 2/430 次：历史抬升已超过 5 cm，但最后一个 Pi0 chunk 的当前
抬升不足 5 cm；其中 1 次是正式瓶子 trial49（真成功），1 次是 smoke
平底锅 trial0（真失败）。后一例当前抬升 1.9674 cm、历史抬升 13.4254 cm；
前一例当前抬升 0.9784 cm、历史抬升 6.6744 cm。公开 pick 停止后 caller
还可能执行试抬，因此不能用 post_robot_measurement 代替 Pi0 最后一块。

这支持“历史峰值可能早停”的局部假设，不能解释其余 22 次 public-pick
真失败，也不能证明改成当前高度就有因果收益。本次不修改 RPent 原版
baseline，不修改 3550/3565 固定快照，不提交新 GPU 作业。
全六类正式实验未完成；平底锅的正式 100 次结果还没有。

执行入口：`scripts/diagnose_v5_grasp470_public_stop.py`，远端同文件
`/public/home/sunyihan/rpent_libero_eval/runtime_launchers/diagnose_v5_grasp470_public_stop.py`。
使用 `--ledger` 指定上述 7 个文件、`--output` 指定新文件，禁止扫描 artifacts。
源报告保留 report.json；report_v2.json 修正 0.2 mm 舍入带的说明、区分
public pick 未使用与缺少轨迹，并将 smoke / 正式分片分开统计。

报告：
`results/harness_v5/grasp470_public_stop_CPU_20261005/report_v2.json`。
SHA256 `8be8e6d38df72ca258621cff92bd815ec3049b79c38c7b2399064fce26d0e2f6`，
本机/远端一致。保存全部 case、public diagnostics、chunk 重算值、输入 SHA；
私有真值只作为已有标签读取，physics=0 / policy=0 / 新训练行=0。

继续按每片真实失败分类推进；预算或 alias 不计为新的独立方法。
3550_4/_5 仍在运行，3554/3565 保持依赖；未通过资格，不冻结、不跑 A3/A4。
