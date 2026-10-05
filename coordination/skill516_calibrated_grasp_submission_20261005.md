# Codex3：516真实标定抓取与完整子任务开发smoke预回执

已接受10/05 12:20统一技能层、回执、融合、原版对照和独立确认要求；门槛不变。当前NO-GO、未冻结、无新训练。3636和3643已结束，3642仍运行，旧确认已访问且计量未知回合保留不重跑。

开发候选commit `0badcf37ab88e1e35e22b1855cf7b72738dbeff8`：新抓取路径只读独立每视角测量、同步robot0_eef_pos/quat/qpos；使用原版空夹爪范围与公开静态刚体标定，保持39维π0.5输入。宽开度点阈值尚未物理校准，保持unknown；缺证据不回落旧验证器。平底锅需测得下沿离开原RGB-D支撑面。两帧间公共10步hold，不由私有接触真值控制。旧抓取与旧快照不改。210 focused CPU tests通过，不能代替物理资格。

源码快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_skill516_calibrated_grasp_20261005`，source516.tar SHA256 `3a1e4a0b3edab45487911a6ab04d6aa4b895775e415273a0c1b9890dd7be8d86`。516的four-case smoke manifest SHA256 `57a8860dd0777803eedfffcbfd1e7ec427761a3af19a7e8338c1f94c6415d70e`；完整400探索manifest `a493a63045abc7b79ea6e351ed40d75c2b70736679edbf94cf05508056a13175`。每pan/moka×centre/handle nominal100，但50独立原版场景重复，不能授确认；训练行0。

GPU预约：smoke array0–3%8，每片1GPU8CPU，不设Req/ExcNodeList或依赖，使用当前空卡，不修改3642。先push此回执并append远端COORD，再提交；实际作业号由Slurm返回后立刻补记。

实际计划命令（cwd远端repo）：

```bash
SKILL516_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_skill516_calibrated_grasp_20261005 SKILL516_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill516_safe_subtask_exploration_20261005/preparation/smoke.json SKILL516_MANIFEST_SHA=57a8860dd0777803eedfffcbfd1e7ec427761a3af19a7e8338c1f94c6415d70e SKILL516_SHARDS=4 sbatch --parsable --array=0-3%8 scripts/run_v5_skill516_safe_subtasks.sbatch
```

输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill516_safe_subtask_exploration_20261005/exploration_job<jobid>/part0–3`。入口快照中 `.venv/bin/python -u -m scripts.probe_v5_skill501_original --manifest <smoke.json> --shard-index <0–3> --shards 4 --output <part>`，解释器为远端repo `.venv/bin/python`。完整子任务不在抓住时提前停止，私有持续抓取轨迹与最终放置分开。无异议，尚未全部完成、无物理达标声明。回执/恢复变化已在开发候选登记，冻结后必须新物理采集。
