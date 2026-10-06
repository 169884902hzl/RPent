# 4241 当前抽屉测量绑定选择批

5/5 已完成，五片 Slurm COMPLETED 0:0，最后结束 2026-10-06 15:47:07 UTC。SOURCE558 commit `329e81961b100555078c33de8b872108d7b24b8a`，archive SHA `080d3ce9841e766a40530e87dae74d60aa2396fe42f1af35af5d87511ebd2e8c`。原版 LIBERO-90 task6 init10–14，都是已访问的选择状态，不授确认或冻结资格。

实际首次执行5/5，before端点均false；物理新完成4/5，Wilson95 [37.55%,96.38%]。公共true4、false0、null1：TP4，FP0，FN0，TN0，null对应private false。测得到的precision/recall为4/4，Wilson95 [51.01%,100%]；包含null的known-truth agreement为4/5。样本小且重复选择状态，不能宣称总体95%达标。

| init | private before→after | 公共判定 | 实测抽屉延伸 cm | 4235 native原端点/公共 |
|---|---|---|---|---|
| 10 | false→false | null | 缺moving face | true / false |
| 11 | false→true | true | 16.02 | true / false |
| 12 | false→true | true | 16.02 | true / false |
| 13 | false→true | true | 16.02 | true / null |
| 14 | false→true | true | 15.99 | true / false |

每例160块×5=800个VLA controls，总4000/4000，短块0；253个非VLA运动controls另列。native成功不停块、无外部截断、无私有真值控制。0基础设施故障、0物理失败重试。所有调用都是原样注册句 `open the bottom drawer of the cabinet`。公共测量before source_step0、after1，当前可动部件关联由 `current_rgbd_selected_drawer_and_fixed_border/4-dev` 给出，fusion `rgbd_dual_view/1`。18条显式公共几何引用、18唯一路径与SOURCE558源码/archive、原始及捕获ledger合计56项SHA核验全部通过。

唯一物理翻转init10：两批完整initial_snapshot、before_first_snapshot、public_before、private_before逐字段完全相同，初始快照canonical SHA `1089af110f2dd2e61395150526e60865679e0fba49c763428324fc1b5d6ed05b`。首个π0.5动作块已经不同，160/160块原始action序列不同：首动作x分量4235=0.3751395，4241=0.2769735。4235原生成功累计473个controls，4241为0；after关节4235约−0.159873m，4241为0。两批均执行相同类型的 `release_fixture_and_restore_view` 后恢复，但恢复waypoint依据各自末端位置而不同，差异不是恢复之后才出现。

源日志没有逐块关节真值或π0.5策略RNG状态，不能锁定startup随机性，也不能把physical翻转归因于moving-plane绑定。当前严格能证明：同一测得起点、同字面指令、同预算，策略动作不是同一前缀。原失败保留，下一轮方法选择应记录策略seed/RNG与原始推理输入，独立确认仍必需。

统计脚本在本机和远端解释器实际运行，audit SHA完全一致。原报告、原始判定与所有完成回合均未修改；raw ledger和source-produced扩展诊断双端保留，未进Git。无新增GPU作业、物理回放或训练行。
