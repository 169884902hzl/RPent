# 专家 fallback 尊重当前候选（job4417）

范围：仅 `robots/libero/v5_oracle_policy.py`、该模块的窄测试与本记录。

真实来源：

- manifest：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/interim574_20261007/preparation/repair_r4/expert_part2.json`
- episode：`libero_object / task8 / init0`。
- 原始 `choices.jsonl`：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/interim574_20261007/expert/job4417/part2/probe/libero_object_t8_s0/choices.jsonl`，SHA256 `f62c3ceec6865ed6696faa0101abe02d436fa8907cc372a842a0a5ed947e18c4`。
- 原始 `result.json`：同目录，SHA256 `4dbdea68c5ec4427b21947379bb8c2579da43a1761971782dce513550a7fc8a7`。

错误原文：`ValueError: Candidate(tool='ask_help', object=None, target=None, mode=None) is not in list`；位置是 r4 `harness_v5_eval.py:621` 的 `choices.index(action)`。原始17条决策与失败终态保留。

根因：源 `e54`（chocolate pudding）和目标 `e114`（basket）均已绑定，但源的两种抓取和 restage 已因失败屏蔽。决策15、16连续 `ask_help`，均为 `help_unavailable / no_effect`，随后该动作也被屏蔽。专家的空 grasp fallback 却直接构造 `Candidate('ask_help')`，并未从当前候选中查找。其他 place、articulate、closed-storage fallback 存在同一问题；finish/release 的无默认 `next` 也会在动作被移除时抛 `StopIteration`。

修复：匹配成功仍返回当前列表中的原对象。fallback 先查当前 `ask_help`，不存在则复用既有 `_recover_missing`，再查已有的 clear_view / reperceive / wrist_scan / retreat；不恢复被禁用动作，不修改预算。无受支持的可用动作或恢复时，抛 `NoLegalCandidate(ValueError)`，类别属性为 `no_legal_candidate`；完成后缺 finish 同样明确报无合法完成候选，不执行其他运动。harness 的异常类别接线不在本子任务所有权内，已通知主代理。

窄证据：`python -m pytest tests/unit_tests/robots/libero/test_v5_oracle_policy.py -q` → **47 passed**（0.28s）。覆盖真实前缀、各 fallback 分支、非 persistent 的耗尽恢复、无候选，以及完成后缺 finish。另有现有 pytest 配置 `timeout` 插件未装的警告，不影响本检查。`git diff --check` 通过。

真实前缀 fixture：`tests/unit_tests/robots/libero/fixtures/oracle_blocked_help_job4417.json`。它使用最后保存的公开测量、全部17条必要回执、私有原版 oracle 标签，以及“最后保存的 options 减 terminal blocked_actions”重建失败前候选；**失败的第18个请求本身未保存，不能声称逐字节复现该未落盘请求**。重建前缀选到列表中的 `clear_view()`，不会再合成 ask_help。

SHA256：

- policy：`070a4a692ddf4af99f364f63a5366276928f4c78623c86049bb04c4c0beaca8d`
- tests：`274232f8d48d607f0e4aee9f8eba0486578d01e7b81885f11118ce614515ac36`
- fixture：`e682ecf3d84db342b318284f3327cea50869253a076a1bdadc99e91705fee3fe`

下一次物理复现：主代理为修复版建立新不可变快照，以同一预算和显式单局 manifest 开发重跑 `libero_object/task8/init0`，保留4417原记录。检查进入同类屏蔽状态后所选 action 在当前 candidates 内；若恢复全部耗尽，应正确记 `no_legal_candidate`，不再出现候选 index 异常。本子任务未提交 GPU 作业，也未声称已做新物理验证。
