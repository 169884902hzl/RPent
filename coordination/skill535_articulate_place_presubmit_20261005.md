# 技能层确认批提交前回执（2026-10-05）

已读取并接受本轮技能层统一冻结要求及已有 3670/3684/3685 运行登记。保留旧作业、旧失败和探索结果；不修改或重跑 3670、3684、3685，不读取 PRO、人工 102 条指令或 sealed_test_v4。

本次运行时合同已固定到源码提交 `7293f9706efb87eb685c5003442eee8e4684467a`：默认 dual_view_fusion_v1、测量回执、候选失败计数；无测量的开合/放置回执为 `unmeasured`；execution_error 后无效果动作进入三步冷却和两次无效果阻断。该回执/恢复语义变化必须交 Codex1/Codex2 后重渲染训练行，确认批不入训。

## 新确认批

- 开合：`fixtures.json`，1200 条，6 类（drawer open/close、microwave open/close、stove on/off）× 两种运行条件，每类/条件 100 次首次尝试。
- 放置：`place.json`，400 条，`place_on`/`place_in` × 两种运行条件，每类/条件 100 次首次尝试；放置 setup 的抓取只作诊断，不改变首次放置分母。
- 仅使用显式 LIBERO-90 原版状态；每条包含 state SHA、原版语言词汇来源和私有诊断绑定，公共状态不含 BDDL 目标或仿真真值坐标；`qualification_authorized=false`、`new_training_rows=0`。
- 清单 preparation 已核验：fixtures SHA `ffb890d894609f3046e88832a33189053a50bb66c6ca333aca6c4c6d98585645`，place SHA `d9c39247883a38e8587364e0bd9c9d73a87f720f866bea7e70c767077c53dc35`。生成器 `1666548a9437b7a5b145bcc658c2c7be92306d9c39b4ee361ba162422d9b8973`；probe `15778e26c767bba2c70fd7cf766caef42410061e79b87211a6de5478c45186b6`；launcher 分别 `6c4c7a57dc445a7b8c63432182af5b8a99cdecc98cf6c69620e48b7359e3437c`、`95faa7118ce240dd1d4d4a84805b14cefebba027f29a9d53612e5037996b0409`。
- 源码快照：`/public/home/sunyihan/rpent_libero_eval/source_v5_skill535_articulate_place_20261005`；关键文件 SHA 在提交后随实际命令回执记录。

## 计划提交

Slurm 将在提交时分配两个新数组号（提交前无法预知，立即回填实际号码）：

- articulate：`array=0-7%8`、1 GPU/片、无依赖、无节点绑定；输出 `results/harness_v5/skill535_articulate_confirmation_20261005/job<JOB>/part<0-7>`。
- place：`array=0-7%8`、1 GPU/片、无依赖、无节点绑定；输出 `results/harness_v5/skill535_place_confirmation_20261005/job<JOB>/part<0-7>`。

当前无异议；确认批完成后按 type/condition 汇报物理成功、Wilson 95% CI、运行时验证器 precision/recall、FP/FN/unmeasured、执行错误与首次成功率。抓取、开合、放置三项全部达标前不宣布冻结、不提交训练。
