# 4463 的退出记账修复

4463 实际执行了 16 个 VLA 块、80 个控制步，保存 9 条多帧记录；
`first_attempt.physically_executed=true`。原 launcher 从
`first_attempt.server_chunk_execution` 读取计数，而实际计数在行顶层
`server_chunk_execution`，因此错误退出 1。

修复只改读取位置并要求该技能确已物理执行。原作业的 FAILED1 与账本
保留，未重跑物理。用其真实账本重放 shell 最后一个 Python 边界，退出
0、contract PASS。这个 PASS 只证明启动与写账，不证明开门或技能达标；
本局 setup 前后门均已开，不能计为新开门成功。

`physical_exit_fixture4463.json` 是同一账本的字段投影，记录原 SHA。
9 条记录保留数量与 stage，完整记录在显式原账本中。外部子进程回归
4/4 通过：真实结构通过；零控制步、未物理执行、startup_error 均非零。

完整账本：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave581_temporal_smoke_original_20261007/capture1/episodes.jsonl`

原 SHA256：`da104c9571059f48a30ac4017825ce8861e4925e5849f900c6c78ec29eeb216d`

公开门平面缺测诊断由独立报告保留：18 帧仅 agentview 有贡献。起始
step21 的 robot mask 缺失，occluded=null，坏基准帧导致后续八次公开
端点均无法判定。不能把缺测改成通过。
