# Codex3：fixture526修复开发预提交

沿3655/fixture526回执，已接受用户统一冻结和独立确认要求，无异议。先修原版开发：4类开合×3init×2arm共24请求；不得把初始已经满足记新成功，setup和first均记录requested/opposite真值，未知/反向变化保留。修的是shell冒充门面和单技能native-term截块，不改变正式评测的原生成功规则。

源码快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_fixture526_original_direction_20261005`，commit `fe702b922f798f3c96479f6aced8c5b419d26155`，tar SHA `812bef39088443ab1115f5e73b602e4cc85759c602a8a3029c488a6eb3018548`。manifest SHA `df08c26b7d161ef254233d61d36eaf50c919b1fcfd8a4f50edb6745bfc54d111`，runner SHA `7389cbbd02ef64778b8c1ce2a6ae187c6cecc85488c3edf113f4b62a016aebb4`。具体prepare路径和私有/公有边界见已登记3655回执。

GPU预约3片×1GPU8CPU90GB/2h、array0–2%8，无节点绑定/依赖；目前3670八卡运行不改，新独立原版开发在空卡自动启动。先push本回执和3655回执，append远端COORD；同步/核source manifest和producer SHA后提交并立即补jobid。未冻结、非确认、不入训练。

实际计划命令（cwd远端repo）：`FIXTURE526_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_fixture526_original_direction_20261005 FIXTURE526_MANIFEST_SHA=df08c26b7d161ef254233d61d36eaf50c919b1fcfd8a4f50edb6745bfc54d111 sbatch --parsable scripts/run_v5_fixture526_original.sbatch`。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/fixture526_original_direction_20261005/probe_job<Slurm返回号>/part0–2`。解释器远端repo `.venv/bin/python`，入口快照 `-m scripts.probe_v5_fixture526_original`。20 focused CPU tests通过；真实开发结果尚未运行，不能称开合技能过线。
