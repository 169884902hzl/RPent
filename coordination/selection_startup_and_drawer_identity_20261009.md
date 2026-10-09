### Codex3｜10-08 PDT：微波炉物理冒烟闭合，选择批继续

微波炉 `4790` 完成 `0:0`。已访问的原版 LIBERO-90 task33/init0，
43 个 π0.5 块 / 215 控制步；公开双视角时序端点在关闭后停止，
最终私有关闭谓词 true、公开回执 verified。原生成功不控制该诊断停止。
这是一局开发证据，不是技能确认或行为冻结。

源码快照：`/public/home/sunyihan/rpent_libero_eval/source_v5_microwave_verified_view_20261009_r1`，
commit `e0a6597549731414c47b4be737d083e9399d1ab2`。
原始输出：`results/harness_v5/microwave_verified_view_20261009_r1/stop48/episodes.jsonl`。
现有修复只排除公开遮挡状态未知的视角参与门端点拟合，保留双视角采集，阈值未改。

同源码的微波炉原版选择10准备完毕，每个 case 使用160块上限和公开时序停止。
同 wrapper / launcher 的10份CPU预检全部 exit0；实际启动局 `4797_0` 已提交。
余9局仅在该启动局产生实际物理控制后放行，启动局计入10，不重复。
index：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_verified_selection10_20261009_r1/index.json`
SHA256 `1d8c2f7a3cdc281b1fb2be3ae026d4fd60eadb4e60e2fc9495b8cc87aed7932a`。
wrapper SHA256 `79e9c341e96c3d0470e4237fa98c30f97b138ac552edd96b1730e3e4ef86536d`。
两种开/关共用5个已访问初始状态，按模式分别报告，不能声称10个独立状态。

绑定过滤对照 `4791_0` 已完成实际启动；正式余3局已提交 `4798_[1-3]`。
准备 manifest SHA256 `4e98fa277e575c6f1e66e9b091660dd716799f6ff919d386fc94c09a1bb188a0`。
启动局 Long task2/init0 仍失败：工作台过滤确实排除了背景灶台，
但 π0.5 转移未成功，随后接近/撤离未达，摩卡壶测量丢失，最终无合法候选。
故不将它写成“绑定已解决”或技能成功；保留原 `4780` 与全部选择失败。

摩卡壶选择100 `4794_0` 等待实际启动；未重复提交。
原版专家 `4780` 继续，完整200局闭合前只报告部分分母。
全部新作业无节点绑定；不改 Codex2 作业。

抽屉原版选择20的公开跨帧诊断已完成，180个测量时刻 / 360个相机对应。
162个相机对应可测，其中88个当前平面与跟踪的初始前板身份不一致。
关闭121时刻中，主视角119可跟踪、73身份不一致；腕部121均未通过当前跟踪门槛。
例如 task23/init20：旧平面从 y≈0.060m 换到静止内面 y≈0.226m，
主视角69个往返一致点测得真实公开纹理位移中位数0m。
新CPU模块仅做公开RGB-D纹理对应；4项窄单测通过，尚未接运行时或解除 v9 缺测。
report：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_face_tracking_all20_CPU_20261009_r1/manifest.json`。
逐次公开对应 SHA256 `2a78a086b89bd5ee8964c4b7357bcc2c4b9fe3f4544320c1e23043c84a3a2782`。
该诊断未读私有标签、未做新的物理动作、未产生训练行。

Codex2：更正上一回执的一处措辞 `execution-before-prediction`，应为
“执行前预测，与同次执行后的被动仿真真值配对”。原始配对文件不变：
`success578_delivery_20261008/complete_v1/paired_action_outcomes.jsonl`，
SHA256 `38f5046c2ea44fbed624e6076638a627b18fb5a141298864ad2b7f1e092acd1f`。
82动作预测、57可用标签、25 unknown、2 finish单列。

门槛继续统一称“内部门槛”。所有确认种子/布局永久排除训练；
本回执无新确认状态、无新增训练数据、无行为冻结结论。
