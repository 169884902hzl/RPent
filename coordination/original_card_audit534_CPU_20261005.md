# Codex3：原版合法卡片完整性审计与物理分支重建

沿用 21e3f03 的显式45卡 manifest、source episode/result SHA、request state/options逐字节配对；不读取 PRO、人工或密封文本。旧的合法-memory 18/40 与无卡21/40保留，不改判定。

远端 CPU 输出：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/original_card_audit534_CPU_20261005/report.json`，报告 SHA `ae00d24d14c9bce9b2b4cd26fa983bda1a4b90261d1f8a637069c82e8bbe3a45`；manifest SHA `c03a28ce61ef2db89f88e6a0ffa116fbd627fbf130da83abf3c055a2c561017b`。固定卡统计：base29、反事实16、finish-only10、含grasp33、place2、articulate2。19张旧卡缺失place，其中18/29可由实际 accepted physical branch 与前后谓词进展重建，11/29需要原版重新采集；不从 final solved 或模型句子补动作。

审计计数：matched_positive_physical_branch 41；goal_progress_inside_grasp_macro 7（拒绝将宏动作冒充place）；grasp_has_no_positive_measured_branch 4；legacy_step_has_no_unique_positive_receipt 2；no_matching_physical_label 2；rollout_action_not_executed_without_error 1。11个待重采任务列于同一 report。新采集必须使用冻结后 v2 物理标签与源码哈希；本次无GPU、0新训练行、未冻结。
