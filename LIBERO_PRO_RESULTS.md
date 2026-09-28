# LIBERO-PRO × RPent typed-choice 零样本评测

状态：2026-09-28。`pilot5` 原始结果留档；每回合 5 次决策不足以代表完整抓放。下一批主结果只计入冻结 harness、15 次决策上限下的 `spatial_swap` 和 `object_swap` 各 10 个完整回合。开发目录和中止回合不混入主表。

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

## 第一批成绩

冻结 harness 后运行。所有完整回合保留失败；中断回合单列，不伪装成完整回合。主 job `2465` 仍在 node02 运行未训练 Qwen4B；Jev job `2466` 依赖主 job，尚未启动。下表只填写已经完整结束的 2323 组，不把未完成组写成 0。

| 决策模型 | Spatial Swap | Object Swap |
| --- | ---: | ---: |
| 冻结 2323 | 0/10 (0%) | 0/10 (0%) |
| 未训练 Qwen3.5-4B | 0/10 (0%) | 运行中（Object 尚未完成） |
| 官方 Jev 1.13.0 | 未运行 | 未运行 |

2323 的 20 个回合全部使用 15 次决策上限。平均单步决策延迟为 Spatial **10.330 s**、Object **14.731 s**（合并 **12.531 s**）。失败分类如下：

| 决策模型 | 套件 | 感知 | 候选缺失 | 模型选错 | 技能执行 | 误报完成 | 预算耗尽 | 完整回合 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 冻结 2323 | Spatial Swap | 0 | 0 | 9 | 1 | 0 | 0 | 10 |
| 冻结 2323 | Object Swap | 0 | 0 | 7 | 3 | 0 | 0 | 10 |
| 未训练 Qwen3.5-4B | Spatial Swap | 9 | 0 | 1 | 0 | 0 | 0 | 10 |

逐回合分类、每一步延迟和 `pi0_pick` 前的分割证据保存在各 provider 目录下的 `classified.jsonl`。冻结 2323 共调用 `pi0_pick` 66 次，66/66 次均有此前的 `segment` 记录（Spatial 24/24，Object 42/42）。完整视频索引见 `results/main15_final/video_index.csv` 和可点击的 `results/main15_final/video_index.md`；目前已回收 2323 的 20 个视频和 Qwen4B Spatial 的 10 个视频，Qwen4B Object/Jev 会在各自回合完成后追加。

Qwen4B Spatial 的逐回合结果、延迟和分割字段在 `results/main15_final/qwen4b/classified.jsonl`；该组 10 次 `pi0_pick` 均在此前完成 segment，平均单步决策延迟为 **10.443 s**。Object Swap 仍在运行，未计入上表的完整回合统计。

### pilot5 留档，不作主判定

| 决策模型 | Spatial Swap | Object Swap | 备注 |
| --- | ---: | ---: | --- |
| 2323 | 2/10 (20%) | 1/10 (10%) | 17 个失败回合全部用满 5 次决策 |
| 未训练 Qwen3.5-4B | 0/10 | 0/10 | 多数回合在 1 次决策后结束 |
| Jev 1.13.0 | 0/4 | 未运行 | 作业 2393 在第 5 个 Spatial 回合遭 HTTP 422，中断；不得写成 0/10 |

原始文件保留在远端 `results/pilot5/`，本地已复制 `result.json`。该 pilot 的 5 步预算是 harness 设置缺陷，不能用于对外比较或判定训练效果。

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

## Harness 冻结候选

当前候选在每个 planner 决策前执行 RPent `segment`，对每个可用框中心执行 `back_project`，并把测量点生成左右、前后、上下和距离关系；动作后重复测量。它不读取 BDDL goal 或仿真物体坐标。文本使用 canonical 序列化器的定点坐标和关系短签名，保证本地 Qwen 的 2048 token 输入合同。smoke `2406`（短候选）曾因对象更多达到 2364 tokens，`2461` Object 和 `2462` Spatial 在最终压缩版本均正常完成 15 步流程；`2461` 的 Object task 0 成功，`2462` 的 Spatial task 0 预算耗尽，二者 `pi0_pick_segmented_before_all=true`。最终冻结运行代码 commit 为 `f8d5fd039540d92694e3709f15c4ed619678b875`；`typed_choice_eval.py` SHA256 为 `f2b5c2178cad8b9f303529c1709563319bd29c6ae91d08d1e494f8cdafa6c0bc`，评测脚本 SHA256 为 `6a206c14e15226a630de40268ffc42147dd00f3547c0a0872d3e230e696f7300`，分类脚本 SHA256 为 `3f5619ffb48d2673d9ea9ff2540abe074b0ff2d70815d1b05031d60d0f4a2e01`。

**公开参照，协议不同，不作同条件对比。** RPent 官网列出 Qwen3.6 27B/no-reasoning：Spatial Swap **78%**、Object Swap **84%**；该数字来自其完整评测配置，不是本轮无 memory、10 回合、typed-choice 的结果。来源：[RPent LIBERO-PRO leaderboard](https://rpent.readthedocs.io/en/latest/rst_source/leaderboard/performance.html)。

## 公平性声明

- 允许观测：任务自然语言；RPent `view_env_state` 的末端位姿、夹爪状态和物体/区域名称；相机 RGB、深度和相机标定产生的视觉产物；`segment`/SAM3 与 `back_project` 的测量结果；工具回执。文本决策模型看序列化的测量坐标、相对关系和回执，不直接看像素；Pi0.5 技能和 SAM3 工具处理图像。物体名称来自 RPent 环境观测键，相当于给定类别表，不代表逐帧视觉识别。
- 人工设计：通用工具接口、参数类型、可行性约束、从当前名称枚举 `segment`/`pi0_pick`，以及持有物体后从已定位的其他名称枚举 `move_to` 目标与释放动作；`move_to` 的高度偏移及分段行程。候选不按任务正确答案过滤。
- 未使用：BDDL `goal`、仿真物体真实坐标、RPent memory、已评测回合给决策打标签、PRO 扰动配置上的训练。BDDL 目标只由官方环境内部用于判分。没有使用真值脚本专家。
- 本系统复用了已训练 Pi0.5 技能与 SAM3，且使用深度；因此既不是纯 4B 控制策略，也不能直接与仅 RGB 的端到端 VLA 视为同条件。三组决策模型共享完全相同的候选生成器和技能执行器。

## 开发记录与待判失败

- node02 无外网使 Pi0.5 tokenizer 下载失败；从已有缓存复制同一 tokenizer 后，官方 toolkit 正常启动。
- 主评测 job `2408` 在 2323 Spatial 10/10 完成后，于 Object task 0 因状态文本 2364 tokens 超过 Qwen 2048 合同而中止；Spatial 产物保留为开发记录，不进入冻结主表。已在同一序列化器内压缩测量字段，Object smoke 通过后从最终版本重跑两套件。
- 开发期 task 1 显示已抓取后仍持续重复 `pi0_pick`：候选状态机在抓取后清空了视觉定位，并允许再次抓取。已改为持有期间不枚举二次抓取，保留静态目标定位；从 `results/v2/` 重新判分。
- 初次并行提交 `2364`/`2365`/`2366` 会同时占多张 GPU，已取消后两组，保留原始轨迹；`2370`→`2371`→`2372` 使用 Slurm 依赖串行，每次只占 node02 一张 GPU。
- 失败分类将在每回合审阅后填入：感知/定位、候选缺失、模型选错、技能执行、误报完成、环境中断；以视频和工具回执为证据。

## 视频

开发期 task 0 的三组完整视频已保存在 `results/initial_task0/{dagger2323,qwen4b,jev}/episode.mp4`；正式第一批将在 `results/v2/` 完成后生成逐回合本地视频索引。
