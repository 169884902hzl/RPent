# Codex3：3637修复后技能开发smoke实际回执

8b0099b预回执已push并先写远端COORD，再执行 `cd /public/home/sunyihan/rpent_libero_eval && sbatch --parsable scripts/run_v5_skill511_json_repaired_smoke.sbatch`，返回3637。数组0–4%8，每片1GPU，无依赖、不绑定节点。20个原smoke请求，非确认。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill511_json_repaired_smoke_20261005/smoke_job3637/part0–4`。

source commit ab33e3fe7bf5a1daaf7e8f22ab96147dc6abb75d；tar SHA a6f590c16bc884c5237bb331d2f7bc66ac7af45d847550e74e1199f88fe98c05。实际入口 `repo.venv/bin/python -u -m scripts.probe_v5_skill501_original --manifest <本批fixtures/place/grasp_subtask_smoke.json> --shard-index <0/1/2/0/0> --shards <3/3/3/1/1> --output <对应part>`，cwd独立source_v5_skill511_json_repaired_20261005。JSON计量修复后继续定位技能失败，原3630证据完整保留。未冻结、未训练。
