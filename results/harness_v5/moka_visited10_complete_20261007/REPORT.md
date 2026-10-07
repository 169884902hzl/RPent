# 摩卡壶 visited10 开发 smoke 完整结果

十个预登记原版状态均已产生真实物理请求；每局执行 320 个动作块、1,600 个 controls。末态官方物理成功 **3/10**，曾到达成功状态 **9/10**，曾成功后又退回 **6/10**。公开放置验证为 **2 true / 3 false / 5 null**。

本表混用 SOURCE571、r5、r6 的首次有效物理记录，状态此前用于开发选择，**不是独立确认批，不判冻结门槛**。所有原始失败和物理记录保留；未用重跑覆盖首次物理尝试。

| init | 首次物理作业 | controls 请求/执行 | 原生成功 controls | 私有末态 done | 公开放置 | 曾成功后退回 |
|---:|---|---:|---:|---|---|---|
| 0 | 4425_0 | 1600/1600 | 1447 | true | null | 否 |
| 1 | 4430_0 | 1600/1600 | 577 | false | null | 是 |
| 2 | 4440_0 | 1600/1600 | 1455 | true | true | 否 |
| 3 | 4378_3 | 1600/1600 | 174 | false | false | 是 |
| 4 | 4430_2 | 1600/1600 | 921 | false | null | 是 |
| 5 | 4430_3 | 1600/1600 | 142 | false | null | 是 |
| 6 | 4430_4 | 1600/1600 | 924 | false | null | 是 |
| 7 | 4430_5 | 1600/1600 | 0 | false | false | 否 |
| 8 | 4430_6 | 1600/1600 | 1472 | true | true | 否 |
| 9 | 4430_7 | 1600/1600 | 804 | false | false | 是 |

三项 Wilson 95% 区间仅作开发描述：
- 末态物理成功 3/10：10.8%–60.3%。
- 曾到达成功状态 9/10：59.6%–98.2%。
- 曾成功后退回 6/10：31.3%–83.2%。

总计请求/执行均为 16,000 controls；原生成功 controls 共 7,916。所有有效试次的 external_truncation、native_success_stops_chunk、private_joint_or_predicate_used_for_control 均为 false。原生成功 controls 只用于私有诊断；它没有控制技能停止。

公开 null 的直接原因是 `two_frame_evidence_missing`。init1/4/5/6 的两帧都是开局缓存：`visible=false`、`src=perception_cached`、`source_step=0`；夹爪已张开且帧间隔充足。init0 在重新松开前有新鲜测量，松开后 `fresh_after_release=false`，两帧也变成缓存。遮挡、物体出视野或实例关联丢失仍需图像诊断，不能仅从 null 确定原因。

启动与失败记录：

- 4369 实际启动的 part0–3 因 `ModuleNotFoundError("No module named 'typed_choice_eval'")` 退出 1，0 物理。sacct 保留未启动取消片，不写成全部 8 片执行失败。
- 4378 因 finally 对 SOURCE571 根目录缺失 `typed_choice_eval.py` 的 hash 读取而退出 1。part3 已真实执行 1,600 controls，私有末态 false、公开 false，按首次物理失败保留；其余零物理故障保留且不计模型成绩。
- 4430 part1/init2 在公共重复灶台歧义下未执行物理；随后 launcher 对 case 字典做 join，又出现 `TypeError: sequence item 0: expected str instance, dict found`。原零物理记录保留。r6 只合并公开重叠框并修正诊断打印，4440 完成 init2 的首次物理尝试。

4440 为 `COMPLETED 0:0`，同快照/launcher 单局启动合同 `pass`；启动合同证明物理调用可执行，不等同任务技能确认。

- 合同：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/startup_preflight/4440/probe/contract.json`
- 合同 SHA-256：`302457438f8d94084940038a806dc0a01ace9c828019a445eb7df53e71f116f2`
- 明确十状态 manifest：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/preparation/repair_r6/moka_visited10.json`
- manifest SHA-256：`2fdc12748f9374f3148e4a4cb2f6145caf3de20dc1f91085449314df9f7d04de`

逐 case 的完整 server_chunk_execution、state SHA、ledger SHA、回执与测量摘要、源码 hash 路径均在 `report.json`；显式输入和源码索引均在 `manifest.json`。
