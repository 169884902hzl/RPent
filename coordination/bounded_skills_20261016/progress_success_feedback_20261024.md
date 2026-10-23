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

## 22:41 UTC 后的已核结果与恢复命令

新技能 r2 的 120 次全部闭合：117 对可测分支的完整初态 SHA 与 r1 一致；改善 6、退步 0，另 3 次绑定 unknown。
关抽屉为 6/30 成功（2 个独立状态各 3 次），12 次真正推进；开微波炉 0/30、3 次推进；
关微波炉 0/27、3 unknown；推盘子 0/30。其他类别主要卡在已有接近准备段，不能称新控制器已成功覆盖。
原始 r2 的 6 个成功仍写 contact_motion_unmeasured，因为成功后停止刷新；不改这些原件。
018 树已修停止原因，待 11973 的精确菜单三次检查。

报告 RUN/CPU_skills_r2_closed（含 paired_with_previous.md/jsonl）；已在远端生成，已本地镜像，待正式最终登记。

代码 a8f35b5a 已推送 user-fork/harness-v5。新 schema SHA
49633b98a14ce6283c2f4b76914ddece49d74072636573b67a4eea6e717179c8；contract SHA
5a82e723a16169e3984e63e52d18d33476d427242fcc8b058f05ffc5d6d9ca31。
已通知 C1/C2：C3_CONTACT9_INTERFACE_A8F35B5A_20261024.json；模型默认仍关闭新技能。
已有 v8 三臂继续固定 360 树，不把新菜单结果混入三臂。

当前资源链保证最多 3 GPU（未借第 4 张）：
- 11956 pi_A → 11973 menu9_smoke（后者还依赖 11968 与已通过的 CPU11971）。
- 11958 oracle_A → 11963 default63。
- 11968 skills_r2 → 11959 oracle_AB。
最后 squeue 中 C2 只有 CPU11967/11972；用户 p3 已自然退出，未做任何修改。

三个整局臂最终 CPU 汇总（必须全部 138 条闭合才执行）：
`ROOT/.venv/bin/python ROOT/report_success_feedback_CPU_20261024.py --run RUN --output RUN/CPU_three_arms_closed --suffix _r1`
保留三臂 46 对同初态核对，40 D2 与旧纯π初态 SHA 也核对；Wilson 和逐局决策/双墙钟口径完整输出。
注意 oracle 自己在 A 与 AB 都知道私有谓词；B 的公开不增加 oracle 的知识。这不是穷举数学上界。

默认63完成后导出（ROOT、RUN 见上文）：
`ROOT/.venv/bin/python ROOT/export_default63_CPU_20261024.py --manifest RUN/preparation/default63_r2/manifest.json --results RUN/default63_r2 --output RUN/CPU_default63_r2_export_closed --prior-export-manifest ROOT/results/bounded_skills/next_b_pi_first_20261023/train_dagger_once_priority1/CPU_export_preview1/manifest.json`
导出前检查 worker 程序错误；开发错误须修并恢复，不写失败报告后停。所有未知试验保留，不编成功/失败。
两个固定 helper 在 next_b_pi_first_20261023/entry_snapshots，SHA 612082b8…（measured_row）与 6142d6cd…（prompt）。
参考 prior manifest 的 policy_hashes_source 已定位，无须重新递归扫描。

/tmp/freeze_feedback9_20261024.py 已把比较基准固定 d357fe3a，不能改为当前 HEAD，否则会丢掉已提交修改。
新源只能新建快照，不能原地改 360、75 或018。当前源安装、CPU面板、菜单准备脚本均在远端 ROOT；
menu9_smoke_submission.json 存完整依赖与 CPU 日志 SHA。

后续：镜像 r2；跟踪三臂/默认项/菜单冒烟，程序错修后继续；导出并登记给 C2；收齐表后更新 spec 的 pending 状态、提交自己的收尾文件并推送。
仅全部自己的运行/排队任务清空且要求产物闭合后结束回合。最终先 ≤5 句结论，再证据与逐局表链接。

## 23:10 UTC 进展与采集接口修复

- pi_A 46/46 已闭合：D2 21/40，原版6/6。oracle_A 46/46 已闭合：D2 28/40，原版6/6。
- oracle_AB 11959 已运行，最近40/46；不可提前给完整三臂汇总。
- menu9_smoke 11973 运行中；首试原生成功，173步，准确选中 open_close_articulated；
  receipt 为 schema9 / success / native_success，contact_displacement_m 为测得的3维向量。
- 默认11963因生产器使用了冻结 f698 不存在的新 grasp_trial_reference API，只取消这个自己的作业。
  f698 真值代码本来直接用 facade.grasp_reference；新冻结生产器只替换这一行，不改评分或旧执行树。
- 11976 是默认项续跑；RUN/default63_r2，preparation/default63_r2/manifest.json。
  12个完整位置（36次）+另外6位置的9次已完成试验原样复用，共45次有效物理试验未重跑。
  原 default63 全部目录未移动，旧22条程序错误日志保留，不算有效正/负标签。
  CPU_API_and_resume.json 核对源端API、唯一改动、旧绑定和每个复用摘要/终点SHA。
  新生产器 ROOT/evaluate_bounded_training_candidate_default63_r2_20261024.py；
  新启动器 ROOT/run_default63_r2_20261024.py；本地 run_default63_20261024.py 已含逐试验复用。
- 第一次导出已成功：RUN/CPU_default63_r2_preview1，20位置/60有效试验（56成功4失败），unknown0；
  每条3次；类别 bowl7/box4/cup3/drawer_open6，均为位置数，不冒称独立状态数。
  C2已收到 C3_DEFAULT63_BATCH1_20261024.json。最终包为它的超集，按query_id/sample_id去重。
- 目前C2有GPU11981（1卡），C3仍最多3卡，未借第4张；合计52CPU/408GB，符合80/600。

最终默认项导出用 r2 的 manifest/results；不要再指向有程序错误的旧 default63。
旧 prior-export-manifest 路径不变。最终导出不加 --allow-incomplete。
新增的总表脚本已补每类K、均值/中位墙钟、逐状态改善/退步和10000步校验；执行前须三个46臂全闭合。

23:10 UTC：C2 GPU11981已启动；C3 11959/11973/11976各1卡，共3卡；总52CPU/408GB。
11976目前56/63位置闭合，未见新程序错误；11959目前40/46，11973首个菜单试验已成功、后两次在跑。
修复/复用准备脚本已本地保存 scripts/prepare_default63_API_resume_20261024.py；
它拒绝覆盖已经登记的 r2 计划。源端 API 旧不匹配已修，不要再取消11976或重采已经完成的位置。

## 最终闭合交付（2026-10-24 UTC）

- 本轮三个46回合臂已全部闭合：D2 纯π+A 21/40、oracle+A 28/40、oracle+AB 29/40；原版均6/6（3初态各K1/K4）。46组初态/seed/config相同，D2与旧纯π40初态相同。
- RUN/CPU_three_arms_closed 含逐局表、Wilson、决策和worker墙钟。是并行N8工作进程墙钟，不称N1。oracle两臂本来都可读私有谓词，29比28不能解释成B信息增益。
- case036（libero_10_task_t2_s40）VLA输入在零基block11先出现腕图像hash差异；预测在block40首次不同，sampling_seed相同。CPU_AB_policy_trace_difference.json仅定位分叉，不声称已证实渲染/数值根因。
- N2最终口径用 CPU_N2_final_scopes：screened调π6/36，permissive36/36，但宽容到点仅9/36；接触>1µm 15/36、>1mm 3/36，非目标最大位移5.900mm。旧0/36→7/36是登记任务谓词；盒子pick没有单独私有抓取v3，每臂6个局部unknown；其他五类局部0/30→7/30。物理试验unknown0。原始结果不改。
- 四类接触120尝试闭合：关抽屉6/30（2状态各3），开微波炉0/30，关微波炉0/27+3绑定unknown，推盘子0/30。117次可计量修前修后初态一致，改善6、退步0；其他类受准备失败限制。精确schema9菜单在单一事后选中训练状态上3/3成功、每次173步，动作与r2差0，不并入成功率分母。
- 默认63已全部导出 RUN/CPU_default63_r2_export_closed：9类各7位置，189试验=157成功+32失败，unknown0。保持旧f698 source和binding，54 holdout排除，45有效旧试验复用；旧22程序错误保留不入标签。final是preview1超集，按query_id/sample_id去重。数据SHA 63f6716f874e8eb9bc8d5d82a4bee28c61604ea812f12579a235c391352bb77d。
- 最终回执数值修复冻结tree736631d06d6dd332144f447b18dde27a4fecde87，只将小位移也累计、无可靠测量记null，不改控制动作；CPU11983 345 passed/1已有warning/194.18s。schema9和contract SHA仍49633b98…/5a82e723…；物理菜单仍引用018树，不改写历史。
- 11956/11958/11959/11968/11973/11976/11983均结束；本轮C3无运行/排队任务，C2 11981未操作。其余项目和旧held未操作。
- 最终报告 reports/success_feedback_20261024/FINAL_REPORT.md；SHA清单 DELIVERY_MANIFEST.json；按文件提交并推送，C1/C2最终登记包含N2口径更正和63项完整包。未训练模型。
