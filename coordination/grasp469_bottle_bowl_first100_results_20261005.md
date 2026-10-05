# Codex3：正式首次抓取分片 3550_2 / 3550_3

接受用户 10/05 03:10 的 95% 标准。3550 不取消、不修改、不重复提交；
3554 汇总与 3565 两帧视觉 smoke 保持 afterany:3550。当前 4/18 分片完成，
3550_4、3550_5 在运行，6–17 等待数组并发上限；六类资格、行为冻结仍未完成。

| 作业 / 类别 / 条件 | 真值成功 | Wilson 95% CI | TP/TN/FP/FN | 验证器一致率 |
| --- | ---: | --- | --- | ---: |
| 3550_2 / bottle / high10-alias160 | 96/100 | 90.1629–98.4337% | 95/3/1/1 | 98% |
| 3550_3 / bowl / reset-bound-full160 | 99/100 | 94.5514–99.8233% | 96/0/1/3 | 96% |

两片均 COMPLETED 0:0，分别耗时 41m57s / 38m26s。各 100 次首次抓取、
100 个唯一原版初始状态、真值全部已知、执行/仪器报错 0；逐个核对 manifest、
ledger、summary 文件 SHA。真值仍为原支撑面以上几何最低点 >=3 cm、
无原支撑接触、手指连续支撑 0.5 秒；仅为测量标签。

- bottle：实际失败 3 次未最终抬起/夹持，1 次抬起但无手指支撑。
  FP 1/4 真实负例=25%；FN 1/96 真实正例=1.0417%。
- bowl：实际失败 1 次未持续夹持。FP 1/1 真实负例=100%；
  FN 3/99 真实正例=3.0303%。FP 分母很小，不能省略分母。
- alias 对 bottle 未改变提示词；与 high10-short 的差异不能归因于 alias，
  policy noise 也未跨条件固定。三个瓶子条件不是三个独立新方法。

原始输出（不覆盖）：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part2/`
及 `part3/`。

正式报告目录：
`results/harness_v5/grasp466_remaining_completed_shards_CPU_20261005/`。
part2.json SHA256 `f29c006b57fb2c1c7cbf65d6bd580db527d4354e0b94a472d5062b4f3a651c76`；
part3.json SHA256 `16731c85c36afe29194cb4adbbba5d73cf23135879fbe904bdc52a1b49d990cf`。
报告已拉回本机，SHA 与远端一致；原始 ledger/summary 留在原路径。

固定实验源码 commit `115ba66`；源码 archive SHA256
`c024d415ac8e9eb4492d2c2cd5ee781a986c20f525a644416d43f586185ddc93`；
full manifest SHA256
`9dca2edd661ccba0d6e69efb595c8951ba9eccb16c74584e48e1007adfb175d0`。
原提交命令：`sbatch --parsable runtime_launchers/run_v5_grasp459_full.sbatch`。
本次没有新 GPU 作业、物理回放或训练行。

未完成：其余 14 分片、总体及各类门槛、3565 的真实两帧验证、后续方法、
A3/A4 新旧开发集和行为冻结。继续读取显式已完成轨迹，分析历史峰值停止
是否与失败有关；不动运行源码、不修改 RPent 原版 baseline。
