# Codex3：平底锅5/10cm试抬探索预提交回执

已接受用户10/05 11:30要求，已核3550完整结果、494固定前50的100条choices SHA、C抓后行为及491勘误。95/90/95门槛、真值≥3cm＋无原支撑＋0.5s持续手指支撑保持不变；新确认状态不消费，默认runtime/renderer131不修改，无异议。

固定前50 centre43/50，失败7中4有手指支撑但最低几何抬离不足3cm。基于这个原版任务证据登记试抬5cm对照与10cm条件，各100请求；仅改物理试抬距离，同一frying pan短提示、high10cm接近、160动作块、两帧视觉验证与夹爪附近检查。50个原版LIBERO10 task2 init每arm各reset两次，是探索名义试次，不是独立确认。
两arm均开启只读私有phase快照：public contact返回、试抬返回、各视觉帧，保存最低几何/接触/sim_time；快照只是单时刻诊断，绝不代替0.5s真值，也不进控制、状态、候选或训练。primitive和已采帧及时保存，后续异常不抹掉已完成接触证据。40 focused tests通过；真实200物理请求尚未运行。

拟提交新数组一次，Slurm编号由提交返回，尚未分配：`sbatch --parsable --dependency=afterany:3620 runtime_launchers/run_v5_grasp498_pan_lift_full.sbatch`。
输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp498_pan_lift_comparison_20261005/full_job<array_id>/part0–1/`。
GPU预约：afterany3620保证当前链最多2卡；array0–1%2、每片1GPU/8CPU/90GB/4h/nice1000；无节点绑定，不修改3616/3619/3620或旧held作业。依赖只用于资源顺序，不根据探索/确认成绩绕过。

source `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp498_pan_lift_comparison_20261005/`，commit8b91a91；archiveSHA828fdc326ab797609261a4cba4bcc0dcddc15fd2e4f5786074dfe620585c52a2。
manifestSHAa9046091f39c5df74e7096945d87dd3fc5a3158afb98cc5e9fdee55c1e92c71a；launcherSHAca9a3b183740c9b5ade6bf1a5369f2d849a15be75d29966f859cb01b419930d1；probeSHA90557bbbd5f6b25bc17319681ca8b1f8c9b1d2b318e6a35992ebe18b585423f4。
入口scripts/probe_v5_grasp449_20261005.py::main，解释器/public/home/sunyihan/rpent_libero_eval/.venv/bin/python。回执先push、远端COORD append及SHA/import核对后再一次sbatch，随后补实际ID与结果。
未完成：四条件pan探索全400、摩卡壶探索300、六类独立确认、共同harness接入及A3/A4复测；当前NO-GO。
