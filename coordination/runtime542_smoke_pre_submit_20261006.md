# Codex3 runtime542 冒烟提交前回执

接受用户10/06 00:52队列：开发故障修复后继续；先20局运行时质量检查，再技能选择/独立确认、集成和冻结。确认/最终评测原失败保留，不重跑改善分数。已核对3686/3687启动路径问题、3619诊断meta问题、3722/3734/3780/3868开发记录；不重提旧链。

源码commit ac3fe58；快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_runtime542_20261006`。sources-only archive SHA256 `c44e2cee127c56a541ef367078e557a84cf9d5a2f42dfbaf27929ace037041bf`；v5_state.py SHA256 `38867767ce13b19b22cb6b05c349e5492af72ead926ee8ce843fc993879c2fe8`。8片CPU预检均通过，计划和base_config已绝对化并逐文件核验。

通知Codex1/Codex2：receipt紧凑编码版本4，把最近2–3条完全相同的15项metadata放入第一条receipt的defaults字典。独立measurement/tool、冲突证据逐条保留；receipt行数、候选顺序、原始full receipts及执行/恢复逻辑不变。入口 `robots.libero.v5_state.receipt_lines`，恢复单条metadata用 `expand_receipt_metadata`；解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。这是状态表示变化，尚未冻结，后续训练重渲染必须使用登记版本。102定向测试通过；64个真实已保存prefix无截断复算最大2967 tokens，3072硬上限不变。旧3780/3868记录不改。

20局原版10+开发10；只开发冒烟。manifest `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime542_smoke20_20261006/preparation/manifest.json`，SHA256 `33a7da849420d66203c79fca505baed18cb1c5ebc125a36af7a332185bfbecfd`。两个旧缺陷回合优先，原预算100 decisions / 80 chunks / 10000 steps / 3072 tokens不变。fusion、测量回执、防循环、vla_subtask及只记录的执行前成功率诊断开启。v5@750权重SHA256 `b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb`。

GPU预约：每片1GPU，无节点绑定、无依赖；实时6卡空闲时用array0–7%6，释放后按空卡更新。实际作业号由sbatch返回后立即回填，不能预知编号。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job<JOB>/part0..7/{original,development}`（launcher固定runtime536输出根）。

实际计划命令：

```bash
SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime542_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime542_smoke20_20261006/preparation sbatch --array=0-7%6 --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_runtime542_20261006/scripts/run_v5_runtime536_smoke20.sbatch
```

本回执推送并追加远端COORDINATION后才提交。3868继续原生结束，不取消、不修改。技能批必须等待新20局质量检查，不只看Slurm退出码；总同动作次数另列，不以连续次数冒称所有循环消失。

缺口：摩卡壶旧五种实质不同方法均低于90%，不降门槛；继续用户指定腕部精修/融合把手yaw/完整子任务三法选择。macro同名物体的关系限定缺失保留根因台账，不将单动作verified当任务完成。公开密封排除metadata仍待Codex1提供，不读取密封内容。当前权重与官方Pi05 checkpoint revision6222623f635769bfc73c9472e29fab9b7fd8e027一致；是否含LIBERO90训练仍unknown（报告SHA65aec68b82faf852e78f15ccc8cf942332031e10ca0d8b77f03ce6266e9a865d）。未冻结、未新训练、未采冻结后大数据。
