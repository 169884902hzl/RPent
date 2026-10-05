# Codex3：摩卡壶三条件300次探索预提交回执

已读取用户10/05 11:30要求、3550全1800试次、C完整指令600轨迹和grasp491摩卡壶300次CPU诊断。接受原版物体类别技能卡、平底锅别名/把手/预算对照、C抓后行为核对以及新独立确认95/90/95门槛，无异议。当前未冻结、未准入训练。

已执行：摩卡壶C/B/BA真成功50/42/58%，验证一致80/83/69%。预算失败仅3/5/7；C主要是握持但抬离不足，B主要未抓起/未保持。3565 FN两帧都可见，第一帧视觉下界不稳。B/BA在摩卡壶上没有方法差异，不将其差值归因于别名。完整指令C有一例抓后输运到灶台并释放，下一轮使用只描述选中物体抓取的短提示。

拟提交一次新数组，Slurm编号尚未分配，提交返回后立即补记：
`sbatch --parsable --dependency=afterany:3619 runtime_launchers/run_v5_grasp493_moka_full.sbatch`。
输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp493_moka_comparison_20261005/full_job<array_id>/part0–2/`。
GPU预约：afterany3619，数组0–2%2，每片1GPU/8CPU/90GB/4h/nice1000，无节点绑定；依赖只约束最多2卡资源并行，不依赖确认分数。保持3616/3619与旧held链不变。

三条件各100首次请求：reset熟悉姿态＋短提示；high10cm＋短提示；视觉唯一测量摩卡壶把手方向接近＋短提示。统一160块预算、public stop、试抬5cm后间隔0.5s的两帧测量，lower-rise≥3cm并在夹爪附近；被拒主视角可追加新腕部证据，原始被拒测量保留。不放宽真值标准、未改默认runtime/renderer131。无唯一把手则保留未执行/unknown，不造几何。

300名义试次来自原版LIBERO-10 task2的50官方init各reset两次/条件，明确为探索，不当独立确认；预留原版LIBERO-90的100新摩卡壶状态保持未消费。不读取PRO、人工或密封文本，不采训练行，真值仅诊断标签。每片保存已执行动作、完整物理/视觉证据、FP/FN分母及异常，不把启动失败算模型成绩。

source `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp493_moka_comparison_20261005/`，源码commit `7e4787a`；入口 `scripts/probe_v5_grasp449_20261005.py::main`，解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。
archiveSHA `4d6f789c4dcb47c59e2c55d0338f99d480885b2ac64e24eb3c86cddaa939069f`；manifestSHA `df3a390cf94cca1e74d0aad4698b411ad495a5a938d2af0b4921d649aa9cba2c`；launcherSHA `0d1e5b454b3b5834f4173cd4e4c62c5ef67afb3f9938a69f6574275277b60f0a`。
58 focused checks、bash-n、diff-check已通过；此配方真实物理试次0/300，部署后核真实runner依赖import。先push本回执，远端COORD append核对，再sbatch一次。

## 实际提交

回执c079356已push并append远端COORD，部署SHA、真实runner依赖import通过后一次提交 **3620**。
实际命令 `sbatch --parsable --dependency=afterany:3619 runtime_launchers/run_v5_grasp493_moka_full.sbatch`；输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp493_moka_comparison_20261005/full_job3620/part0–2/`。
300次/三条件、最多2GPU，无节点绑定，当前PENDING Dependency，真实结果0/300。3616正在运行、3619等待3616，不修改旧链，不提前绕过依赖。source7e4787a/archive4d6f789c4dcb47c59e2c55d0338f99d480885b2ac64e24eb3c86cddaa939069f，manifestdf3a390cf94cca1e74d0aad4698b411ad495a5a938d2af0b4921d649aa9cba2c。
