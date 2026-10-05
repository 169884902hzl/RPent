# Codex3：3642杯子未访问状态续跑实际回执

631de23预回执已push并先写远端COORD，再执行 `cd /public/home/sunyihan/rpent_libero_eval && sbatch --parsable scripts/run_v5_grasp512_mug_unvisited_resume.sbatch`，返回3642。1GPU8CPU、无依赖、不绑定节点；只79个原注册未访问状态。3631前20个真实完成+第21个已执行但真值未知全部保留且排除，不重跑。

输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp512_mug_unvisited_resume_20261005/resume_job3642/part0`。源码source_v5_grasp512_mug_unvisited_resume_20261005；tar SHA238f7082ee4b870df9998cba4e4cd8d23b5e44744b8646791360bfbd134c38f6；resume manifest SHAf3a73d239a9b1bfcdd2ec9610aeb202ba57a48e1e745eedb8756e34be867c975。入口 repo.venv/bin/python -u scripts/probe_v5_grasp449_20261005.py --manifest <本批preparation/resume.json> --shard-index 0 --shards 1 --output <上目录>。与507仅私有无名geom计量修复不同。未授全100确认资格、未冻结、无新训练。
