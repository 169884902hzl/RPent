# 4335 第一批完成 3/5 状态

part0–2（node02）全部 COMPLETED 0:0，elapsed 8:33–8:34；每局 160 条公开 off 观测、322 条私有评分、6 阶段完整，640 个逐块 raw RGB/world 引用存在，无执行/评分异常。物理阶段结果 after_contact / after_release / after_retreat 都是 1/3。三局都曾满足官方 off，其中 s1/s2 在接触160块终点之前已经丢失。中位回合墙钟461.40秒。

|状态|首次满足off块|接触终点off|release后off|retreat后off|真实失败类别|
|---|---:|---|---|---|---|
|init0|20|是|是|是|恢复后仍关闭|
|init1|43|否|否|否|接触中关闭后再丢失|
|init2|46|否|否|否|接触中关闭后再丢失|

part3/4（node01）尚在RUNNING，分别只保存8/9个公开off观测；两个文件约同秒停止写入6分钟以上。对node01的只读SSH hostname也15秒超时，无输出；保留状态，不算物理失败。已立即交root处理，未自行取消或重提。

这是同一批五个原版选择状态中的中间开发记录，不是确认批，不改变完成判据。公开stop保持禁用。大型raw图像/点云SHA由observer写入，CPU monitor只验证文件存在；阶段标签/公开测量和ledgers SHA单独验证。
