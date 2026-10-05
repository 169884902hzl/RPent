# Codex3 子任务回执：原版完整接触子任务，2026-10-05

已接受用户 12:20 的完整技能方向和主代理接口。新模块只从感知实体、中性 ID、合法模板枚举 `vla_subtask`；不读 BDDL、PRO、人工测试文本或 sealed 数据。BDDL 与原版指令只在准备器/oracle 侧登记。运行时模板入口为 `robots.libero.v5_subtasks.subtask_prompt(action, entities)`，候选入口为 `subtask_candidates(entities, instruction, eef_xyz, held, limit=6)`。

候选采用 `vla_subtask(object,target,on|in)` 与 `vla_subtask(fixture,open|close|turn_on|turn_off)`。不增加自由文字参数或单抓取宏。完整搬运执行不以初次抓住物体为提前停止条件；完整子任务完成、抓后释放、原 0.5 秒持续夹持真值分别报告，不改变原抓取标准。

CPU 实际准备目录：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill500_original_comparisons_20261005/preparation_v2/`。

| 文件 | 请求数 | SHA256 |
| --- | ---: | --- |
| full.json | 400 | 4cf765257b86229ee624499adfca72b2359bb4069331fbd9227c598061ce0b92 |
| fixtures.json | 1200 | f295e32be1391c88a8062b545e323579d5695c0f16dcafed2fa071da1eadf338 |
| place.json | 400 | 35907164206d6464e9286f85a38194526be0dc6fca91ac5b1c0c049da9b3a60b |

每个类型/arm 都是 100 名义首次请求，原版 50 个官方初始状态 reset 两次；只有 50 个独立场景，不授予确认资格。六个开合类型为抽屉开/关、微波炉开/关、炉灶开/关；放置覆盖 on/in。放置先真实执行抓取，公共验证未通过时记录 not_attempted；私有持续抓取真值只记录，不控制动作。准备器显式登记 `vla_subtask_v1`、双视角融合、深度裁剪、测量回执及测量进展阻断为 true。v1 产物保留，后续仅采用 v2。

限制：原版 40 任务中平底锅出现在 10/task2 场景，但不在该任务原目标或原句中。其 `put the frying pan on the stove` 是事先登记的原场景反事实模板，不能称为原版逐字指令；摩卡壶是该原任务搬运子句的公共类别模板。完整子句采用与运行时同一份 `subtask_phrase`，原整任务指令只留作 oracle 诊断元数据。

π0.5 训练身份的 primary 证据不是 checkpoint 名字：HF revision `6222623f635769bfc73c9472e29fab9b7fd8e027` 的 `metadata.pt`（SHA256 `8eba92f1159903755c6f529320913033a142a691bb148f90a96db0b6b91d6528`）记录 global_step=30000、`data.base_config.root=data/libero_130_fullshot`、`prompt_from_task=true`、action_horizon=10、action_chunk=5。该模型仓库没有 README/model card。RLinf 固定源码 revision `c70606f08cdca259b8dec03d4430926b5b8fac9d` 的 `docs/source-en/rst_source/examples/embodied/libero.rst` 第 62–97 行明确 130 是五套件组合，包含 LIBERO-90；文档 SHA256 `f309274954c61153dd3d0e030affd1252cf3225db6ba4f8e99b9f9ee4e22462a`。

现场 `/public/home/sunyihan/rpent_libero_eval/assets/pi05/metadata.pt` 同为 3236 bytes，SHA256 与 HF 固定 revision 完全一致。因此注册训练配方包含 LIBERO-90，不能称 π0.5 在确认中的 LIBERO-90 任务完全未见。公开仓库未提供原训练逐任务/逐 episode manifest，实际曝光量没有独立复建。证据报告：`results/harness_v5/skill500_original_comparisons_20261005/provenance/pi05_training_identity.json`。

实际命令为登录节点 CPU `.venv/bin/python scripts/prepare_v5_skill500_original_comparisons.py --base-config <3414显式config> --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a --output <preparation_v2>`。因远端主工作树不含当前 v5 模块，本次用旧 492 独立源码解释器搜索路径，并注入本次新模板模块后运行准备器；不启动环境、π0.5 服务或 Slurm。相关 CPU 单元测试已通过；执行器由主代理集成，物理验证尚未运行。
