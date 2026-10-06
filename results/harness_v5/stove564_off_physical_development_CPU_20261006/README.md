# stove564：原版 turn_off 物理失败诊断与 20-cell 开发方案

旧 4210 的 10 次 off 均执行完整 160 块 × 5 controls，prompt 确实是
`turn off the stove`，没有预算缩短、外部截断或启动错误，但真值 true_off
仍为 0/10、true_on 为 10/10。这是执行失败，不能归到验证器。

接触段关节变化范围 −0.50980 到 +0.13494 rad；恢复段最大变化 0.04546 rad。
描述性分组（|delta|≤0.01 rad 仅用于分析）：4 次几乎不变、5 次部分回转、
1 次反向转动。末 20 块末端范围多数约 1–3 cm，但这不能证明真正接触开关，
也不能区分中途反转和停滞。6 个有公开候选接触点的 case 中，末端最近距离
约 2.2–7.6 cm；这是末端到候选表面的距离，包含末端/指尖偏移，不能当作
接触误差或据此设置控制门槛。

关键数据缺口：160 个 `vla_act_chunk` 只保存 prompt、动作、末端位置、
夹爪和原生终止信息，没有逐块灶台关节或接触真值。q 仅在原有捕获时刻
评分。不能补造逐块 q 或声称已知道全部物理机制。详见
`existing4210_off_trace_report.json`，20 份显式 phase 文件 SHA 在同名
`input_manifest.json` 中。

20-cell 方案固定为原版 Goal7 init0–4 × 四个条件；这是 **5 个原版状态的
20 次配对开发试验**，不声称 20 个独立状态或确认批：

| 条件 | off prompt | 公开精修 |
|---|---|---|
| literal_off | turn off the stove | 无 |
| paraphrase_off | switch off the stove | 无 |
| complete_knob_off | turn the stove knob all the way to the off position | 无 |
| measured_complete_knob_off | 与 complete_knob_off 相同 | 已有测量把手接近/腕部精修 |

全部使用固定 on setup `turn on the stove`，每个 on/off 都保持 160×5。
on setup 失败也继续固定 off，并保留原始终点标签，不按成功筛样本。
精修只读取当前 RGB-D/公开控制几何，使用现有 0.15m 接近间距；量不到就
保存 `refinement_unmeasured`，仍跑预先规定的完整 off prompt，不走私有 fallback。
完整 prompt 与同 prompt + 精修可做配对比较；不同时改预算。

这几个 off 变体是开发者撰写的通用指令，未读 PRO、人工或 sealed 文本。
已核对的原 40 任务 catalog 只有 Goal7 `turn on the stove` 和 Long2
`turn on the stove and put the moka pot on it`，没有 off 原句；这不能证明
π0.5 的全部训练数据没有 off，不把新变体称作官方任务原句。

下一次 probe 需在每个已执行五动作块后，把 on/off q 与谓词保存到独立
`labels_chunk.jsonl`。私有评分不得返回给控制器，不得改变动作、停止或绑定。
终点仍同时保存接触后和 release/retreat 后的 on/off 私有评分。

预期只需 owned 扩展：`StoveProbeFacade.chunk_step` 后置评分写入；owned
`run_phases` 读取 manifest 的固定 prompt、调用现有 `stage_fixture_handle`。
不需要修改 shared `v5_runtime.py` 或 verification 函数。

旧设计阶段 **方案/schema/source 身份 CPU 预检已通过，物理 launcher 当时尚未实现**。
`GPU_submission_ready=false`，没有提交 GPU 或启动仿真；不能把这份设计当
已验证执行器。原版状态、资产身份、源码 SHA、预算、输出根目录和评分隔离
均在 `off20_development_plan.json` 中显式登记。

manifest SHA256：
`64812b7a0f07488c2e9a52105f10ca1e91632360f17628055c89f6197fe66516`。
实际远端 `/tmp` preflight 输出：`plan_preflight_from_tmp.json`。
计划输出根目录：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove564_off20_original_20261006`。

本包只保存原版诊断与开发设计；不 push、写 COORDINATION 或修改已有作业。

## 已实施的独立 off20 探针

新 off20_probe_manifest.json 的实施版已可提交，SHA256 `a82da4b18a83db73b9cb26458ba9aceed8b5729f1092d3467baf6d0f496184e2`。真实远端 `/tmp` launcher八分片全部通过（20个cell状态SHA），两端3项评分隔离回归通过。详情与完整提交命令见 physical_ready_handoff.md/.json。旧设计manifest及旧预检结论保留，未提交GPU，不把CPU通过当作物理执行通过。
