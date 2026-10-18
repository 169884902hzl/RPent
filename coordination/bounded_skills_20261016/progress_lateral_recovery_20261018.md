# 公开恢复选项与 node02 三卡进展（2026-10-18 UTC）

Codex1 / Codex2：继续10/16技能包方向，仅仿真，不训练。node02三条串行通道，合计最多3卡；node01无自有新作业，不修改c5/c6/rf与历史JobHeldUser。

## 本轮修复

源码已推送 harness-v5：`e6b0b47765c0cda7b4ef7a49e2cd9bc0ff7fd712`。仅修改私有上限选择器：完整搬运、对齐和向上微移都受阻时，选择现有公开候选中能缩短目标距离、已通过几何检查的平面微移。请求、schema、候选几何、碰撞间隙、执行器和测量回执均未修改。

真实保存请求 job8249_60 step12 的逐字节等值CPU配对：旧选择器选择 `observe(wrist_scan)`；新选择器选择原候选 `nudge(y,+0.01m,e6)`。原请求已有x+2cm、y+1cm和转腕45度三种可达且不碰撞的候选，旧选择器只尝试向上恢复，遗漏了平面恢复。证据：`reports/cup8249_oracle_recovery_pair_CPU_20261018.json`。这是选择器配对，不是物理成功。

240项CPU测试通过（87.46s）；针对性9项通过；Ruff与改动文件的diff检查通过。命令：`.venv/bin/python -m pytest tests/unit_tests/robots/libero/test_bounded_skills.py tests/unit_tests/robots/libero/test_v5_oracle_policy.py -q`。保留已有unknown timeout配置警告，退出码0。

## 未解决的测量问题

11ec9aa完整杯子回合8249_60为0/1，17次决策、1973仿真步、约1559.0s。第一个杯子已放好，第二个杯子抓起后的搬运受阻。公开逐阶段复算：残留杯壁点距已归属点9.32–9.80mm，仍在测得的物体范围内；它们位于自过滤后夹爪间的细窄可见缝隙，既无当前语义种子，也无3mm深度连通路径。私有射线仅用于诊断，证实为真实杯壁，不进入控制。旧刚体预测距这些点18.99–20.57mm；通用圆柱拟合也不支持1mm残差（中位残差2.74mm）。未放宽阈值、未把这些点删成机器人像素。几何归属仍待修，先物理检验已存在的公开恢复路径。

## 原版开发结果与运行

关闭π0.5，启动预检不计任务分母；同状态跨源码重放不能增加独立状态分母。

| 源码 | 类别 | 原生成功 | Wilson95% / 说明 | 中位墙钟 |
|---|---|---|---|---|
| 3d71f44 | 碗 init3–18 | 13/16 | 56.99–93.41%；init19仍运行 | 570.770s |
| 9cacb71 | 抽屉打开 init0–1 | 2/2 | 34.24–100%；其余18状态继续 | 945.282s |
| 9cacb71 | 抽屉关 init0 | 1/1 | 20.65–100%；剩余19状态已排队 | 2209.275s |
| 9cacb71 | 开火 init0 | 1/1 | 20.65–100%；剩余19状态已排队 | 209.731s |
| 9cacb71 | 关火 init0 | 1/1 | 20.65–100%；剩余19状态已排队 | 254.402s |
| 11ec9aa | 双杯任务 init0 | 0/1 | 0–79.35%；第二杯搬运碰撞筛查受阻 | 1559.0s |

8250_120：af76e3d同源同launcher关闭微波炉启动通过，实际290步。8253_140：e425264同源同launcher打开微波炉启动通过，实际444步。8255_120完整关闭正在跑；8256_140完整打开串行接续；8257_14联合绑定碗init14启动接在其后；8258_60新e6b0b47杯子启动再接其后。启动通过并有真实物理请求后才放同源完整数组。另两通道8192→8252与8173继续，未取消任何运行作业。

新源码快照：`/public/home/sunyihan/rpent_libero_eval/source_bounded_e6b0b47_20261018`。归档SHA256：`5e3de89ae49e38bb27aa7c250a9661f81708e4639dfbaaf33d4e685bf5fad0c6`。220状态CPU预检通过。Manifest：`results/bounded_skills/feasibility_20261017/preparation/original20_manifest_lateral_recovery_20261018.json`，SHA256 `e5fcac39dd026c7daccb10b12024e1990c70f71a89abbbd98a4bffed1265390e`。

规格 `SKILL_PACKAGE_SPEC.md`；机器合同 `rpent/skill_package/schema.json`，仍为bounded-skills/1；入口 `scripts.probe_bounded_feasibility:episode`、`robots.libero.bounded_skills:MeasuredSkillAdapter.request/execute`；解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

各类尚未全部完成20状态，不做类别通过或冻结结论。先补oracle上限，再同状态两个对照、K1/K4与分叉；不使用PRO。全部确认状态永久排除训练仍有效。
