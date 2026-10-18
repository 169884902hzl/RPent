Codex1 / Codex2：当前物理快照仍为 b6cf6d0e8cb3b1a5dcd1f6e9d698aafaad170556，路径 /public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_self_filter_20261018_b6cf6d0。没有更改执行器、碰撞间隙、IK、速度、夹持力或预算。schema bounded-skills/3，SHA256 7082085b2c59e592e92bfdfedb85e82e3197c3f366d3f0e9e2959435fb415cb3；私有判定器 libero-private-task-progress-rules/4。

六类原版各20状态的 oracle K4 队列8870已登记：碗、罐头（历史标签box_transfer）、容器、杯子、关抽屉、开抽屉，共120个唯一(BDDL SHA,state SHA)。117局新运行，另3局必须复用同源码8862的索引0/60/100，成功或失败均照录，不能替换或重复计数。只运行oracle_k4，关闭π0.5。原始身份及提交回执见 reports/original20_cohort_identity_CPU_20261018.json 和 reports/original20_self_filter_20261018_full_submission.json。未完成状态不算成功或失败，汇总入口为 scripts/summarize_original20_self_filter_20261018.py。

真实奶油奶酪盒另20状态：启动8861_0同快照同launcher已COMPLETED 0:0，1决策、23个物理步、53.873秒、pi05_calls=0。它是startup_physical，不是完整任务结果。之后提交正式数组8987，全部20状态从reset重新运行，不复用启动结果；排在8870之后，node02、nice500、初始%3，继续由实际资源容量调整。启动证据与原始ledger SHA见 reports/real_box20_self_filter_20261018_full_submission.json。补充20状态与原120状态不重合，并排除了已知确认登记状态。原220控制不覆盖这20个盒子，不能挪用其控制成绩。

已闭合代表配对（同一行内源码相同；都不是每类20局上限）：

|源码/作业/状态|结果新/旧|决策新/旧|仿真步新/旧|墙钟秒新/旧|
|---|---|---|---|---|
|b6cf6d0 / 8862_0 / 碗|成功/成功|3/5|265/265|394.559/474.798|
|da28708 / 8858_100 / 开抽屉|成功/成功|7/10|594/582|1067.315/965.582|
|da28708 / 8858_80 / 关抽屉|成功/成功|17/19|635/635|2230.617/2225.387|
|739fa4b / 8846_80 / 关抽屉|失败/成功|7/19|490/635|985.852/2249.179|

旧739fa4b的关抽屉新臂是planning_unreachable/no_public_option；失败永久保留。后续da28708的同状态两臂成功，与前一行不合成同源配对或新独立样本。新规则在开抽屉墙钟增加10.5%，关抽屉增加0.24%，碗减少16.9%；不能据决策数减少宣称稳定提速。

加法时间分解（主线程独占秒；IO/其他及残差仍在完整报告）：

|源码/状态/规则|感知|规划|仿真/渲染|oracle独占|π0.5|
|---|---:|---:|---:|---:|---:|
|b6cf6d0/碗/新|161.069|213.263|6.991|3.371|0|
|b6cf6d0/碗/旧|175.242|272.327|7.256|7.948|0|
|da28708/开抽屉/新|415.029|504.271|13.374|3.258|0|
|da28708/开抽屉/旧|423.173|477.876|12.932|3.343|0|
|da28708/关抽屉/新|918.399|1216.289|16.888|4.394|0|
|da28708/关抽屉/旧|958.765|1165.867|16.696|4.057|0|

执行内感知是感知列的子集，不能重复相加。新关抽屉为675.955秒，旧为659.745秒；此状态规划仍比感知更耗时。完整报告为 reports/wall_time_prefix_pairs_20261018.{json,md}、reports/wall_time_self_filter_pairs_20261018.{json,md}。尚未缩减回执测量。

CPU复算同状态启动8857_24/8860_24：完整公开request逐字段相等，均56候选，规范JSON SHA相同。保存的request profile总self时间29.707→28.193秒，仅一对启动样本，不作稳定提速结论。新请求grasp_geometry包含时间18.596秒、_cloud_and_ik包含时间15.309秒、PublicRouteScreen.__call__包含时间8.982秒；包含时间相互重叠，不能相加。原始choices、episodes、pstats哈希和重算脚本SHA见 reports/startup_profile_8857_8860_CPU_20261018.json。

继续先完成oracle上限，再两个对照，再K1/K4决策和平滑度，最后分叉。只用node02、nice500；Codex2无GPU工作时暂借第四卡，有其排队后10分钟内降低后续并发到≤3，不取消running，不动c5/c6/rf、node01或历史held。所有确认状态永久排除训练。本轮没有训练、确认批或冻结结论。
