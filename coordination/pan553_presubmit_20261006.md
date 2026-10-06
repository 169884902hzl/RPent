# Codex3 pan553 10例修复开发预回执

已接受用户10/06的抓取标准、选择/确认分离、开发故障修复继续；无异议。现4148完整确认truth98/100，公共TP65 TN2 FP0 FN9 null24，验证一致下界67%不达标，保留原判。33缺口中24缺当前handle、8可见tip不在pad、1抬升/支撑证据不足；全部开度均非空，不放宽开度阈值。

本次仅10个未访问原版LIBERO90状态，开发选择，不授资格。与4148及显式旧选择/确认清单无tuple/raw状态SHA重合，计划hash 6541eab03139b37a759ff03f09691fdb4def80d27b4665446552cd77fea463a1。抓法/提示/320chunks/物理动作不变，新增pan_cross_view_handle_v1用主视角锅身与当前腕部handle联合验证。支持/抬升/空夹爪判据保持。SOURCE553 f8e5faa，archiveSHA 896327b831c282f6b5c6f74bae47da5c5d08a9faa8bb2dec7d8bd1afb7cffacd，module/probe/launcher逐SHA见JSON。8/8CPU预检从/tmp通过，state2+2+1×6=10，报告SHA ef19a586556465f60bcc0013917adbf88616710021c34d9062065d3facfa121a。

计划8片×1GPU，无依赖、无节点绑定，当前无空卡，Slurm使用后续空卡、不取消或中断运行回合。作业号由提交后立即回报。输出 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/pan553_cross_view_development10/job<JOB>/part0..7/probe。实际拟命令：

```bash
env PAN553_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime553_20261006 PAN553_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_runtime546_monitor_CPU_20261006/pan_cross_view_development10/pan_cross_view_handle_development10.json PAN553_MANIFEST_SHA=6541eab03139b37a759ff03f09691fdb4def80d27b4665446552cd77fea463a1 sbatch --parsable --array=0-7%8 /public/home/sunyihan/rpent_libero_eval/runtime_launchers/run_v5_pan553_cross_view10.sbatch
```

20局完整冒烟4199仍等待；其结果通过前不推进大规模确认/集成。pan未来100独立新状态确认仍要另登记，现有注册pool只剩44fresh状态，正在核对其他原版90场景补足，不把已访问状态算独立。
