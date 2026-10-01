# LIBERO-PRO × RPent typed-choice 零样本评测

状态：2026-09-29。Main15-v1 冻结主结果保留：2323 0/20、未训练 4B 0/20、Jev 8/20。pilot5 原样留档；后续开发轨迹不改分。LIBERO 训练暂停，等待 MuJoCo v4 新语义数据和验证结果。

## 已跑通

- 独立仓库：`/home/agilex/cobot_magic/rpent_libero_eval`，分支 `spike/typed-choice-no-memory`；RPent 基线 commit `71f5775d7cef0a3d38ca642f90512cc4f0dc6e74`。未修改或推送 `robot_decider_instruction`。
- `.[libero-pro]` 已安装到独立 Python 3.10 环境；`LIBERO_TYPE=pro` 加载 `liberopro`。Pi0.5、SAM3 和 LIBERO-PRO 资产在 node02 本地；Slurm 固定 `node02`，harness 修正和第 1、2 步判定每个作业只申请 `gpu:1`，三个决策组用依赖串行排队。第 3 步训练暂缓，等待 MuJoCo v4 配方验证表；训练授权恢复后最多申请 4 张卡。
- `typed_choice_eval.py` 用 RPent `LiberoToolkit` 执行工具与官方成功检查，保留每步候选、Choice 概率、工具回执、官方终止结果和完整 `episode.mp4`。`qwen_choice_service.py` 分别加载冻结 2323 和未训练 Qwen3.5-4B，读取候选字母 logits；`jev_choice_service.py` 使用本机官方客户端，node02 走反向隧道。
- 作业 `2363` 的开发期 smoke：`libero_spatial_swap` task 0、seed 0、2323 官方成功，2 次决策；这条轨迹不计正式第一批成绩。其完整视频已复制到 `results/initial_task0/dagger2323/episode.mp4`。

## 评测合同

| 项目 | 本轮设置 |
| --- | --- |
| 套件 | `libero_spatial_swap`、`libero_object_swap` |
| 样本 | 每套件 10 个任务索引 × 每任务 seed 0 一回合，共 10 回合/套件/模型；**不是**官方每任务 50 回合 |
| 模型 | 冻结 2323、未训练 Qwen3.5-4B、官方 Jev 1.13.0 |
| 成功判定 | 只取 RPent `LiberoToolkit.solved()` / LIBERO 官方环境终止；工具自己的 `success` 只是过程回执 |
| 记忆 | 关闭：只向 toolkit 传不存在的逐回合只读空目录，planner 不调用 memory API |
| 训练 | 零样本；不在 PRO 扰动配置或评测轨迹上训练 |
| 运行 | node02 `--gres=gpu:1`；Pi0.5、SAM3、Qwen 占该卡，MuJoCo 环境步进在 CPU，EGL 渲染使用同卡；主结果每回合最多 15 次 planner 决策。训练不在本阶段启动 |

## Main15-v1：原结果留档

冻结 harness 后运行。所有完整回合保留失败；没有用重跑或删失败回合改变分母。主 job `2465`（两个 4B）和 Jev job `2466` 均已完成。

| 决策模型 | Spatial Swap | Object Swap |
| --- | ---: | ---: |
| 冻结 2323 | 0/10 (0%) | 0/10 (0%) |
| 未训练 Qwen3.5-4B | 0/10 (0%) | 0/10 (0%) |
| 官方 Jev 1.13.0 | 5/10 (50%) | 3/10 (30%) |

合计成功率：冻结 2323 为 **0/20 (0%)**，未训练 Qwen3.5-4B 为 **0/20 (0%)**，官方 Jev 1.13.0 为 **8/20 (40%)**。在当前冻结 harness 的 20 个固定 seed 回合中，Jev 高于两个 4B；2323 的失败分类以决策错误为主（16/20），另 4/20 为技能执行。只读候选冗余也是 harness 因素，不能把差距单独归因于模型。已先调用 `segment` 不等于感知正确，也不能排除技能问题；这组对比不能解释为 SFT 导致退化。每任务只测 seed 0 一回合，非完整官方评测。

所有 60 个回合使用 15 次决策上限；成功回合提前结束。v1 只记录了 planner Choice 调用墙钟时间和每步总耗时，没有分别记录 Qwen 服务端计时或 Jev 官方 HTTP 计时，不能事后把总耗时改名为模型推理时间。逐步总耗时数组在各 provider 的 `classified.jsonl`，逐回合值在 `results/main15_final/episode_audit.md`。

| 决策模型 | 套件 | 决策模型推理时间（本地服务端计算 / Jev HTTP 往返，每步） | Harness 总耗时（含自动感知与工具执行，每步） |
| --- | --- | ---: | ---: |
| 冻结 2323 | Spatial Swap | 未单独记录 | 10.330 s |
| 冻结 2323 | Object Swap | 未单独记录 | 14.731 s |
| 未训练 Qwen3.5-4B | Spatial Swap | 未单独记录 | 10.443 s |
| 未训练 Qwen3.5-4B | Object Swap | 未单独记录 | 16.046 s |
| 官方 Jev 1.13.0 | Spatial Swap | 未单独记录 | 14.525 s |
| 官方 Jev 1.13.0 | Object Swap | 未单独记录 | 17.990 s |

失败分类如下（`success` 不计入失败类别）：

| 决策模型 | 套件 | 感知 | 候选缺失 | 模型选错 | 技能执行 | 误报完成 | 预算耗尽 | 完整回合 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 冻结 2323 | Spatial Swap | 0 | 0 | 9 | 1 | 0 | 0 | 10 |
| 冻结 2323 | Object Swap | 0 | 0 | 7 | 3 | 0 | 0 | 10 |
| 未训练 Qwen3.5-4B | Spatial Swap | 9 | 0 | 1 | 0 | 0 | 0 | 10 |
| 未训练 Qwen3.5-4B | Object Swap | 0 | 0 | 9 | 1 | 0 | 0 | 10 |
| 官方 Jev 1.13.0 | Spatial Swap | 0 | 0 | 0 | 5 | 0 | 0 | 10 |
| 官方 Jev 1.13.0 | Object Swap | 0 | 0 | 1 | 6 | 0 | 0 | 10 |

没有回合被归为候选缺失、误报完成或预算耗尽；15 次上限仍记录在每回合的 `decisions`/`max_decisions` 字段，模型选错、技能执行和感知类别按 choices、工具回执和视频证据判定。逐回合分类、每一步延迟和 `pi0_pick` 前的分割证据保存在各 provider 目录下的 `classified.jsonl`；跨 provider 的逐回合表由 `results/main15_final/episode_audit.md` 汇总。

`pi0_pick` 前已完成 `segment` 的统计为：2323 **66/66**（Spatial 24/24，Object 42/42），未训练 Qwen3.5-4B **34/34**（Spatial 10/10，Object 24/24），Jev **145/145**（Spatial 67/67，Object 78/78）。因此，主结果中 2323 没有再出现 pilot5 里“未先 segment 就调用 pi0_pick”的 harness 证据。

复核 `choices.jsonl`：2323 选中只读 `segment/back_project` **234 次**，未训练 4B **133 次**，Jev **0 次**。2323 的 **17/20** 个失败回合在 `pi0_pick` 后进入连续 `back_project`；其中 16 个从首次抓取后就纯只读至 15 步上限，另 1 个在五次抓取后进入只读循环。v1 的“模型选错”分类保留；同时明确其候选冗余这一 harness 因素。15 步上限耗尽是这些回合的终止方式，不会覆盖已记录的主要失败类别。

## pilot5 留档，不作主判定

| 决策模型 | Spatial Swap | Object Swap | 备注 |
| --- | ---: | ---: | --- |
| 2323 | 2/10 (20%) | 1/10 (10%) | 17 个失败回合全部用满 5 次决策 |
| 未训练 Qwen3.5-4B | 0/10 | 0/10 | 多数回合在 1 次决策后结束 |
| Jev 1.13.0 | 0/4 | 未运行 | 作业 2393 在第 5 个 Spatial 回合遭 HTTP 422，中断；不得写成 0/10 |

原始文件保留在远端 `results/pilot5/`，本地已复制 `result.json`。该 pilot 的 5 步预算是 harness 设置缺陷，不能用于对外比较或判定训练效果。

## Main15-v2 开发记录

开发 harness 固定为 `f037752003c80bdc818f540f82b6046d8ed304e9`，自动感知开启时不再枚举重复的 `segment/back_project` 候选。v2 **不替换 Main15-v1 的冻结结果或结论**；每套件仍为任务 0–9 × seed 0，15 次决策上限。本节是开发记录，每任务一个 seed，不能解释为完整官方基准。

`2483` 留存的有效 Jev 回合实际为 Spatial 全部 10 局及 Object 任务 0、1 两局。作业 `2531` / `2536` / `2537` 在 node02 单 GPU 补完 Object 任务 2–9，写入独立目录 `results/main15_v2_completion_20260929/`。旧完整回合和被取消时的部分轨迹都保留，没有重跑已有结果。`2530` 在首次回合前的桥接健康检查失败，零模型调用，不计为模型成绩。`2531` 在任务 5 首次决策过程中遭官方 API Cloudflare 520，`2536` 在任务 6 首次决策过程中遭同类 520；两次均未记录完整决策和动作，原目录分别保留在 `infrastructure_failures/job2531_task_5_seed_0/` 和 `job2536_task_6_seed_0/`。恢复作业均跳过已有完整回合。CPU 汇总作业为 `2534`。

| 决策模型 | Spatial Swap | Object Swap | 合计 |
| --- | ---: | ---: | ---: |
| 冻结 2323 | 4/10 | 1/10 | 5/20 |
| 未训练 Qwen3.5-4B | 0/10 | 2/10 | 2/20 |
| 官方 Jev 1.13.0 | 4/10 | 4/10 | 8/20 |

本地 Qwen 的推理时间取服务端 `model_inference_s`，包含请求准备、前向和概率读出；Jev 取 agilex 官方 API 调用的 HTTP 往返及客户端解析时间，不含反向隧道时间，不称纯模型计算。每步可能包含工具、对象、区域等多个 Choice 调用，模型时间为该步各调用之和；harness 总耗时包含自动感知、模型请求和工具执行，不含回合服务启动及末尾视频落盘。下表按全部已记录步骤加权平均，失败步骤也计入。

| 决策模型 | 套件 | 决策模型推理时间（本地服务端计算 / Jev HTTP 往返，每步） | Harness 总耗时（含自动感知与工具执行，每步） | 计时步数 |
| --- | --- | ---: | ---: | ---: |
| 冻结 2323 | Spatial Swap | 0.214 s | 9.358 s | 115 |
| 冻结 2323 | Object Swap | 0.267 s | 12.073 s | 140 |
| 未训练 Qwen3.5-4B | Spatial Swap | 0.235 s | 8.931 s | 68 |
| 未训练 Qwen3.5-4B | Object Swap | 0.278 s | 10.544 s | 34 |
| 官方 Jev 1.13.0 | Spatial Swap | 0.832 s | 9.867 s | 105 |
| 官方 Jev 1.13.0 | Object Swap | 0.826 s | 14.633 s | 107 |

`2531` 初次桥接使用既有配置的 `jev-latest` 请求名；恢复作业 `2536` / `2537` 在启动时显式固定请求名为 `jev-1.13.0`，桥接与 harness 源码保持不变。原有回合及本次补跑的全部已记录 Choice 阶段实际返回版本均为 `jev-1.13.0`；旧回合的请求别名没有另行记录，官方权重 revision 未提供。启动/API 中断的记录单独保留；这些中断没有完整逐步计时，不混入完整回合的步骤均值。

| 决策模型 | 套件 | 感知 | 候选缺失 | 模型选错 | 技能执行 | 误报完成 | 预算耗尽（主要类别） | 达到预算上限（终止症状） |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 冻结 2323 | Spatial Swap | 0 | 0 | 0 | 6 | 0 | 0 | 6 |
| 冻结 2323 | Object Swap | 0 | 0 | 8 | 1 | 0 | 0 | 9 |
| 未训练 Qwen3.5-4B | Spatial Swap | 0 | 0 | 1 | 2 | 7 | 0 | 3 |
| 未训练 Qwen3.5-4B | Object Swap | 0 | 0 | 0 | 0 | 8 | 0 | 0 |
| 官方 Jev 1.13.0 | Spatial Swap | 0 | 0 | 1 | 5 | 0 | 0 | 6 |
| 官方 Jev 1.13.0 | Object Swap | 0 | 0 | 3 | 3 | 0 | 0 | 6 |

主要失败类别继续由原始选择、工具回执和官方成功判据分类；达到 15 次预算上限单列为终止症状，不覆盖主要类别。逐局证据和完整动作序列均保留。

| 决策模型 | 只读 `segment` 选择 | 只读 `back_project` 选择 | 此类模型候选数 |
| --- | ---: | ---: | ---: |
| 冻结 2323 | 0 | 0 | 0 |
| 未训练 Qwen3.5-4B | 0 | 0 | 0 |
| 官方 Jev 1.13.0 | 0 | 0 | 0 |

60/60 完整 v2 回合的只读候选与模型选择均为 0，因此 v1 的 `segment/back_project` 决策死循环已移除。自动感知仍执行这些工具，耗时计入 harness 总耗时；这里的零计数不表示没有感知调用，也不表示重复抓取、技能执行或其它失败已解决。

产物：[`summary.json`](results/main15_v2_audit/summary.json)、[`classified.jsonl`](results/main15_v2_audit/classified.jsonl)、[`逐局表`](results/main15_v2_audit/episode_audit.md)、[`视频索引`](results/main15_v2_audit/video_index.md) / [`CSV`](results/main15_v2_audit/video_index.csv)、[`执行及哈希`](results/main15_v2_audit/execution.json)。视频本体留在 node02，不提交二进制。原始 result/choices 分别留在 `results/main15_v2/` 和补跑目录；汇总不会覆盖冻结 v1。LIBERO 数据生成和训练均未启动。

## 预先固定的训练后判定标准

本节在查看任何 LIBERO 版训练后结果之前提交；后续不得根据评测结果修改阈值、测试集或选择性重跑。

1. 只使用冻结的同一 harness、相同的 Spatial/Object Swap 各 10 个任务 × seed 0 回合，比训练后 2323、训练前 2323 和 Jev。每个失败回合计入分母。
2. “成立”须同时满足：训练后两套件合计成功率 **≥60%（至少 12/20）**；相对同一 harness 下的 Jev **至少高 20 个百分点（至少多 4/20）**，且两个套件的成功数都不低于 Jev。这里的“明显高于”是预先定义的实用差异，不声称 20 回合有统计显著性。
3. 如任一条件不满足，判为“不成立”，把 LIBERO 作为当前方法局限报告，不提交榜单；如满足，才进入 8 套件 × 每套件 100 回合的评测，并先把结果交给用户决定是否提交榜单。
4. 训练只取原版 `libero_spatial/object/goal/10` 和 LIBERO-90，不读任何 PRO swap/task/language/object/env 扰动配置或评测回合。训练 BDDL goal 只在专家与分支标签器内部使用，不进入决策输入。未执行的候选标为 `unknown`。从冻结 2323 全参数初始化，优先使用 LoRA 继续训练；LoRA 不改变基础权重，混入一部分原 MuJoCo 行防止退化，并在原 81000 开发集复测。若改用全参数，学习率固定为当前版本的 0.1 倍，并加入对 2323 的 KL 约束；不得把两种方案的结果混写。本阶段不启动第 3 步，先等待 Codex1 推送并验证 MuJoCo v4 配方表。

### 训练规模与泄漏审计状态

- 本阶段训练尚未启动，已生成训练行 **0**、DAgger 行 **0**、LIBERO 改写行 **0**；因此没有训练 checkpoint、训练曲线或训练前后校准数字可报告。
- 预定最低规模是每个原版训练任务 30 条改写（四个原版套件加 LIBERO-90 若为 130 个任务，则至少 3,900 条改写，最终以不含 PRO 的 manifest 计数为准），另混入一部分原 MuJoCo 行。该数字是计划下限，不是已生成数据量。
- 当前已完成的 PRO 评测请求、轨迹、视频和扰动配置没有被送入训练流水线；训练泄漏审计将在生成 manifest 前逐文件核对并记录为独立证据。训练开始前还必须运行 `verify_serialization_contract.py`，逐字段比对一条评测请求和一条训练行。

### 指令改写与验证合同

- 每个原版训练任务至少生成 30 条改写，覆盖同义词、语序变化、空间关系表达和条件表达。改写只由原版 LIBERO 任务指令和物体/区域类别生成；明确禁止引用任何 LIBERO-PRO swap/task/language/object/env 文本、BDDL 或评测回合。按任务分组去重，原句保留为一条独立样本。
- 训练改写和验证改写使用不同的 LLM、不同的生成提示和不同随机种子。第二个 LLM 生成的验证集只用于挑检查点，不参与梯度、阈值或候选规则调整。训练前后在**同一批固定验证句**上各测一次，并保存原句、改写来源、任务 ID、生成模型和 SHA256。
- 规模按当前 manifest 实际任务数计算；最低规模为 `30 × 原版任务数` 条改写，另加原句和一部分 MuJoCo 行。若四个原版套件加 LIBERO-90 共 130 个任务，最低为 3,900 条改写；最终以不含 PRO 的 manifest 计数为准。
- 标签沿用 acceptable-set 方法：专家和物理分支可以在训练任务内部读取 BDDL goal 判定可接受动作；goal、专家轨迹和未执行候选都不进入模型输入。跑一轮 2323 DAgger 后，只对访问状态重新打标签。
- 置信度校准固定报告两项：验证句的 top-1 成功率；错误选择样本的平均最大候选概率 `mean(max p | wrong)`，并额外保留按套件/任务聚合值。用户已观察到人工 `select_object` 为 4/15、Jev 为 10/15，且错误时 `p≈1.0`；该现象作为训练前基线，不改写为 PRO 结果。

### 训练行与评测请求序列化合同

- `robots/libero/serialization.py` 是唯一序列化器。评测状态文本、候选列表和后续 LIBERO 训练行都由同一 `request_body()` 生成；训练行保留该 canonical request，不允许另写一套字段拼接逻辑。
- 头部固定包含 serializer 版本和坐标约定（world frame、米、`x,y,z`、关系阈值 0.02 m）；字段顺序固定为 `instruction → eef_xyz → gripper_qpos → objects_and_regions → available_observations → visual_locations → measured_relative_relations → inferred_held_object → last_tool_receipt`。候选在 canonical body 中使用稳定的短签名，完整候选仍作为 typed-choice 选项传入；两者都由同一模块生成。`verify_serialization_contract.py` 在训练启动前读取一条评测请求和一条训练行，逐项比较头部、字段顺序和坐标约定；任一不一致直接报错，不能开始训练。首个尝试使用完整候选字典导致 2120/2048 tokens，已改为短签名并保留该失败日志；对象更多时仍出现 2364/2048 tokens，现将测量坐标定点、关系压为短签名并去掉冗余框/分数。
- 训练改写不会改变序列化合同。改写只替换 `instruction` 值，其余字段、候选顺序和坐标表示必须由同一序列化器生成。

## Harness v1 冻结记录

v1 harness 在每个 planner 决策前执行 RPent `segment`，对每个可用框中心执行 `back_project`，并把测量点生成左右、前后、上下和距离关系；动作后重复测量。它不读取 BDDL goal 或仿真物体坐标。文本使用 canonical 序列化器的定点坐标和关系短签名，保证本地 Qwen 的 2048 token 输入合同。smoke `2406`（短候选）曾因对象更多达到 2364 tokens，`2461` Object 和 `2462` Spatial 在最终压缩版本均正常完成 15 步流程；`2461` 的 Object task 0 成功，`2462` 的 Spatial task 0 预算耗尽，二者 `pi0_pick_segmented_before_all=true`。最终冻结运行代码 commit 为 `f8d5fd039540d92694e3709f15c4ed619678b875`；`typed_choice_eval.py` SHA256 为 `f2b5c2178cad8b9f303529c1709563319bd29c6ae91d08d1e494f8cdafa6c0bc`，评测脚本 SHA256 为 `6a206c14e15226a630de40268ffc42147dd00f3547c0a0872d3e230e696f7300`，分类脚本 SHA256 为 `3f5619ffb48d2673d9ea9ff2540abe074b0ff2d70815d1b05031d60d0f4a2e01`。

**公开参照，协议不同，不作同条件对比。** RPent 官网列出 Qwen3.6 27B/no-reasoning：Spatial Swap **78%**、Object Swap **84%**；该数字来自其完整评测配置，不是本轮无 memory、10 回合、typed-choice 的结果。来源：[RPent LIBERO-PRO leaderboard](https://rpent.readthedocs.io/en/latest/rst_source/leaderboard/performance.html)。

## 公平性声明

- 允许观测：任务自然语言；RPent `view_env_state` 的末端位姿、夹爪状态和物体/区域名称；相机 RGB、深度和相机标定产生的视觉产物；`segment`/SAM3 与 `back_project` 的测量结果；工具回执。文本决策模型看序列化的测量坐标、相对关系和回执，不直接看像素；Pi0.5 技能和 SAM3 工具处理图像。物体名称来自 RPent 环境观测键，相当于给定类别表，不代表逐帧视觉识别。
- 人工设计：通用工具接口、参数类型、可行性约束，从当前名称枚举 `segment/back_project/pi0_pick` 及持有物体后的 `move_to` 目标、释放动作；`move_to` 的高度偏移及分段行程。Main15-v1 中只读工具与自动感知重复，构成已知 harness 因素。候选不按任务正确答案过滤。
- 未使用：BDDL `goal`、仿真物体真实坐标、RPent memory、已评测回合给决策打标签、PRO 扰动配置上的训练。BDDL 目标只由官方环境内部用于判分。没有使用真值脚本专家。
- 本系统复用了已训练 Pi0.5 技能与 SAM3，且使用深度；因此既不是纯 4B 控制策略，也不能直接与仅 RGB 的端到端 VLA 视为同条件。三组决策模型共享完全相同的候选生成器和技能执行器。

## 开发记录与待判失败

- node02 无外网使 Pi0.5 tokenizer 下载失败；从已有缓存复制同一 tokenizer 后，官方 toolkit 正常启动。
- 主评测 job `2408` 在 2323 Spatial 10/10 完成后，于 Object task 0 因状态文本 2364 tokens 超过 Qwen 2048 合同而中止；Spatial 产物保留为开发记录，不进入冻结主表。已在同一序列化器内压缩测量字段，Object smoke 通过后从最终版本重跑两套件。
- 开发期 task 1 显示已抓取后仍持续重复 `pi0_pick`：候选状态机在抓取后清空了视觉定位，并允许再次抓取。已改为持有期间不枚举二次抓取，保留静态目标定位；从 `results/v2/` 重新判分。
- 初次并行提交 `2364`/`2365`/`2366` 会同时占多张 GPU，已取消后两组，保留原始轨迹；`2370`→`2371`→`2372` 使用 Slurm 依赖串行，每次只占 node02 一张 GPU。
- 主结果失败分类已完成并冻结；逐回合证据见 `results/main15_final/episode_audit.md`，每步延迟和原始选择见各 provider 的 `classified.jsonl`/`choices.jsonl`。

## 视频

开发期 task 0 的视频保存在 `results/initial_task0/{dagger2323,qwen4b,jev}/episode.mp4`。Main15 冻结运行的 60 个完整 episode 视频与 SHA256 索引见 [`results/main15_final/video_index.md`](results/main15_final/video_index.md) 和 [`results/main15_final/video_index.csv`](results/main15_final/video_index.csv)。视频本体保存在现有本地与 node02 存储，不纳入 Git 归档。

## 2026-09-30 官方 HF 资产修复注记

已按 RPent 指南2.3–2.4同步 `zhouxueyang/LIBERO-Pro` 固定 revision
`c86fc3b8293185a6f373677018ff3e37f8391602`。完整备份、逐文件差异及160任务
校验见 [资产修复记录](results/asset_repair_20260930/REPORT.md)。80个最终任务均有50个
初始状态；D2仍为原40局，不替换任务。

Main15使用的Spatial Swap/Object Swap各10任务，共40个BDDL/init文件，在覆盖前
安装与HF之间全部一致，没有落入此次40个不同文件的清单。旧Main15缺少运行时逐文件
资产哈希，当前比对不能追溯证明各次历史运行的字节身份。Main15-v1/v2原结果、失败和
延迟均保留，不并入v5。Spatial Task的task3/task7重复语言在权威HF中仍存在，分别与
各自BDDL一致，未擅自改写。


## 10/01 D2 stock-vLLM 开发复现

本节为开发记录，不替换冻结的Main15-v1/v2结果或表A最终评测。A1-M完整40局为28局物理完成且显式finish；12局终止类别为planner_wall_budget_inferred，全部保留。D2固定8套件×task0–4×init40，每套件5局，只与公开大样本数字作粗核对。

| 套件 | A1-N 正确finish | A1-M 正确finish | 官网Qwen27B参考（有memory） |
| --- | ---: | ---: | ---: |
| Spatial Task | 3/5 | 4/5 | 82% |
| Spatial Swap | 2/5 | 4/5 | 78% |
| Object Task | 4/5 | 3/5 | 83% |
| Object Swap | 2/5 | 4/5 | 84% |
| Goal Task | 2/5 | 4/5 | 68% |
| Goal Swap | 2/5 | 3/5 | 68% |
| Long Task | 2/5 | 3/5 | 61% |
| Long Swap | 0/5 | 3/5 | 41% |
| 合计 | 17/40 | 28/40 | 70.63% |

A1-M使用未修改vLLM0.19、Qwen3.6-27B-FP8 revision e89b16ebf1988b3d6befa7de50abc2d76f26eb09；TP2/context262144，temperature0.7/top_p0.8/top_k20/min_p0/presence_penalty1.5/max_tokens8192、no reasoning。memory-version auto按上游select_version对Qwen的回退使用GPT_5.5_xhigh。全部1083次上游响应HTTP200、返回模型Qwen3.6-27B-FP8；无“继续”注入。旧SGLang2780记录保留为运行时不对齐的开发诊断，不作基线。

A1-N2825/2826及汇总2829已完成，40局物理完成且正确finish17局；17局显式失败结束、1局误报finish、5局planner墙钟预算推断，全部保留。1313次响应均HTTP200、解析名称不匹配0，无续写注入。2825在原EVALUATION_DONE后正常退出，与worker一起释放3张GPU。两组使用同软件、权重与参数；服务进程已重启，不能称同一物理服务进程或单变量因果复现。同一40局中两组都成功14局、仅M成功14局、仅N成功3局。

逐局端到端墙钟：N平均661.15秒、中位590.92秒、P95=1213.92秒；M平均743.67秒、中位593.18秒、P95=1225.38秒。按各组实测40局线性估算80局worker为14.69/16.53 GPU小时，均未包含两卡vLLM启动和常驻时间，不能当作完整算力费用。原始transcript和完整核对留在远端a1n_vllm_development40_20261001/summary_N40及a1m_vllm_development40_20261001/summary_M40；本地[配对和计时](results/harness_v5/a1n_stock_complete40_20261001/paired_timing.json)保留源SHA。70%只对应D2开发40局，不能称复现官方800局成绩。

用户10/01 11:15已授权A4先跑开发诊断，原2890已提交运行，非冻结、非止损终判；完整200局专家至少160正确finish的冻结条件保持。新数据按修复后的2873源码采集，已交prefix8统计版（946动作+11479辅助、另101验证）及新源码单独包（30动作+525辅助），待独立来源核对；两个包重叠，不相加。

原版训练已开始独立采集并交付首批，不改变历史Main15“训练未启动”记录：exact manifest6718ece82f7e93b427a5f85d3ca2334605a1bbdddbade64425fa86faac895aae包含744next_skill+3623辅助及独立101题验证。Codex1独立审计为PASS_PARTIAL，完整mix/SFT尚未准入。旧专家2836完整111/200未达160；修复后2852另行运行，未提前放行A4或整体冻结。
