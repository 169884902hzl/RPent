# Codex3：摩卡壶初始姿态与原版句子对照预回执

继续接受10/05 12:20的技能层、测量回执、双视角融合和独立确认门槛，无异议。已读取3670 report5/6的闭合中间结果、原版90访问池及已登记3678–3682。已有作业不改、不重复提交；当前未冻结、不提交训练。

摩卡壶centre完整子任务的独立首访问仅抓取6/11、最终目标5/11，先隔离π0.5的语言/初始姿态分布。新增8个原版libero_10 task2请求：init0–3各两种句子，均保持初始机械臂姿态、不先高处接近、完整160块。一臂用现有transfer模板，一臂透传该原版任务实际原句（含灶台打开）；必须与运行时公开instruction匹配。期间持续抓取、最终放置、全任务solved分别记录。这是复用原版开发状态的小规模机制诊断，不是独立确认，不入训练。

源码快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_moka530_original_prompt_20261005`，commit `ec9b572d74fab246abbdf0e92bfecc51463f3ed4`，source tar SHA `09bc99ff4221b07d83ed5a4c4c26d47c588616555c071e9339bceaa49f6a95c7`。manifest `results/harness_v5/moka530_initial_pose_prompt_original_20261005/preparation/probe.json` SHA `7a89769d0383bdf690f9a12f82366933282770f4d672f78c33b7e7fbbb670fbb`；runner SHA `e1eb84ab197a996f852ff10311e242a9f63e9c596aa7b4322faf8425689d44a9`。

GPU预约4片×1GPU8CPU90GB/2h，array0–3%8，无节点绑定/依赖，空卡自动启动。先推送本回执、append远端COORD，再同步独立源并核SHA后提交。尚无作业号，Slurm返回后立即登记；不编造待提交号。实际计划命令（cwd远端repo）：

```bash
MOKA530_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_moka530_original_prompt_20261005 MOKA530_MANIFEST_SHA=7a89769d0383bdf690f9a12f82366933282770f4d672f78c33b7e7fbbb670fbb sbatch --parsable scripts/run_v5_moka530_original_prompt.sbatch
```

输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka530_initial_pose_prompt_original_20261005/probe_job<Slurm返回号>/part0–3`。解释器远端repo `.venv/bin/python`，入口快照 `-m scripts.probe_v5_skill501_original`。56个focused CPU tests和bash syntax已通过；物理诊断尚未运行，不能称技能达标。
