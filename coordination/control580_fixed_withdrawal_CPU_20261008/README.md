固定撤臂诊断包已准备，尚未验证物理执行。3 个既有原版 train 态（libero_goal/task7/init0–2）分别执行固定 off20/40/160，共 9 局；val3/4 不读。

唯一远端入口：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/control580_fixed_withdrawal_CPU_20261008/preparation_r1/run_fixed_withdrawal.sbatch`。来源仍是不可变 `source_v5_stove555_20261006`；新增 collector/server/driver/producer 逐文件 SHA 在 manifest 中。

每局先固定 on160，保留接触，再执行预登记的 off 块数。固定块终点保存 before 帧，然后显式 release、三帧序列、retreat、三帧序列。序列帧之间各执行 6 个 open-gripper hold controls。release/retreat 的真实控制次数与额外 24 个 hold controls 单列；测量插入可能改变家具状态，不能当成无干扰观察。

私有关节标签只在执行后用于比较撤臂前后的家具变化，不决定块数、ROI、命令或停止时刻。撤臂命令不是可见性证据，旋钮仍被挡住时记缺测。未训练新验证器，stop 未准入。

同一运行的撤臂前后可以配对。与旧 r4 只匹配原始状态、指令及声明的块调度；旧 VLA 动作 prefix 未做字节重放，因此不能作旧运行的单项因果归因。

检查：同一 launcher 的 9 个 shard CPU 前检均 exit0；有意传错误 manifest SHA 的 CPU 检查产生 startup_error、exit1、零物理动作。正式提交必须先只放 shard0；保存实际物理控制后，主代理才放 shard1–8。GPU 预约与提交由主代理负责。
