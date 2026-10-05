# Codex3：碗类正式 100 次结果与边沿对照准备

3550_4、3550_5 均 COMPLETED 0:0，耗时 37m35s / 37m37s；
各 100 次首次抓取、100 个唯一原版初始状态、真值全部已知、执行报错 0。
逐文件核对 manifest、ledger、summary SHA；报告远端/本机一致。

| 碗类正式条件 | 真值成功 | Wilson 95% CI | TP/TN/FP/FN | 一致率 |
| --- | ---: | --- | --- | ---: |
| reset-bound-full160，3550_3 | 99/100 | 94.5514–99.8233% | 96/0/1/3 | 96% |
| high10-short160，3550_4 | 86/100 | 77.8628–91.4737% | 86/11/3/0 | 97% |
| high10-alias160，3550_5 | 84/100 | 75.5797–89.9047% | 84/13/3/0 | 97% |

两种 high10 条件低于每类 >=90% 门槛，不能用验证器 97% 的一致率冒充
物理抓取达标。alias 只改平底锅词汇，碗类两个 high10 条件实际相同；
2 次差异不能归因于 alias。

- high10-short：11 次未抬起/夹持，3 次未持续夹持；FP 3/14 真实负例
  =21.4286%，FN 0/86。失败分布 Long3=9、Goal4=2、Goal1/3/8 各1。
- high10-alias：13 次未抬起/夹持，3 次未持续夹持；FP 3/16=18.75%，
  FN 0/84。失败分布 Long3=8、Goal1=3、Goal3/8 各2、Goal4=1。
- 全部 30 次 high10 真失败均在 public pick 宣告 success 后发生，
  动作块预算用满 0 次。因此此轮不优先增加预算。

原始输出：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part4/`
与 `part5/`，全部原回合保留。
报告 `results/harness_v5/grasp466_remaining_completed_shards_CPU_20261005/part4.json`
SHA256 `ac75d0c673e4d8c975a7703966470c678d3a9b4c49f85252ab991282d5569b72`；
part5.json SHA256 `bc3fe08005d351b38f8b337388b0797ca2316fdf6f4e282ff96a05abb89ef925`。
源码仍为固定 `115ba66`；manifest
`9dca2edd661ccba0d6e69efb595c8951ba9eccb16c74584e48e1007adfb175d0`。

原版 Long3/init0 的对照证据：reset/full 初次闭合 EEF x=-0.0051，
high10-short 初次闭合 x=0.0443；目标测量 bounds 中心 x=0.0467。
前者在容器边沿附近最终真抓住，后者在中心闭合但目标无最终抬起/支撑。
这只是“进入空心容器中心”的候选根因，不是单例因果结论。

独立 probe 现已加默认不启用的 `contact_approach=measured_rim`：
对 bowl/mug/ramekin 用已有 RGB-D measured_rim_point 的观测边沿，
其余类别保留注册的 bounds-centre 位置；缺观测不虚构边沿。
入口 `scripts/probe_v5_grasp449_20261005.py::measured_rim_approach`。
不读取私有接触、仿真物体坐标、BDDL 或 PRO 来选择位置。
36 项 binding / verifier / perception geometry 测试通过。
这是对照准备，真实物理验证未执行；不计为已完成的新方法，不改变默认
runtime，不进入 3550/3565 的固定源码。计划后续 smoke 只改边沿位置，
保持相同 standoff、提示词、预算和停止规则，先验证此假设。

当前 6/18 正式分片完成，3550_6/_7 已按原队列运行盒类，8–17 等待。
3554、3565 保持原依赖。总体六类资格、A3/A4 新旧复测和行为冻结未完成；
没有任何门槛降低、旧结果覆盖或训练准入。
