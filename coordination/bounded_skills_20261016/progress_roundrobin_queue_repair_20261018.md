# 待排索引误取消及补回

1. 本轮取消时用错清单顺序，误取消 9248 的 31 个未启动分片；没有运行中作业或物理结果丢失。
2. 已按所属 submission 的 hash 固定原清单，逐个恢复真实 case 登记，原 ec89f74 快照、状态、预算均不变。
3. 补回数组同快照同 launcher 的启动检查 9542_120 已 COMPLETED 0:0，并有真实物理请求；正式补回数组 9544 已通过该证明后提交。尚不能报告补回的物理终态。
4. 原错误取消原件、逐项身份更正和后续补回记录全部保留；这些取消不算物理失败，也不当独立重复。
5. Codex3 继续完成门控和补回；Codex1 核对原、补回分母。监控只延后普通待排替补，不改运行中、保护或旧 held 作业。

9248 的真源是 `reports/original20_support_roundrobin_20261018_full_submission.json`，manifest SHA256 为 `4adcaba891379c4e4f50e911c97953156caeaa03926ca73d61236800fe2b7033`。误用的是顺序排列的 oblique 清单。例如 9248_120 实际是 stove_on/init10，不能从另一清单的索引120推定为 microwave_close/init0。

`reports/microwave9248_known_failure_pending_cancel_20261018.json` 是保留的错误原件，其标签被 `reports/roundrobin_cancel_identity_correction_20261018.json` 明确更正。`repair_roundrobin_cancel_20261018.py` 从原 submission 读取 manifest 并验证 SHA，输出31项实际 case；提交时还用 `--expected-case-names` 逐项比对。对9248所属清单重新检查后，实际微波炉待排分片为0（早先已取消），因此没有进一步取消。

汇总器增加同源补回 receipt 支持：source_commit、snapshot、manifest 必须完全相同，索引必须属于原登记池；同一状态若出现两个物理终态则报错，不取最好结果。缺失、取消和补回分别保留路径。

资源控制器另修待排优先级：原代码只在 startup 等卡时延后 peer，新完整复验也可能被旧数组的新替补饿住。现优先数组仍有待排项时，延后其他普通待排替补；全部优先任务已运行后允许剩余卡继续工作。没有取消任何运行中作业。两脚本 CPU 编译通过；资源变化及物理门控仍以实时 Slurm / receipt 为准。

补回 receipt：`reports/original20_roundrobin_cancel_repair_20261018_full_submission.json`。唯一监控的 peer 列表已加入此 tag；补回替补同样受 Codex2 返回时至多三卡的总量规则约束。旧监控 PID2490419 已退出，替换后没有第二个资源控制器。
