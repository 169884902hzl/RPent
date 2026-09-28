# LIBERO-PRO × RPent typed-choice 零样本评测

状态：2026-09-28。`pilot5` 原始结果留档；每回合 5 次决策不足以代表完整抓放。下一批主结果只计入冻结 harness、15 次决策上限下的 `spatial_swap` 和 `object_swap` 各 10 个完整回合。开发目录和中止回合不混入主表。

## 已跑通

- 独立仓库：`/home/agilex/cobot_magic/rpent_libero_eval`，分支 `spike/typed-choice-no-memory`；RPent 基线 commit `71f5775d7cef0a3d38ca642f90512cc4f0dc6e74`。未修改或推送 `robot_decider_instruction`。
- `.[libero-pro]` 已安装到独立 Python 3.10 环境；`LIBERO_TYPE=pro` 加载 `liberopro`。Pi0.5、SAM3 和 LIBERO-PRO 资产在 node02 本地；Slurm 固定 `node02`，每个作业申请 `gpu:1`，三个决策组用依赖串行排队。
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
| 运行 | node02 `--gres=gpu:1`；Pi0.5、SAM3、Qwen 占该卡，MuJoCo 环境步进在 CPU，EGL 渲染使用同卡；主结果每回合最多 15 次 planner 决策 |

## 第一批成绩

冻结 harness 后运行并填写。所有完整回合保留失败；中断回合单列，不伪装成完整回合。

| 决策模型 | Spatial Swap | Object Swap |
| --- | ---: | ---: |
| 2323 | 未运行 | 未运行 |
| 未训练 Qwen3.5-4B | 未运行 | 未运行 |
| 官方 Jev 1.13.0 | 未运行 | 未运行 |

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
4. 训练只取原版 `libero_spatial/object/goal/10` 和 LIBERO-90，不读任何 PRO swap/task/language/object/env 扰动配置或评测回合。训练 BDDL goal 只在专家与分支标签器内部使用，不进入决策输入。未执行的候选标为 `unknown`。从冻结 2323 全参数初始化，优先使用 LoRA 继续训练；LoRA 不改变基础权重，混入一部分原 MuJoCo 行防止退化，并在原 81000 开发集复测。若改用全参数，学习率固定为当前版本的 0.1 倍，并加入对 2323 的 KL 约束；不得把两种方案的结果混写。

### 指令改写与验证合同

- 每个原版训练任务至少生成 30 条改写，覆盖同义词、语序变化、空间关系表达和条件表达。改写只由原版 LIBERO 任务指令和物体/区域类别生成；明确禁止引用任何 LIBERO-PRO swap/task/language/object/env 文本、BDDL 或评测回合。按任务分组去重，原句保留为一条独立样本。
- 训练改写和验证改写使用不同的 LLM、不同的生成提示和不同随机种子。第二个 LLM 生成的验证集只用于挑检查点，不参与梯度、阈值或候选规则调整。训练前后在**同一批固定验证句**上各测一次，并保存原句、改写来源、任务 ID、生成模型和 SHA256。
- 规模按当前 manifest 实际任务数计算；最低规模为 `30 × 原版任务数` 条改写，另加原句和一部分 MuJoCo 行。若四个原版套件加 LIBERO-90 共 130 个任务，最低为 3,900 条改写；最终以不含 PRO 的 manifest 计数为准。
- 标签沿用 acceptable-set 方法：专家和物理分支可以在训练任务内部读取 BDDL goal 判定可接受动作；goal、专家轨迹和未执行候选都不进入模型输入。跑一轮 2323 DAgger 后，只对访问状态重新打标签。
- 置信度校准固定报告两项：验证句的 top-1 成功率；错误选择样本的平均最大候选概率 `mean(max p | wrong)`，并额外保留按套件/任务聚合值。用户已观察到人工 `select_object` 为 4/15、Jev 为 10/15，且错误时 `p≈1.0`；该现象作为训练前基线，不改写为 PRO 结果。

## Harness 冻结候选

当前候选在每个 planner 决策前执行 RPent `segment`，对每个可用框中心执行 `back_project`，并把测量点生成左右、前后、上下和距离关系；动作后重复测量。它不读取 BDDL goal 或仿真物体坐标。文本只保留紧凑测量结果，避免超过本地 Qwen 的 2048 token 输入合同。单回合 smoke `2403` 已跑通 15 次决策上限、逐步感知和视频记录。冻结 harness commit 为 `5d8f0d28bdf4ab3d87f26e89fe37a0e2ec73a9d6`；`typed_choice_eval.py` SHA256 为 `36172e3d2855f55b39e3ea3c1ec829065c8e0d1f0816618b5f924fd81950165c`，评测脚本 SHA256 为 `6a206c14e15226a630de40268ffc42147dd00f3547c0a0872d3e230e696f7300`。

**公开参照，协议不同，不作同条件对比。** RPent 官网列出 Qwen3.6 27B/no-reasoning：Spatial Swap **78%**、Object Swap **84%**；该数字来自其完整评测配置，不是本轮无 memory、10 回合、typed-choice 的结果。来源：[RPent LIBERO-PRO leaderboard](https://rpent.readthedocs.io/en/latest/rst_source/leaderboard/performance.html)。

## 公平性声明

- 允许观测：任务自然语言；RPent `view_env_state` 的末端位姿、夹爪状态和物体/区域名称；相机 RGB、深度和相机标定产生的视觉产物；`segment`/SAM3 与 `back_project` 的测量结果；工具回执。文本决策模型看序列化的测量坐标、相对关系和回执，不直接看像素；Pi0.5 技能和 SAM3 工具处理图像。物体名称来自 RPent 环境观测键，相当于给定类别表，不代表逐帧视觉识别。
- 人工设计：通用工具接口、参数类型、可行性约束、从当前名称枚举 `segment`/`pi0_pick`，以及持有物体后从已定位的其他名称枚举 `move_to` 目标与释放动作；`move_to` 的高度偏移及分段行程。候选不按任务正确答案过滤。
- 未使用：BDDL `goal`、仿真物体真实坐标、RPent memory、已评测回合给决策打标签、PRO 扰动配置上的训练。BDDL 目标只由官方环境内部用于判分。没有使用真值脚本专家。
- 本系统复用了已训练 Pi0.5 技能与 SAM3，且使用深度；因此既不是纯 4B 控制策略，也不能直接与仅 RGB 的端到端 VLA 视为同条件。三组决策模型共享完全相同的候选生成器和技能执行器。

## 开发记录与待判失败

- node02 无外网使 Pi0.5 tokenizer 下载失败；从已有缓存复制同一 tokenizer 后，官方 toolkit 正常启动。
- 开发期 task 1 显示已抓取后仍持续重复 `pi0_pick`：候选状态机在抓取后清空了视觉定位，并允许再次抓取。已改为持有期间不枚举二次抓取，保留静态目标定位；从 `results/v2/` 重新判分。
- 初次并行提交 `2364`/`2365`/`2366` 会同时占多张 GPU，已取消后两组，保留原始轨迹；`2370`→`2371`→`2372` 使用 Slurm 依赖串行，每次只占 node02 一张 GPU。
- 失败分类将在每回合审阅后填入：感知/定位、候选缺失、模型选错、技能执行、误报完成、环境中断；以视频和工具回执为证据。

## 视频

开发期 task 0 的三组完整视频已保存在 `results/initial_task0/{dagger2323,qwen4b,jev}/episode.mp4`；正式第一批将在 `results/v2/` 完成后生成逐回合本地视频索引。
