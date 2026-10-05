# Codex3 子任务回执：3619_3 零调用基础设施修复，2026-10-05

3619_3 的首个 original90 确认回合因严格 env metadata 匹配缺字段启动失败。原失败 ledger 保留：`results/harness_v5/grasp492_first4_confirmation_20261005/full_job3619/part3/episodes.jsonl`，SHA256 `5f3cb5b1fc393ebab232c09c7739d9933f560fbd55045e14c286d36f2d9805b9`。确认零 contact 调用后才准备重试，不把启动失败算作模型成绩。

根因链：harness 正确给 oracle server 加 `--original90-grasp-diagnostic`；server metadata 带 `original90_grasp_diagnostic_v1=true`。Generic LIBERO 连接器只构造 suite/task/seed/max_episode_steps 四字段。`BaseEnvClient` 执行整字典严格相等，故失败。

唯一 payload 差异：V5 client 在 `expected_meta.suite=libero_90` 且该标志未显式提供时，加 `original90_grasp_diagnostic_v1=true`。任务 65、seed 10、max_episode_steps 10000 等原字段不改；显式 false 不被覆盖，其他 task/seed/预算/未知字段继续严格匹配，输入字典不被修改。普通原版 40 任务也不静默接受额外诊断标志。

独立快照：`/public/home/sunyihan/rpent_libero_eval/source_v5_grasp502_mug_meta_retry_20261005`。从 3619 旧 source 复制，`diff -qr` 确认只修改 `robots/libero/v5_env_client.py`；该文件 SHA256 `556d0ceb8df9b1da98635c04a81b9187eb8a8deeccfc5b30f2d65c2438611f5e`。不加入融合、完整宏或新抓取配方，不改已完成确认回合。

注册：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp502_mug_meta_retry_20261005/preparation/retry.json`，SHA256 `cb1a3c72f016787ad1be08428b1c3520c25c0bc6379c5123eb50e33973cbdf5a`。使用原确认 manifest `dfa8c31e0568d52e9ffb19ca4d7d338284eb08460aa6424e523d9fe012a67ac9`，仍为 `--shard-index 3 --shards 4`，只重试该 mug 100 个预登记请求。

launcher：`scripts/run_v5_grasp502_mug_meta_retry.sbatch`；1 GPU、8 CPU、不绑定节点。输出为 `results/harness_v5/grasp502_mug_meta_retry_20261005/retry_job${SLURM_JOB_ID}/part3`。子代理未 sbatch；由主代理先写 COORDINATION 并推送，再提交。

实际验证：`.venv/bin/python -m pytest tests/unit_tests/robots/libero/test_v5_env_client.py tests/unit_tests/robots/libero/test_v5_subtasks.py tests/unit_tests/robots/libero/test_v5_skill500_preparation.py -q`，42 passed。新增测试覆盖 original90 必需字段、所有其余 metadata 严格匹配、显式 false、原字典不变，以及普通套件拒绝额外 flag。未运行物理确认回合。
