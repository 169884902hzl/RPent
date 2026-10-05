# Codex3：525原版类别抓取集成smoke预回执

已读10/05 12:20全部技能/回执/融合交接，接受95/90/95独立确认、开合与放置门槛、原版专家190/200和统一冻结。当前NO-GO、未冻结、无新训练。旧确认的未知和失败不重跑。此批12请求只开发验证运行时集成，不授资格、不入训练；无异议。

source `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp525_category_runtime_20261005`，commit `9e392d3931cbdcc4d13803914f4db4214401ab85`（runtime类别接入fb86a88+owned probe9e392d3），archive SHA `4d0715468ecf702ddb9a04ad2316bacdfc0cd20549d7945e7ab0042b15a8e140`。runtime SHA `7e90b7200c9e07fae3a4ae03f339095925ae667ae27959b13e131888b02e51a8`，probe SHA `3d6ead34e62ee8970c082ba642910bc12ee098d8ab0f7cb0c58fe3d60e504b97`，launcher SHA `4fe6b4988f847b8b9c0a68d8e7ccdb502093ed6636525cf050f7535442d81edd`。

manifest `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp525_first4_runtime_smoke_20261005/preparation/smoke.json` SHA `2b1097366c0097a71ceead869cc45c4927a524760036560ec1f88132e31ce451`。原版40任务内碗/瓶/盒/杯每类2个初始抓取+1个公共retreat/EEF偏移后的恢复，共12；mug来自Long t4/t6原版，不读PRO或90文件。C原始target_first完整句，B短类别句，均pi0_pick160；新的公共独立验证器/calibration513启用，阈值缺校准仍null。C中途公共EEF回位是新增干预；无真值回位、无私有done控制policy。双视角融合开启，同刻私有contact仅诊断，0.5s持续夹持真值在公共动作之后独立测量。CPU focused200+owned53 checks通过，不替代物理验证。

GPU预约4片×1GPU8CPU/90GB，array0–3%8，无节点绑定、无依赖；3670仍全8片运行，不取消修改。Slurm按空卡自动启动。先push此回执并append远端COORD再提交；作业号由Slurm返回立刻补记。

实际计划命令（cwd远端repo）：`GRASP525_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_grasp525_category_runtime_20261005 GRASP525_MANIFEST_SHA=2b1097366c0097a71ceead869cc45c4927a524760036560ec1f88132e31ce451 sbatch --parsable scripts/run_v5_grasp525_runtime_smoke.sbatch`。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp525_first4_runtime_smoke_20261005/probe_job<jobid>/part0–3`。解释器远端repo `.venv/bin/python`，入口快照 `-m scripts.probe_v5_skill501_original --manifest <smoke.json> --shard-index <0–3> --shards 4 --output <part>`。每个失败保留、开发bug继续修复。
