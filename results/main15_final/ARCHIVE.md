# Main15 冻结结果归档

冻结结果：2323 **0/20**、未训练 Qwen3.5-4B **0/20**、官方 Jev 1.13.0 **8/20**。每组包含 Spatial Swap 与 Object Swap 各 10 个任务，每任务仅 seed 0 一回合，每回合最多 15 次决策；这不是官方完整评测。正式 Slurm 作业为 `2465`、`2466`。pilot5 和后续开发轨迹不计入分母。

本目录归档 60 份 `result.json`、60 份 `choices.jsonl`、三个 provider 的 `classified.jsonl`、`summary.txt`、`episode_audit.md` 及视频索引。逐回合失败分类以决策错误为主，但候选中的重复只读工具是已知 harness 因素；`segment` 曾调用不证明感知或技能正确。不能据此推断 SFT 导致退化。见仓库根目录 `LIBERO_PRO_RESULTS.md`。

## 运行源码

RPent 上游基线：`71f5775d7cef0a3d38ca642f90512cc4f0dc6e74`。Main15 冻结运行 commit：`f8d5fd039540d92694e3709f15c4ed619678b875`。以下 SHA256 均取该 commit 的文件内容：

| 文件 | SHA256 |
| --- | --- |
| `typed_choice_eval.py` | `f2b5c2178cad8b9f303529c1709563319bd29c6ae91d08d1e494f8cdafa6c0bc` |
| `qwen_choice_service.py` | `7d9348e89a61ca41e765aac9bf894ae106b02ecdf0280ea85ece42b434647e30` |
| `jev_choice_service.py` | `9c7ed3834e808ede7827f9872a879406ead7a5cd55797d753a5770cc41be454a` |
| `robots/libero/serialization.py` | `290abc445c607fa9e2599df889bd3e586c3d04b4ad90ac401373916d6b303f76` |
| `run_typed_choice_node02.sbatch` | `6a206c14e15226a630de40268ffc42147dd00f3547c0a0872d3e230e696f7300` |
| `classify_results.py` | `3f5619ffb48d2673d9ea9ff2540abe074b0ff2d70815d1b05031d60d0f4a2e01` |

## 决策模型

| 模型文件 | 字节 | SHA256 |
| --- | ---: | --- |
| 2323 `checkpoint_dagger_counterfactual/pytorch_model.bin` | 20,700,197,179 | `2acb4622e1b564d0dc23038b82bde5c50f4c140432beee7583bd1e82157d52f9` |
| 未训练 4B `model.safetensors-00001-of-00002.safetensors` | 5,329,398,688 | `26a93f066e1916adb13453dae5a0c707c0fbc71299ed98779571a907b8e74c61` |
| 未训练 4B `model.safetensors-00002-of-00002.safetensors` | 3,990,429,408 | `cb544bd9bfae93dc59b0f22b292f5933573854a7f9b97835c67060d7d910e188` |

权重位于 node02 的 `/public/home/sunyihan/rd_instruction_20260923/`；哈希由存储中的实际文件计算。Jev 为官方托管模型，使用 1.13.0 客户端，没有可公开核验的本地权重文件；其响应只用于评测，不作训练标签。

## 视频与完整性

60 个完整 MP4 不纳入 Git，保留在本机 `/home/agilex/cobot_magic/rpent_libero_eval/results/main15_final/` 与 node02 `/public/home/sunyihan/rpent_libero_eval/results/main15_final/`。`video_index.csv` 为每个视频记录 provider、套件、任务、seed、相对路径、字节数与 SHA256；`video_index.md` 的链接在视频仍位于相对位置时可直接打开。`SHA256SUMS.txt` 核对本归档的文本与 JSON 产物，不包含视频本体。

`runtime_config/`、凭据、模型权重和开发期结果均不纳入本次 Git 归档。
