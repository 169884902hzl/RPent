# Codex3：用户11:30交接后的平底锅400次正式探索登记

已读取并接受本提示及3550全18片产物：按类别技能卡只基于原版任务选方法；确认门槛仅由与探索不重合的新原版状态判定。未启用PRO/人工/密封文本，未改变95/90/95；无异议。

拟提交一次新数组（Slurm编号由提交返回，当前尚未分配），4片各100次，array0–3%2、每片1GPU/8CPU/90GB/4h/nice1000；无节点绑定，无未满足依赖。原3550及3554/3565/3591/3598/3604均已结束，不修改或重提。
实际命令：`sbatch --parsable runtime_launchers/run_v5_grasp488_pan_full.sbatch`。
输出：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp488_pan_prompt_handle_budget_20261005/full_job<array_id>/part0–3/`。

四条件：原版叫法frying pan、body-centre接近160块；测量把手接近160；body-centre320；测量把手320。每条件100首次请求；原版LIBERO-10 t2的50官方初始状态各reset两次，仅用于探索。不得作为新确认样本。别名依据原版LIBERO-90 t18/21/40/41/42/45语言，标准40原指令没有平底锅目标叫法；只把原版实际名词移入抓取短提示，不读PRO或RPent扰动memory。

统一实验验证器：public pi0_pick之后总是试抬5cm，间隔10控制步的两次新视觉测量均要求底边升高≥3cm、开度2–70mm、物体测量框在夹爪附近（xy外扩4cm，TCP到手指15cm范围）。无仿真真值输入。此为探针开关，不修改默认runtime或renderer131格式。真实持续几何/接触仍仅作私有测量标签；同时报缺测、stage未执行、FP/FN，不把unknown或基础设施失败算模型成绩。

完整指令C检查并行进行；已出现moka抓起后输运/释放到灶台的单例证据，碗/瓶尚未发现这种证据，现有public stop保留。独立确认池正在显式登记六类各100个原版官方新状态，含LIBERO-90，按state字节SHA排除3550，先选recipe再执行，当前确认未开始。

source快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp488_pan_prompt_handle_budget_20261005/`，commit dc79638；入口 `scripts/probe_v5_grasp449_20261005.py::main`，解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。
archive SHA256 `977aa3004f0cb484623c541242733b5c0a59d6b2427d44224644d2dfd585c8ea`；full manifest SHA256 `7f53e64c71ab6c74309424e6ec2a819c57495417c1c9c92bd1b861dac63eee1c`；launcher SHA256 `c16aa2350c58b3470fc2026e0f6bd8ca8101b84b640957fe6f0dbaa91f92ef4b`。
39 focused tests通过、bash-n/diff-check通过。物理0/400尚未执行，不能声称修复达标。

本回执推送并确认远端append成功后才sbatch；提交后立即补实际ID、命令、目录与状态。GPU预约：本数组最多2卡，无节点绑定，其他卡留给共享训练；若共享整节点训练预约恢复，以COORD当前预约表让步。不释放旧held作业。

## 实际提交回执

3612一次提交成功。命令 `sbatch --parsable runtime_launchers/run_v5_grasp488_pan_full.sbatch`，无依赖；实际输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp488_pan_prompt_handle_budget_20261005/full_job3612/part0–3/`。
pre回执73ae5ba已推送，远端append及SHA/import/bash-n明确返回成功后才sbatch。源码dc79638，400次，资格与确认仍未完成。提交后立即核队列、加入监控，不修改其他held链。
