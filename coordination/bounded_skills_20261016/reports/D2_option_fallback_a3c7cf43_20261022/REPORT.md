D2三档40局已全部闭合，独立整局回放成功为12/40、21/40、20/40，尚未达到A1-M的28/40。
6条新增完整方法路径都独立回放，4成功、2失败；其余保留原已执行路径，所有原件不覆盖。
首绑缺失的3类状态81/81个首子任务π分支已实际推理；余79条unavailable均为公开无进展/循环终止后的目录，不是漏掉legal整句回退。
原生成功恢复后丢失在新批120回合中为0；15条采样/回放差异按逐局证据分类保留。
本批只评测，PRO/D2不进训练；65状态扰动标签还在采集，下一步由本会话闭合导出并交Codex2。

| 恢复预算 | 实际整局成功 | Wilson 95% | 采样上界（规则覆盖38） | 相对A1改善/退步 |
|---:|---:|---|---:|---:|
| 0 | 12/40 | [18.07%, 45.43%] | 18/38，另2 unknown | 4/20 |
| 1 | 21/40 | [37.50%, 67.06%] | 24/38，另2 unknown | 5/12 |
| 2 | 20/40 | [35.20%, 64.80%] | 26/38，另2 unknown | 5/13 |

逐局对照见 [paired_table.md](closed120/paired_table.md)，可核原件的JSONL见 [paired_cases.jsonl](closed120/paired_cases.jsonl)，8套件和Wilson区间见 [by_suite_table.md](closed120/by_suite_table.md)。每档未知私有子任务规则为 `libero_10_swap_t3_s40`、`libero_10_task_t3_s40`；它们仍有真实原生整局回放，计入40分母，仅采样上界unknown。三档都是独立策略采样，不能要求随恢复预算单调，不以D2选择训练阈值。

所有120个回合均有独立回放尝试记录；恢复0有4条在第0步被执行层或候选限制拒绝，按失败保留，不称产生了物理控制：object_swap_t4、goal_swap_t4、libero_10_swap_t0、libero_10_task_t1。恢复1/2没有零步回放。114条可直接比较的完整首态digest均一致，另6条为无私有拆分规则的原生整句回放，没有伪造对应采样首态。

三项专项核对：

- 旧245条unavailable的归因和修复证据保留在 `../attached_05143337_20261022/D2_THREE_ISSUES.md`。新批三个首绑缺失任务 object_task_t3/t4、goal_swap_t4，在每档首子任务各9条π分支均真实调用，共81/81。公开绑定依然可能缺失，不把整句成功当原子抓取成功。
- 新批剩余79条unavailable的终点请求都只剩finish/ask_help，其中38条stagnant_decisions=11，41条循环检测触发；limit均为11。保存输入核验没有legal不绑定回退。最终120的79条输入与119阶段逐个endpoint SHA/状态/种子一致，避免重复反序列化。N来自原版220，未用D2调大。
- `libero_spatial_task_t1_s40`在三档独立整局均成功；新批没有“最后子任务成功但恢复后final=False”。native派生buffer修复与实际结果分开登记，旧结果不改判。
- 新批15个采样成功/实际回放失败：2 predicted_anchor_changed、4交还未保持完成、3π动作块预算、1公开抓取对v3误报、3 observe无变化消耗恢复、1π无进展停止、1后续变体不可用。逐局表见 [replay_gaps.md](closed120/replay_gaps.md)。独立回放种子与采样不同，不把所有差异归为确定性错误。

精确D2源树：`a3c7cf4338f79cb3e11af5eced1d195f8b3f34a1`；归档SHA256 `23c4d59a705daa3669788ad282ee8b724b6dc67b481a3c36944f1f662ff3f076`。执行/碰撞/oracle/chunk与达标N1树9d00ee63逐blob一致。CPU729通过；固定10+真实VLA启动11334通过。11335/11336/11337/11338和新增路径11395均COMPLETED0:0。

完整只读指针视图：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/D2_option_fallback_a3c7cf43/CPU_closed120_selected_paths`。最优完整路径选择由保存的采样率和native成功确定，独立新种子回放；没有重复同一路径赌到成功。6条native_changed_paths6的2条失败保留。C6中断批和a3新批分母分开。

| 恢复预算 | 独立回放均值（秒） | 中位（秒） |
|---:|---:|---:|
| 0 | 147.659 | 120.238 |
| 1 | 159.113 | 97.908 |
| 2 | 177.828 | 133.086 |

以上为N8环境、从恢复初态之后开始的回放诊断耗时，包含规划/执行/私有计量，排除方法分叉采样和仿真构造。它不是严格N1端到端时延，不据此声称达到Astra 412s同协议目标。严格N1四段时延见 `../refresh_ablation_20261022/REPORT.md`（整决策104.276→30.152s，整局333.929→123.833s，≤5s目标未达）。
