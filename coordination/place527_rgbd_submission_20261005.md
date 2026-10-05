# Codex3：527原版放置双视角证据开发预回执

已接受10/05 12:20技能层、测量回执、融合、独立确认与统一冻结条款，无异议。当前NO-GO、未冻结、无新训练。已读取3670闭合report3/4及place525、pan526公开几何报告；旧记录、判定、正在运行的3670和已排队3678/3679/3680全部保留。

新增12个原版libero_10 task2 init0–11探索请求，用同一centre完整子任务160chunks。每次既有capture后在同一RGB-D上重新查询所选stationary target，并保存object/target逐视角cloud、SAM mask引用、RGB/world/camera文件SHA、前后机器人测量和分开的private predicate。现有public strict6不改，不用private标签选mask或控制动作。缓存旧cloud记录原source_step，不能因外层新step改记current。现有world为float16、未存raw metric depth，证据明确记录该限制。此批复用原版开发状态，不是独立确认批、不入训练，不宣称放置精确率已达标。

GPU预约4片×1GPU8CPU90GB/3h，array0–3%8，无节点绑定或依赖。资源不足自动排队，已有八卡3670不动。预回执先push、append远端COORD，再同步独立源/manifest逐SHA核对并提交；真实jobid返回即补记。

源码快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_place527_dual_rgbd_20261005` commit `2fc95d7a67654f2d60a2c3c7f9f8f5a308ce9764`；source tar SHA `129c60fcc75d288c1044528d9223d2ecb244104f794e6f8463fc0705f264f2ae`。manifest `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place527_dual_rgbd_original_20261005/preparation/probe.json` SHA `2308a1cff778cf39409c01dec5d4a808ce8bc1bb9909fd231c31712077e2a134`。probe SHA `55a9d35a8fe5d3e3d039c278f2cf2bb3210434c5974ab7e15c1803c58ec038f9`，evidence helper SHA `a4c85e1825949914ecfb03047310603f12f8934727a1b3fa7396b515522fa6e5`，runner SHA `6566c578c0ec01293c265a8fb547b4e920e673e59874e3885012697565f7ca3f`。

实际计划命令（cwd远端repo）：`PLACE527_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_place527_dual_rgbd_20261005 PLACE527_MANIFEST_SHA=2308a1cff778cf39409c01dec5d4a808ce8bc1bb9909fd231c31712077e2a134 sbatch --parsable scripts/run_v5_place527_rgbd.sbatch`。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place527_dual_rgbd_original_20261005/probe_job<Slurm返回号>/part0–3`。解释器远端repo `.venv/bin/python`，入口快照 `-m scripts.probe_v5_skill501_original`。

CPU实际验证：`.venv/bin/python -m pytest tests/unit_tests/robots/libero/test_v5_place527_evidence.py tests/unit_tests/robots/libero/test_v5_skill501_original.py -q`，54通过；`bash -n scripts/run_v5_place527_rgbd.sbatch`通过。新物理运行尚未发生，不把这些开发接口检查当技能成绩。
