4537_0 已 COMPLETED 0:0，墙钟 2m50；case libero_goal/task7/init0，固定 on160/off20。保存 900 个实际接触 controls，公共 off ledger 20 行、每行 5 controls，私有 chunk ledger 182 行；collector_boundary completed，真实物理启动已通过。

同次运行终点→release 三帧→retreat 三帧，共 7 帧×两视角。release 20 controls，retreat 77 controls，两段序列另加 24 个 open hold controls。公共图像中主视角的旋钮在接触/松手时被夹爪部分遮住；撤臂后三帧可看清轮廓。腕部七帧旋钮都不在视野中。炉圈可见部分一直是红色。公开颜色不是 endpoint 标签，旋钮角度未测，stop 未准入。

私有执行后诊断单独保存于远端 manifest 指定文件，SHA `76a7122a2dc43fce5b686cc2060d90fe248d7a8a4cc0334cff38c31898df296c`。七帧 turn_off 都为 false，未发生 off→on 翻转。contact qpos 0.731983，release 第一帧 0.727800、最后帧 0.729532，retreat 第一帧 0.853741、最后帧 0.855426。retreat 时间窗内约 +0.12421 的变化不等于已经识别 retreat 的独立因果效应：没有同时长的无撤臂对照，也可能含释放后回弹或物理演化。该干预窗口不能当成无扰动静态测量。

与旧 r4 同 init/指令/块调度，不是同 VLA 动作 prefix；不能将旧 seed0/off20 的黑色图与本局红色图作单项因果归因。其余八局由主代理以同 launcher 提交 4538（array1–8），4537_0 不重跑。
