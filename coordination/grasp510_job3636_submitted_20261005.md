# Codex3：3636盒子未执行状态续跑实际回执

预回执ccb18b0已push并先写远端COORD。实际命令 `cd /public/home/sunyihan/rpent_libero_eval && sbatch --parsable scripts/run_v5_grasp510_box_remaining.sbatch`，返回3636；1GPU，无依赖、不绑定节点。只续原注册52个未执行状态trial48–99。第48个已执行但真值未知回合保留，不重跑。

输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp510_box_remaining_20261005/remaining_job3636/part2`。入口为source_v5_grasp510_box_remaining_20261005内由repo.venv/bin/python执行 `-u scripts/probe_v5_grasp449_20261005.py --manifest <本批preparation/remaining52.json> --shard-index 0 --shards 1 --output <上目录>`。manifest SHA cd93583d546deb434c6233ab57367f8c510098ac3e8430b88478a33290a6f48a；truth SHA e4523ec989398dbc1433cf1e97842a8ebbcf2af467a0c6f9ee56b1f165d25137。与固定old492逐文件diff仅私有truth文件变化。未授完整100确认资格、未冻结、无新训练。
