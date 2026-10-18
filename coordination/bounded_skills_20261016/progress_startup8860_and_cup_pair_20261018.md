Codex1 / Codex2：b6cf6d0同快照同launcher启动检查8860_24已COMPLETED 0:0，真实175仿真步，1次决策，97.933秒，pi05_calls=0。startup_physical不是完整回合成功，不计入技能上限。原始证明与状态写在reports/chunk_v3_self_filter_20261018_full_submission.json的startup_proof。

通过启动检查后，正式数组8862已提交，indices=0/60/100/120/140/160/180/200，使用b6cf6d0快照，逐状态比较新旧chunk边界规则；8862_0已在node02运行。解释器/public/home/sunyihan/rpent_libero_eval/.venv/bin/python；入口scripts.probe_bounded_feasibility:episode；schema bounded-skills/3与SHA不变。源快照/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_self_filter_20261018_b6cf6d0，archive SHA256 cc0a7bdc5578aa97a0c325d4a43aa4e30128cd41ef724f49b7a8edc78042bffe。

739fa4b的杯子双物体代表状态8846_60配对闭合，两臂均原生成功：

| 规则 | 决策 | 仿真步 | 墙钟秒 | 感知秒 | 后果/规划秒 | 仿真/渲染秒 | oracle独占秒 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 新chunk规则 | 6 | 2009 | 961.247 | 376.563 | 494.108 | 36.029 | 14.684 |
| 旧chunk边界 | 11 | 2009 | 1268.053 | 433.318 | 740.082 | 35.263 | 24.195 |

两臂pi0.5耗时都是0，未列的IO/执行杂项与残差仍保留在完整时间报告。新规则墙钟减少24.2%，这是一个原版状态的探索性配对，不是稳定的类别提速结论。新规则执行内感知250.795秒（包含在376.563秒里），旧规则197.919秒（包含在433.318秒里），不能重复相加。

同一739fa4b下，碗/罐头/容器/杯子四个已闭合代表状态均两臂成功。它的关抽屉新臂失败（7决策/490步/985.852秒，planning_unreachable/no_public_option），旧臂仍在跑；后续da28708在同一关抽屉状态的新臂成功（17决策/635步/2230.617秒），其旧臂尚未结束。失败与源码身份全部保留，不把跨源码的行合成同一个配对或独立样本。

时间报告：reports/wall_time_live_pairs_20261018.{json,md}；配对与截断报告：reports/chunk_v3_fixture_surface_20261018_paired_latest.json。它们只统计已实际完成的臂，pending列表保留未闭合状态。尚未完成当前源码每类20局上限，不作冻结、确认或训练结论。当前四卡均本组node02任务，Codex2无GPU工作时借第四卡；继续监控其返回并调整后续并发。
