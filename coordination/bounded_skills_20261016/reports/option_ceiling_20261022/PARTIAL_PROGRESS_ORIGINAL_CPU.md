在原版保存的失败端点中，确认了两条“完成当前目标，但未完成整任务”的情况。它们来自原版 LIBERO-10 task2/init10，策略种子42083000和42090000：炉灶已开启，摩卡壶尚未放到灶台。原整句失败分数保持False。

CPU核对共检查12条原版多目标失败端点，逐条恢复native_data并核对字节一致；恢复后不执行控制。两条端点的原生目标向量均为[True, False]。这不是总体发生率估计，来源为按失败和多目标条件筛出的有限记录。

旧混合选择器只使用局部`success`，会把这两个端点当作没有可继续的分支。修复保留抓取、调用和整局分数，另存私有登记目标是否完成；私有oracle允许从已实现的任务进展接续。整局必须继续实际执行并满足原判据，单个目标完成不能宣告整局成功。

原件：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022/measured_anchor_efa57340/CPU_original_partial_progress_r1/`。两个逐端点来源已写入`tests/unit_tests/robots/libero/fixtures/original_partial_goal_20261023.json`。本核对不含PRO、D2、确认池，不用于训练，也不修改历史分数。
