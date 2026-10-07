# 4355 / 4369 / 4378 原始启动错误核对

只读核对 `sacct` 与显式日志、episode ledger；原始失败不覆盖。日志逐行原文和 SHA-256 在 `report.json`。未扫描产物目录，未打开 PRO 任务正文。

| 作业 | 实时历史状态 | 原始 ledger | 物理执行证据 |
| --- | --- | --- | --- |
| 4355 | 0–7 全 `COMPLETED 0:0` | 80/80 `startup_error` | 0 controls；8 片各 10 条导入错误 |
| 4369 | 0–3 `FAILED 1:0`；5–7 未启动取消；4 无 sacct/日志 | 4 条 `startup_error` | 0 controls；不能称 8 片都运行失败 |
| 4378 | 0–7 全 `FAILED 1:0` | 8 条被结束记账覆盖为 `startup_error` | part3 执行 320 块 / 1600 controls；其它 7 片 0 |

4355 的错误没有打印到 Slurm stdout，原文在 `A3-N/job4355/part0/probe/episodes.jsonl` 的 result：

```json
{"status": "startup_error", "error": "ModuleNotFoundError: No module named 'typed_choice_eval'"}
```

4369_0 的 `slurm-4369_0.log` 第 51 行原文：

```text
{"case": "moka_transfer_visited_libero_90_t19_s0", "startup_or_execution_error": "ModuleNotFoundError(\"No module named 'typed_choice_eval'\")"}
```

4378_3 的 `slurm-4378_3.log` 第 51–52 行原文：

```text
{"case": "moka_transfer_visited_libero_90_t19_s3", "startup_or_execution_error": "FileNotFoundError(2, 'No such file or directory')"}
{"case": "moka_transfer_visited_libero_90_t19_s3", "grasp_attempted": false, "visual_verified": false, "private_contact": false, "chunks": 320, "error": "FileNotFoundError(2, 'No such file or directory')"}
```

4369 和 4378 的末条异常原文都是：

```text
RuntimeError: preserved instrument/execution failure; stop before further trials
```

4355 / 4369 根因是延迟导入时找不到 `typed_choice_eval`。4378 的导入已有 supplement，结束代码却仍从 SOURCE571 根目录读取这个文件来计算源码 hash；根目录文件不存在。SOURCE571 `harness_v5_eval.py` 第 939 行的 `(Path(__file__).resolve().parent / name).read_bytes()` 与第 969 行的 `typed_choice_eval.py` 构成这个路径错误。该结束异常覆盖了已发生的物理执行。

修复与真实执行的对应：

- `d0ed260` 将 decision scorer 纳入专家/A3 显式依赖并校验真实导入位置；`53f4da9` 修摩卡依赖 bootstrap、记录实际导入路径/SHA 与完整 traceback，结束 hash 使用实际 module 路径。
- `82c7ab5` 让 batch 任意一条 `startup_error` 最终退出非零；`e87abbc` 让 interim 数组以同快照、同 launcher 的真实物理启动合同放行。`793a5c6` 对摩卡正式数组绑定同源启动合同，并排除已完成启动局。
- 专家 4412：11 VLA 块 + 115 放置运动步；A3 4413：11 VLA 块 + 125 放置运动步；均实际 `COMPLETED 0:0`。不是 mock import 检查。
- 摩卡 4425：r5 同 launcher，320 块 / 1600 controls；4440：r6 同 launcher，320 块 / 1600 controls，合同 PASS。`7aa7a08` 修日志中的 NumPy JSON 值；`a1b99dc` 修公开重复 bbox 绑定与 launcher 错误提示。
- 合并首次物理十局的正式开发包是 `moka_visited10_complete_20261007` / commit `1da95b8`。十局共 16000 controls，曾原生成功 9/10、私有末态成功 3/10、成功后退回 6/10；公开验证 2 true / 3 false / 5 null。此包混合访问过的选择状态与不同启动修复版本，不用于独立确认门槛。

非零退出覆盖与剩余项：

| 范围 | 当前实现 / 实际证据 | 仍需说明 |
| --- | --- | --- |
| batch 的 `startup_error` | `82c7ab5` 保留 ledger 后退出 1 | 4355 历史 exit0 不修改；旧 SOURCE571 不可复用作新启动 |
| interim 启动 / 基础设施错误 | launcher 检查 status、termination_category、infrastructure_failure 并退出非零；4418_3 以 bool_ 基础设施标记实际退出 2 | 普通已执行的 `no_legal_candidate` 按程序终止保留，不能伪装成启动错误；启动合同准入与技能成绩分开 |
| 摩卡启动 / 基础设施 / 零物理 | 同源合同、依赖 SHA、正式数组逐局退出检查；4430_1 实际非零、4440 实际 PASS | r6 不解决技能终点未停和公开两帧缺测；确认批仍不可开分 |
| 微波炉 4463 | 80 controls 已实际执行；原 launcher 误从 first_attempt 层读计数而退出 1 | 当前工作树已改为顶层 controls + first_attempt.physically_executed；新快照同 launcher 的真实复验还待完成，不能称该 launcher 已物理复验通过 |

本文件仅核对这三组失败和已知关联启动路径，没有声称全部历史 launcher 都已完成真实启动验证。当前工作树代码的准确 SHA 随 `report.json` 保存；运行产物的源码身份由各自 manifest / startup contract 记录。
