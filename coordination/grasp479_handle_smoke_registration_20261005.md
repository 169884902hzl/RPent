# Codex3：测量把手接近smoke提交前回执

已读取并接受10/05 01:45与03:10抓取要求、最新COORD及3550_0–7正式产物。
原有3550/3554/3565/3591/3598不改、不重复提交；95%总体/90%每类/95%验证器
一致率及正式每类100次、Wilson95%CI、FP/FN报告保持。真值只用于诊断标签。
当前六类资格、A3/A4复测、严格place完整物理复验、冻结均未完成。

GPU预约：本次1GPU/8CPU/90GB/1h/nice1000，无节点绑定，依赖afterany:3565。
3565依赖3550完整结束，因此本次与3591或其后继3598最多占两张卡。
预提交回执先推送，再append共享COORD；确认成功后只执行一次：
`sbatch --parsable --dependency=afterany:3565 runtime_launchers/run_v5_grasp479_pan_handle.sbatch`。
作业号尚未分配，提交后立即补记；输出目录
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp479_measured_pan_handle_20261005/smoke_job<assigned_job_id>/`。

平底锅前30条已闭合前缀只有1条真成功；29次真失败中24次public pick宣告成功，
5次用满160块。前缀不算100次正式结果，不改原label。
本次10次smoke：5个相同原版init×2组。centre control与measured handle共享
frying pan提示词/别名、160预算、停止规则、2mm实验开度及单帧验证器。
只换当前RGB-D/SAM测量把手的接近位置，z=max(测量把手z,物体测量顶面)+10cm；
不读BDDL/仿真坐标/PRO来定位。唯一把手缺测返回unverified，不虚构几何。
其他类在后续full登记中仍保留相同centre control，不归因其噪声差异。
此变体不计为已完成的另一种物理方法，不改变默认runtime/renderer131。

source快照
`/public/home/sunyihan/rpent_libero_eval/source_v5_grasp479_measured_pan_handle_20261005/`，
commit `cc34e7b`，archive SHA256
`b72810bb2df4072993cf58bd7398b1c0584b7e88f345a90fbe3d86e1206c67ec`。
入口 `scripts/probe_v5_grasp449_20261005.py::measured_handle_approach`；
解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。
smoke10 SHA256 `22612d2593665734dfb958cb91449d914f22f6b1c0e10cb49d2b834a4fb8718b`；
full1200 SHA256 `7e49d9a3fc1b0a36904e73d545337ecbc5799a183344c0fd126400168e900930`，仅准备未提交。
launcher SHA256 `20510adc956fff6a8aa8c839cf69101729763687e6a76f5580c3d258244665eb`。
48项绑定/视觉验证/私有真值/感知几何测试通过，远端入口import及bash-n通过；
实际物理smoke0/10，尚未运行，不能当成功率或训练准入。

无异议。此前3598晚append回执的顺序错误已保留并纠正；本次将各步骤分开执行，
确认append成功后才提交。本轮诊断init0–49不入训，不读人工/密封文本；
不改共享服务。若后续采用新回执或恢复语义，先交Codex1/2重渲染。

实际一次提交 **3604**，`afterany:3565`，实际命令同上，输出
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp479_measured_pan_handle_20261005/smoke_job3604/`。
预提交回执ee4f635推送成功后，逐步核对scp/远端append成功，再执行sbatch；
PENDING(Dependency)，物理0/10，full1200未提交。已加入现有watcher，不改变旧作业。
