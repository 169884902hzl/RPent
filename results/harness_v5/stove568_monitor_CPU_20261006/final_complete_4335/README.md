# 4335 五局完整结果

5片全部COMPLETED 0:0；800条公共逐块观测、1610条私有逐块评分、30阶段capture。3280个显式输入文件SHA全部匹配（包含逐块RGB/world）；0执行或评分故障。

5/5状态曾达到off（Wilson95% 56.6–100%），接触终点、release后、retreat后均1/5（20%，95% 3.6–62.4%）。4局在接触160块结束前已失去off，release/retreat没有把这批唯一终点off状态变成失败。

|init|首次off块|off评分块数|接触后q|release后q|retreat后q|结束结果|墙钟s|
|---|---:|---:|---:|---:|---:|---|---:|
|0|20|32|-0.005629|-0.005006|-0.004881|retained_off_after_retreat|456.9|
|1|43|18|0.474420|0.408535|0.407247|off_reached_then_lost_before_contact_end|461.4|
|2|46|26|0.594835|0.593363|0.595866|off_reached_then_lost_before_contact_end|463.2|
|3|24|20|0.202709|0.250050|0.529006|off_reached_then_lost_before_contact_end|1661.2|
|4|73|34|0.481352|0.505246|0.475856|off_reached_then_lost_before_contact_end|1656.9|

总体中位墙钟463.18秒；node01两片的约1657/1661秒包含此前节点阻塞，不当作算法耗时优势或物理失败。

red_fraction=0诊断仍有686个假阳性、260个真阳性，precision27.48%；不校准scalar stop、不读private q控制动作。本批固定前缀中首次off后仍继续，不能由后置私有曲线宣称某个公开stop已验证。

这是5个原版选择状态，非独立确认批，不改官方判据。下一步多帧验证器只用公开输入，并按rawstate分训练/验证；private labels独立保存。
