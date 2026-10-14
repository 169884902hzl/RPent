# Robot Decider / Codex3 暂停交接

用户于 2026-10-14 08:30（America/Los_Angeles）决定暂停 Robot Decider。本次仅做 CPU 收尾和本地 Git 提交；不提交、释放或重提 GPU 作业，已挂起作业保持挂起。推送须另获用户确认。行为尚未冻结。

实现仓库：`/home/agilex/cobot_magic/rpent_libero_eval`，分支 `harness-v5`。收尾前 HEAD 为 `32cd3d7`（2026-10-09）。远端根目录以下记作 ROOT：`/public/home/sunyihan/rpent_libero_eval`；仿真解释器为 `ROOT/.venv/bin/python`。共享协调文件为 `/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md`。

## 抓取确认批：关闭，381/500，不改判

五类共 500 个登记状态，成功 **381/500（76.2%）**。用户操作分桶为成功 381、测量未知 25、失败 94。原始真值、公开回执和操作失败分类各自保留；不得把操作分桶倒写成私有真值标签。确认批已关闭，失败保留，不补跑、不用之后的测量或新判据改判。

原始记录：`ROOT/coordination/grasp_geometry_confirmation_event_closed_20261010_r2/fiveclass/rows.jsonl`。该目录 `manifest.json` SHA256：`645ce7f7aa95dca1030753736c05a327b2cd315e2a92319e395d375162231f0d`。后续 119 个旧状态的独立开发重放只用于补测量，不能混入该确认批分数。

补测量的已有结果：119 个登记状态中实际执行技能 114 次，114/114 保存了完整逐控制轨迹，`whole_skill_trace_not_saved=0`；另外 4 个碗绑定失败、1 个杯子几何拒绝，没有执行技能。旧锅 16 例在新的开发重放中自动确定初始支撑面后 unknown 为 0。详细路径：`ROOT/coordination/grasp_measurement_development_closed_20261011_r1/`、`ROOT/coordination/grasp_measurement_development_stages_20261011_r2/`；[测量收尾说明](grasp_measurement_closed_handoff_20261011_r3.md)。

## 统一流程 r7：14 个完整配对，改善 0、退步 7

这是选择池中间结果，不是确认批。锁定方法与统一流程在相同的 14 个状态上：双成功 6、双失败 1、改善 0、退步 7；配对成功为 13/14 → 6/14。该中间报告总共收录 134 条尝试（locked 120、unified 14），不能以两个不等分母的总平均代替逐状态配对。

| 类别 | 布局种子 | 原方法 → r7 真值 | r7 回执原因 | 已能确认的失败阶段 |
| --- | ---: | --- | --- | --- |
| 瓶子 | 9301109 | true → false | `no_collision_free_opposing_grasp` | 对夹候选/路线筛选没有保留可执行方案，未闭合 |
| 瓶子 | 9301126 | true → false | `no_collision_free_opposing_grasp` | 对夹候选/路线筛选没有保留可执行方案，未闭合 |
| 瓶子 | 9301140 | true → false | `analytic_route_pregrasp_above_23_not_reached` | 预抓取路线点未到达，未闭合 |
| 瓶子 | 9301180 | true → false | `no_collision_free_opposing_grasp` | 对夹候选/路线筛选没有保留可执行方案，未闭合 |
| 瓶子 | 9301198 | true → false | `no_collision_free_opposing_grasp` | 对夹候选/路线筛选没有保留可执行方案，未闭合 |
| 瓶子 | 9304020 | true → false | `no_collision_free_opposing_grasp` | 对夹候选/路线筛选没有保留可执行方案，未闭合 |
| 平底锅 | 9301400 | true → false | `no_collision_free_opposing_grasp` | 对夹候选/路线筛选没有保留可执行方案，未闭合 |

六条筛选拒绝不是“接触后打滑”；拒绝码本身也不能证明真实场景无可行抓取。是否属于点云边界、自身点污染、碰撞筛选或数值 IK 的误拒绝仍须靠保存的候选和路线证据继续区分。9301140 尚不能仅凭未到达标签断言 IK 无解或碰撞阻挡。

14 条 r7 公开验证：TP 3、TN 1、缺测 10，一致 4/14；FP/FN 为 0 不表示验证器通过。五类选择池尚未各达 95%，不能开启新确认。

证据：`ROOT/coordination/unified_route_paired_interim_20261011_r7_t1/`。

- `manifest.json` SHA256：`d6eabc86fbae693479c3fa14cafd587a116bb486ae8865b399e1adece1f8d575`
- `paired_states.jsonl` SHA256：`091256738935d27145b49272c43282c65d7dd5ebc1f272d702b1b1ab5cc69709`
- `regressions_only.jsonl` SHA256：`e2a385ad001a936856ac8f5a5a13adc30248fe1e077ca53388ad2a813aecc4e9`，含逐状态完整 SHA 和失败阶段。
- r7 快照：`ROOT/source_v5_unified_route_selection_20261011_r7`；tar SHA256：`cb1112e5e1e491d333b574d4ec9c8789fd0ca028817b1b19b255df86462ca806`。

## r9 快照：10/11 取消，无物理结果

- 源码目录：`/public/home/sunyihan/rpent_libero_eval/source_v5_unified_route_selection_20261011_r9`
- 归档：`/public/home/sunyihan/rpent_libero_eval/source_v5_unified_route_selection_20261011_r9.tar`
- 归档 SHA256：`5090f0431f4e620803e475bcd9e5bba5f5e496a714da68b7d3816d24e815801f`，本次 CPU 收尾已重新核对。
- 配置 SHA256：`ea88d3b672bbc7672768a3167eac3409c94695245a59d80ae3d982328f5fdd61`
- 运行目录：`ROOT/results/harness_v5/unified_route_paired_selection_20261011_r9`
- 6882–6886 在 10/11 全部于 PENDING 状态取消。`sacct` 回读均为 `CANCELLED by 2004`、`Start=None`，取消记录为上述运行目录的 `superseded_before_physical_pad_fusion.json`（SHA256：`3169d4b4cfd743cb324c1670e2febaf4334a601b405e0eabe176e066c4319d64`）。**没有 r9 物理结果**，CPU 预检不替代物理验证。

r9 增加五类共用的 PCA 两侧斜视点恢复、完整扫掠检查和公开数值 IK。视点恢复仍共享原 160 步额度，接触路线仍 300 步，力限制不变。核心实现为 `robots/libero/v5_grasp_observation.py`、`v5_analytic_grasp.py`、`v5_grasp_geometry.py`；准备入口为 `coordination/prepare_unified_observation_source_20261011.py`。当前本地工作树另含后续改动，不能把当前文件直接称为 r9 快照。

后续 r10 必须单列：其 tar SHA256 为 `f04cf171326a32d004802bb36f5c8356511d52e50e2e9d2d5075b333b9d51cb0`。本次只读查询发现启动 6887–6891 以及正式数组 6917/6919/6920/6921/6923 已完成，保存了物理请求与逐次记录，目录为 `ROOT/results/harness_v5/unified_route_paired_selection_20261011_r10`；这些不算 r9 结果，也不改写上面登记的 r7 中间统计。尚未在本次收尾中生成 r10 完整配对结论。此前“r10 首次增加双视角 pad 并集”的描述不准确：旧实现已跨两视角累计支持并集，r10 主要增加注释、回执元数据及覆盖既有行为的测试，不能称其已修复杯子缺测。原取消记录中的历史理由保留，以上说明纠正其解释。

## 其他冻结项

| 项目 | 已有结果/缺口 | 暂停状态 |
| --- | --- | --- |
| 灶台开/关 | 未找到完整新确认通过证据；到终点后继续执行导致状态反转、撤离后时序复测仍待验证 | 未冻结 |
| 抽屉开/关 | 缺测、身份保持和到终点停下的问题未形成完整新确认通过证据 | 未冻结 |
| 微波炉门 | 跨帧/跨视角门与柜体身份、门平面测量及终点停止仍未形成完整新确认通过证据；`microwave_verified_selection10_20261009_r1` 不能视为已通过 10 局 | 未冻结 |
| 摩卡壶转移 | 选择批放到位 **85/100**，Wilson 95% 区间 76.7%–90.7%；公开验证 FN 85、TN 7、缺测 8，一致 **7/100**，召回 0；无公开阳性，精确率不可计算 | 未通过；不得把选择批当确认准入证据 |
| spatial_task | A3 十局配对 **1/10 → 2/10**，改善 1、退步 0；小样本不能据此认定问题已解决 | 未冻结 |
| 放置 | 目标身份、footprint 与遮挡缺测修复尚缺完整新确认通过证据；首次放置 ≥90%、严格验证器精确率 ≥95%仍待确认 | 未冻结 |

摩卡壶证据：`ROOT/coordination/moka_terminal5768_closed_20261011/manifest.json`，SHA256 `443350b77c330a845ae1bf1d5b1eaf3454390193a0d72f3b564568e6db1791bf`；逐次记录在同目录 `attempts.jsonl`。该批为 `selection_only=true`。

spatial 证据：`ROOT/coordination/spatial_binding_A3_pair10_closed_20261010/manifest.json`，SHA256 `32f107c9e27ffc35a5bb8dfe1f3110f3249002ab0f3b95c2199ca11db5baab6f`；同目录 `paired.jsonl`。

门槛统一称为**内部门槛**：抓取/开合总体 ≥95%、单类 ≥90%、验证器一致 ≥95%；摩卡壶按转移技能单列。门槛不下调。选择批不授确认资格，已关闭确认不重跑、不改判。

## 确认状态永久排除训练

暂停不撤销隔离。所有已登记确认状态的布局参数、随机种子、状态 SHA 和几何身份永久排除训练；未执行、失败、unknown 以及后来转为诊断使用的确认状态也不回流。不同种子不能替代状态/几何去重。

500 状态排除表：`ROOT/coordination/grasp_confirmation_permanent_exclusions_20261010_r1/excluded_states.jsonl`，SHA256 `9cd277920b17afe18d18692e51c62035543f3a711e23a6761672bca2f411a6fe`；对应 `manifest.json` SHA256 `e6c7a589e96ff99bef3daeb86f7d4049e2018f126257b29cf297300fa3e6da13`。该表只列已执行的 500 个状态，不撤销其余已登记确认池的排除。代码入口仍为 `robots/libero/v5_confirmation_exclusions.py`。

摩卡壶既有 580100–580199、后续确认池和 Codex1 后续预留范围均继续按登记表隔离；训练布局使用不相交的 680100–689999 范围，并与每个确认布局的落定后摩卡 XY 位置保持至少 0.050 m 欧氏距离。完整状态身份和登记表优先于范围示例。[既有隔离合同](confirmation_permanent_exclusion_20261008.md)继续有效。本次不启动采集，也不声称已复核全部历史训练行。

## 恢复时第一步

获得用户明确恢复授权后，**先做 CPU 恢复盘点**：读取本交接和 `COORDINATION.md`，核对 r9/r10 快照 SHA、现有 r10 完整输出与逐状态配对、永久排除表及当前挂起作业；优先汇总已经落盘的 r10 结果，避免重复运行。核对版本后，用现有候选/整段路线证据定位 r7 七个闭合前退步，再决定统一流程的下一项修复。不要直接开新确认或释放历史挂起作业。

需要恢复 GPU 开发时，沿用当时仍有效的资源授权并刷新队列；暂停本身不授 node02 使用权，不触碰 `c5-` 作业。正式数组仍须同快照、同 launcher 真实启动到首次物理请求，失败退出码非零。选择池五类各 ≥95%后，才使用 Codex1 登记、与旧状态不重合的新确认状态判内部门槛。

## 本地保存与检查

本次把 10/08–10/11 尚未提交的相关实现、准备/统计脚本、已有单元测试和本交接逐文件保存到 `harness-v5`。提交文件清单见 `PAUSE_COMMIT_FILES_20261014.txt`。原始录像、模型权重、数据归档、复制源码快照和派生结果留在既有目录；无关 dirty tree 保留。

验证仅用 CPU：277 个 Python 文件 AST 语法检查通过；30 个已有离线测试文件合计 **577 passed，1 warning（22.93 s）**。解释器为本地 `.venv/bin/python`（Python 3.10.19），环境为 `CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`，命令为该解释器的 `-m pytest <清单中的 29 个 tests/ 文件> coordination/microwave_runtime_wiring_20261007/test_physical_exit_contract.py -q --disable-warnings`。

首次合并运行因导入顺序在收集阶段失败：MuJoCo fixture 先导入 `mujoco`，触发环境 facade 的渲染器初始化断言。按现有初始化约束把 `test_v5_skill501_complete_chunks.py` 放在测试列表首项后，所有同一批测试通过；未更改断言或测试。完整输出保留于本机 `coordination/pause_evidence_20261014/cpu_tests.log`。测试包含小型 CPU MuJoCo fixture，不是新的基准/确认物理运行。

500 条排除记录的数量、唯一状态身份、`permanent_training_exclusion=true` 和 `training_allowed=false` 均逐条核对。相关 r9 归档与交接引用的结果 SHA 已重新核对。只读队列快照在 `coordination/pause_evidence_20261014/queue_before.json`：89 个 Robot Decider 项，83 个 JobHeldUser、1 个 JobHeldAdmin、运行项 0；不释放挂起任务。本次不提交 GPU 作业，也不据 CPU 检查宣布行为冻结。

暂存检查：按清单逐文件 `git add -- <path>`，本地提交共 288 个改动文件；9 月的 `classify_results.py`、`make_episode_table.py` 等无关变更未暂存。`git diff --cached --check` 仅报告两个原有新 launcher 的末尾空行（`run_v5_grasp_measurement_development_20261011.sbatch`、`run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch`）；为保留计划/启动记录引用的 launcher 字节与 SHA，本次不格式化。
