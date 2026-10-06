# Codex3：3722重复失败根因修复与新冒烟预回执

3722原始记录保留：截至18/20完成、14物理成功；原版libero_10 task1 init0同一个vla_subtask连续7次验证failed，却因测得物体/框变化清空计数。修复robots/libero/v5_recovery.py：当前失败动作的计数不被自身位移清除，本次失败始终计入；两次失败屏蔽；其他恢复动作测得场景变化或本动作验证成功可释放。未新增状态字段，格式不变，但恢复数值语义修正，已在本回执通知Codex1/Codex2，冻结后训练必须用最终源码新采。30 focused tests通过，等待物理验证。

源码commit2312d6f，snapshot /public/home/sunyihan/rpent_libero_eval/source_v5_runtime537_20261006。新20局仍为原版10+开发10，same registered budget；不是确认批，可以修复后重跑，旧物理失败不删。新增仅preaction success诊断，执行前保存独立概率，不改变选择，用于用户第8项配对。

计划作业：Slurm分配后回填；无依赖/节点绑定。3722剩1片运行，其余7卡空闲，本次array0-7%7，释放后提高到%8。manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime537_smoke20_20261006/preparation/manifest.json（逐片SHA显式列出）；输出 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job<JOB>/part0..7。独立job目录，不覆盖3722。

计划命令：SMOKE536_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime537_20261006 SMOKE536_PREP=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime537_smoke20_20261006/preparation sbatch --array=0-7%7 --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_runtime537_20261006/scripts/run_v5_runtime536_smoke20.sbatch。

所有8片CPU路径/init预检通过后才提交。本次未达到smoke准入前，不提交大批量技能。新第三开合方法已有CPU实现（实测把手+腕部融合+安全预接近），物理未验；stove旋钮接口继续补足。技能确认/集成/冻结尚未通过。
