# Codex3：技能层独立确认批预回执（2026-10-05）

接受 10/05 12:20 的技能层改动要求：确认门槛保持总体 95%、每类 90%、运行时验证器与私有物理真值一致率 95%；抓取、开合、放置确认批与选择批分离，历史探索和失败全部保留，不把 Slurm `COMPLETED` 当作技能成功。融合默认开启；公共状态不写仿真真值，私有真值只用于确认统计。

当前状态：3670 八片仍运行，`ArrayTaskThrottle=8`、无节点绑定；3678–3683 已登记为 `%8`、无依赖/节点绑定并等待资源。3616/3619 已结束，不能再更新 throttle，历史配置保留。SoM 及 v6 图像包尚未达到准入，旧训练包不入训。

本回执登记两组新的 LIBERO-90 原版独立确认批，使用 `init10–39`，逐状态 SHA 与 3550 选择批及彼此去重；原版句子、平底锅/摩卡壶测量把手接近、`frying pan`/`moka pot` 物体叫法、完整原版子任务句、320 动作块预算均在冻结 recipe 中。两批各 100 个首次抓取请求，结果按真值 sustained grasp、运行时 verifier、FP/FN、Wilson 95% CI 统计；资格仍未授予，需与已登记四类确认共同闭合。

## 计划提交

|组|作业|依赖|manifest|manifest SHA|输出|
|---|---|---|---|---|---|
|frypan|新数组（Slurm 返回后填写）|无|`results/harness_v5/grasp535_remaining_confirmation_CPU_20261005/frypan/full.json`|`92f6a9cc86135361ba8dedb6bfb4be40d562ad547cd6591d311e22d4e0f86887`|`.../frypan/confirmation_job<JOB>/part0–3`|
|moka_pot|新数组（Slurm 返回后填写）|无|`results/harness_v5/grasp535_remaining_confirmation_CPU_20261005/moka_pot/full.json`|`ef7e22819cde9a9d12e627663df842d86f5c2aaf97bba4f9c1f482d4aabb106e`|`.../moka_pot/confirmation_job<JOB>/part0–3`|

两数组均使用 `/public/home/sunyihan/rpent_libero_eval/runtime_launchers/run_v5_grasp535_remaining_confirmation.sbatch`，`array=0-3%8`、1 GPU/片、无节点绑定。源码快照为 `/public/home/sunyihan/rpent_libero_eval/source_v5_skill535_confirmation_20261005`；关键 SHA：`harness_v5_eval.py` `ed761a0d0c05a27f92ec0a2c3fc0b199034954fd7e8afc9c976d269dc7ab9654`，`v5_runtime.py` `42d69b7f4836819e259ffec782e7997a827ae5fac5cf52b8774dc0833994d7bc`，`v5_state.py` `f3c1790bb3ba92e6376b2f5591fff81a53f09831468f250618d3802e93d01e68`，`v5_action_effect.py` `c82f78b26568fffb17c5db1a253357eb54177afdb55f5b1ce7239ac2381be47d`，launcher `533c54eeb9482ce2e379244f4072e0011407351f69f9fdd3c93754495281c166`。

异议/限制：3670 的 219/400 report7 及 pan/moka 探索都不是确认结果；SoM 39/50 且 v6 包 `full_training_admission=false`，不能替代图像准入；开合/放置各类 ≥100 确认批尚未完成。因此不提前声明冻结、不提交训练。
