# Codex3 子任务回执：3628 零动作私有计量绑定修复，2026-10-05

3628 metadata 已通过，但首个红杯确认回合在 contact 前抛出 `ValueError: target has no unique private diagnostic binding`。ledger 只有 1 行，`chunks=0`、`executed_vla_actions=0`、`contact_samples=[]`；不计为模型或抓取成绩。原 ledger 保留：`results/harness_v5/grasp502_mug_meta_retry_20261005/retry_job3628/part3/episodes.jsonl`，SHA256 `0c5ee547ac9bb6e1f79894774e29b509c033c0941a1aca182785ab734aec4906`。更早的 3619_3 ledger SHA256 `5f3cb5b1fc393ebab232c09c7739d9933f560fbd55045e14c286d36f2d9805b9`，同样保留。

定位证据：`mug_libero_90_t65_s10_confirmation` 的公开选择为 `grasp(e74,direct)`，公开类别 `red coffee mug`。可见表面测量中心 `[-0.1844482421875, 0.0291900634765625, 0.53466796875]`；私有 `red_coffee_mug_1` body origin 为 `[-0.21224065772885592, 0.017612525126619375, 0.4385990213862531]`。类别唯一且 XY 相差约 3.0cm，z 定义相差约 9.6cm，原 3D 距离约 10.06cm 刚超过私有绑定门限。物体存在于 `OriginalOracleFacade.grasp_contacts()` 返回值，非家具过滤、漏物体或服务器错误。

只修复公开选择之后的私有诊断绑定函数 `contact_binding()`：比较 XY，保留 exact category、10cm 半径、2cm nearest-match 唯一性差；同类别同 XY 叠放对象继续拒绝。未改变公开实体、候选、专家选择、抓取配方、预算、真值成功或判定门槛。

独立快照：`/public/home/sunyihan/rpent_libero_eval/source_v5_grasp507_mug_private_binding_retry_20261005`。以 old492 为基线，`diff -qr` 只有 `robots/libero/v5_env_client.py` 和 `scripts/probe_v5_grasp449_20261005.py` 两个文件不同；后者 AST 删除 `contact_binding` 后与 old492 完全相同。旧回合与旧快照不改。新源码中的 Python cache 与 old492 一致，launcher 禁止写 pyc。

同一确认 manifest SHA256 `dfa8c31e0568d52e9ffb19ca4d7d338284eb08460aa6424e523d9fe012a67ac9`；`--shard-index 3 --shards 4` 仍是 mug 的 100 个预登记请求，不增加或换确认状态。

注册路径：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp507_mug_private_binding_retry_20261005/preparation/retry.json`，SHA256 `fa32a221426229aea7c6a2d88be0a9e20fd863d1f7fdc8f269ae1a7bd1728076`。
源码 archive：同 preparation 的 `source507.tar`，SHA256 `d15e3635c3f8b957c8b19ec71a3458ae412daf90f424feadb562eb09ce7f262a`。
client SHA256 `556d0ceb8df9b1da98635c04a81b9187eb8a8deeccfc5b30f2d65c2438611f5e`；冻结 probe SHA256 `a607a8713280bc9f57898bd8a2f56fdb6a07c0fb85e74a708702d9893f1c641f`。

launcher：`scripts/run_v5_grasp507_mug_private_binding_retry.sbatch`，SHA256 `4d2705a18cd4940159a65a5df3ca410513d47934914f90ab512f3332ffcc2d45`。实际命令 `sbatch scripts/run_v5_grasp507_mug_private_binding_retry.sbatch`；1GPU、8CPU、无节点绑定。输出 `results/harness_v5/grasp507_mug_private_binding_retry_20261005/retry_job${SLURM_JOB_ID}/part3`。子代理未提交作业或推送，交主代理先登记 COORDINATION 并推送再提交。

验证命令 `.venv/bin/python -m pytest tests/unit_tests/robots/libero/test_v5_grasp_probe.py tests/unit_tests/robots/libero/test_v5_env_client.py -q`，63 passed。测试复现原红杯数值并覆盖类别、半径、叠放和 nearest-margin 歧义。物理确认尚未运行。
