# 成功反馈与持续尝试：当前回合

执行用户 10/23 14:00 PDT 指令，13:50 版作废。本轮不训练模型。
node02、nice=500，Codex3 最多 3 GPU；与 Codex2 合计不超过 80 CPU / 600 GB。
不修改用户 p3/c5/c6/rf/RVRT 或旧 held 作业。自己的队列未清空时继续工作。

## 已推送与通知

- db8be033：A task_success / B subgoal_status 独立开关、schema8、legal/6。
  A true 在感知前结束；A false 时 finish 非法；无人时 ask_help 非法。
- 2b5653c2：40 决策 / 10000 环境步的持续尝试、宽容 measured_anchor 准备段、公开 RGB-D 接触控制原型与配对 runner。
- d357fe3a：原生成功查询修正为 inner LIBERO `_check_success`；只在唯一公开子部件支持时解决重复 fixture 父实体；测试与报告脚本。
- 三项提交已推送 user-fork/harness-v5。C1/C2 已通过共享登记及 owner_alerts 收到字段、SHA 和当前执行树。

合格执行基底为 df589b7d，不把本地 HEAD 其他抓取改动或 dirty SAM cache 混入。
实际冻结执行树：3605901c7425d27df9fa04d1ca7345aeeb388663。
远端：/public/home/sunyihan/rpent_libero_eval/source_feedback8_3605901c_20261024。
schema SHA：5ab07c9ce77fef3f339cbb29fc6d45fd5f7060f1bcf193f044e229448a8928b4。
contract SHA：b6917b52a9cbe317adebec3d3140e2db509a838a898bb0db330952a8d2eba99b。

CPU：36 项 feedback/schema/staged、12 项循环/控制、7 项 native/contact 复现已通过。
旧 58b98480 的 native API 程序失败保留，不算任务失败；当前三臂均为新目录。

## N2 已闭合

12 状态 × screened/permissive × 3，共 72 次，unknown=0，36 对完整初态 SHA 一致。
原检查准备后 π：0/36 成功，6/36 调 π。
宽容准备后 π：7/36 成功，36/36 调 π，但仅 9/36 到点。
新增/加深接触 >1µm 为 15/36，>1mm 为 3/36；非目标最大位移 0.00589978 m。
不把准备放行当作到点，也不把同一状态重复当独立布局。

远端报告：results/bounded_skills/success_feedback_20261024/CPU_N2_r3_closed。
本地镜像：coordination/bounded_skills_20261016/reports/success_feedback_20261024/CPU_N2_r3_closed。
逐状态 paired_table.md、逐次 trials.jsonl 和 raw SHA 均已登记 C1/C2。

## 运行和排队

远端 RUN：/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/success_feedback_20261024。

- 11955 N2 已完成。
- 11956 pi_A：40 D2 + 原版 6 臂，运行中。
- 11957 新技能：四类 40 原版训练状态 × 3，运行中。
- 11958 oracle_A：同 46 臂，运行中，宽容准备开启。
- 11959 oracle_AB：依赖 11968，优先接替新技能重测的卡。
- 11968 新技能 r2：同 40 状态 × 3，运行中，完成后接默认项。
- 11963 默认 63 train 候选 × 3：依赖 11958，沿用 oracle_A 的卡，不超过三卡。

A/B 两臂 oracle 本身均读私有谓词，B 的公开与否并不增加 oracle 知识。
选择器为规则 + 历史有限采样偏好，结果不是穷尽动作和随机种子的数学上界。
报告将保留每局选择、决策数、两种墙钟口径、Wilson 及相同初态核对；N8 不称 N1。

## 新技能开发证据

首轮 40 状态 × 3 已闭合，成功 0，3 次公开绑定缺失为 unknown，6 次实际运行了推进。
原件和报告分别为 RUN/skills_r1、RUN/CPU_skills_r1_closed。

同状态 case005 捕获并重放了真实拒绝：左指壳–场景点起点间距 13.76 mm，
2 cm 路线在约 18.6 mm 处降到 3.81 mm。4 mm 余量不变时，1 cm 前缀通过。
修为只有未执行的碰撞拒绝可再筛 1 cm；每次筛查完整保留。
修后独立树 75e333fad1542733ab14aab9f86888c1777730a7，仅改变新接触模块。
运行 11968 / skills_r2，不改已运行的三臂源码或旧结果。

r2 的 case005 首试已实际推进 173 控制步并触发 native 成功；每步兼容区间支持推进方向。
另一个旧零步状态已运行 14 步。尚不把这些未全闭合状态当作 3/3 成功。
发现成功后 refresh 没有配准值，被写成 contact_motion_unmeasured；已修成先处理 native stop，
环境预算截断另报 environment_budget，不能当成功。此修复尚未进入 75 树。

v9 菜单原型默认关闭；公开候选为六个把手方向与所有测得的目标区域，不按任务谓词筛选。
回执增加 contact_displacement_m；未执行时 null。legal/7 在实测接触回执前不预测后继。
修复了 prefix_context 沿用旧 schema 的问题；现在继承输入请求版本。
本地相关 77 项 CPU 测试曾通过，后续 native-stop/null 补测 10 项通过。
精确 v9 树现为 018f13c6728abae8279902b70dac847f365340d0：
source_feedback9_018f13c6_20261024。a439 树 CPU 341 通过、1 条过时测试失败；
它还期望无人时提供 ask_help。018 树仅同步这个已有测试，执行文件 SHA 不变。
11971 的完整 CPU 面板已通过 343 项（1 CPU / 8 GB，无 GPU）；
日志 CPU_qualified9_018f13c6_tests.log。
未混入当前三臂，也未通知模型侧启用。准备了一个训练状态 × 3 的 v9 精确菜单冒烟，
CPU 通过后已提交 11973，依赖 11956 + 11968 + 11971，沿用 pi_A 的卡，不增加第四卡。

## 默认 63 项

MISSING_DEFAULT_MEASUREMENTS 中 63 train / 54 holdout，只测 63 train。
CPU 精确旧 request、snapshot、contract、candidate 绑定核验 63/63 通过。
执行树 f6987f0d，未换 source 或上下文，不把新源结果回填旧标签。
清单和 CPU 核验在 RUN/preparation/default63；输出 RUN/default63，完成后导出给 Codex2。

## 待交付

1. 修复有真实输入支持的新技能拒绝；四类每状态 3 次，准备与推进分开统计。
2. 三个 46 臂全部闭合，逐局同表、Wilson、决策数及墙钟。
3. 新技能菜单/规格及 schema 通知，仅在相应实测之后启用。
4. 有余力完成默认 63 × 3 并按已接收格式交付。
5. 按文件暂存提交；保留无关 dirty，不改运行快照，原件和失败全部保留。
