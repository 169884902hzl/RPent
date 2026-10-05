# Codex3：3643公共endpoint开发smoke实际回执

d171369预回执已push并先append远端COORD，再执行 `cd /public/home/sunyihan/rpent_libero_eval && sbatch --parsable scripts/run_v5_skill515_public_endpoint_smoke.sbatch`，返回3643；数组0–4%8，每片1GPU，无依赖、不绑定节点。五片均已RUNNING（node01/02），总20请求。

输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill515_public_endpoint_smoke_20261005/smoke_job3643/part0–4`。source commit c8b5bc5c86f3c661d417036ad6da5eec1945060c；tar SHA588baac5938b46414e4f71c1f2bda150928df6dd6d57c7019540c617318eae8e。入口source_v5_skill515_public_endpoint_20261005内 repo.venv/bin/python -u -m scripts.probe_v5_skill501_original --manifest <fixtures/place/grasp_subtask_smoke.json> --shard-index <0/1/2/0/0> --shards <3/3/3/1/1> --output <对应part>。不是确认、不是评测成绩；未冻结、未训练。
