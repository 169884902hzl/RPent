# Codex3 stove555 公共控制部件测量预回执

接受用户10/06全部条款；本次只补原版Goal7 init0–9的两视角测量，10reset/20接触/80capture/160camera views，选择开发非确认。私有qpos仅采后标签，不驱动动作、停止、公共绑定；endpoint仍unmeasured，PCA无向轴不能冒充关闭端点。无异议。

SOURCE555 b07c707（含2ca8a），archiveSHA bf0e2ac6e6b60a4fe4c4e26c53f06336982ffbaccd7d9440b24a46dc68d2ead0。manifestSHA 50fef3327c6d264d19a911ea5f3bd86807c683dab9bbbf25d4e9042874d83597；实际probe同入口从/tmp预检核33显式文件/4资源/10官方init SHA通过，CPU checks65及bash-n通过，无GPU物理尚无成绩。完整5步块/160chunks，不受native latch提前截断，外部10000步保持。

4片×1GPU，无依赖/节点绑定；全卡当前在4199完整smoke，接着4200平底锅开发，再由Slurm空卡调度，不中断回合。job由Slurm在回执推送后分配立即回报。输出 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_measurement10_original_20261006/probe_job<JOB>/part0..3。

```bash
env STOVE552_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_stove555_20261006 STOVE552_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_fixed_prefix_CPU_20261006/stove_control_sampling10.json STOVE552_MANIFEST_SHA=50fef3327c6d264d19a911ea5f3bd86807c683dab9bbbf25d4e9042874d83597 STOVE552_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_measurement10_original_20261006 sbatch --parsable --array=0-3%8 /public/home/sunyihan/rpent_libero_eval/source_v5_stove555_20261006/scripts/run_v5_stove552_measurement.sbatch
```

100格近零固定前缀方案已实现并CPU准备通过，但本次不提交；先看10局公共特征召回的物理证据。未冻结、未开训、未开始大规模采集。
