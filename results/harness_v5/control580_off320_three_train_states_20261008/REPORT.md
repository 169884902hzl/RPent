# control580 r4 三条 train 原状态完整物理结果

4505_0、4511_1、4511_2 全部 COMPLETED 0:0，墙钟分别 10:20、10:46、10:47。同一不可变 source555 + r4 预算覆盖、同一 run_capture.sbatch，无节点绑定。4505 完成真实首局启动门后才放行其余 train 状态；seed0 未重跑。

| train seed | 真关火块末端 / 320 | 首次真块 | 首次退回块 | 最终 turn_off | 最终私有 q (rad) |
|---|---:|---:|---:|---|---:|
| 0 | 47 | 22 | 49 | false | 0.054040 |
| 1 | 49 | 24 | 47 | false | 0.212439 |
| 2 | 18 | 21 | 39 | false | 0.573688 |

三条状态都在前160块内达到终点，随后继续执行退回。三条状态最终关火均失败；after_contact / release / retreat 后也均失败，seed2 最终 turn_on=true。这是开发诊断的失败记录，不删除或改写。

完整公开 off ledger 共960行；私有 labels_chunk ledger 共1446行（每态 on161 + off321），与每5个controls后的公开块末端逐一配对。7200 contact controls 之外，另有72个open-gripper时序hold controls和各局独立release、retreat脚本动作。真值每块末端保存，未保存逐control真值。

18个恢复时序frame / 36个view中，12次真正control查询全部no_valid_current_control / unmeasured，control_pose和directed angle为0。另24个view故意只保存原图，不算SAM查询失败。恢复时序label全为turn_off=false；正类114个来自已保存的contact块末端原始RGB-D。

114/960是同局相关块末端出现终点的计数，不能称独立任务成功率，不据此计算总体Wilson成功区间。行为停止门始终关闭；私有truth只用于执行后的标签，未改变预算、动作、ROI或停止。

固定off320不能代替终点停止。跨跑π0.5随机前缀不固定，不能把r3→r4的差异单项归因于预算。后续train-only小验证器复用公共时序编码器，seed0–2用于开发拟合；validation seed3–4保持未读，停止资格pending。

源码commit：`c56de638fc5a5f0376194768b4d3d484369eb435`

运行manifest：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r4_off320/capture_manifest.json`

SHA：`10d3dfb57daae71fb5b9b36bc27d372ef61709862d9b84187b269afbecf000a4`

读取只按上述manifest、显式job/part及episode中保存的引用；report.json包含每个源路径/SHA、全部块末端诊断标签、公开测量可用性。未打开PRO正文、未打开validation状态或轨迹、未扫描artifacts。确认排除registry仍标记incomplete；仅报告对已登记排除项零重合。
