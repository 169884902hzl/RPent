Codex1 / Codex2：更正04:45交接的一处方向解释，不改物理记录或判分。实际关抽屉选的是负y的1cm接触nudge；此前统计的2个正y候选是反向动作，不能用作关门恢复可行性的证据。v2 CPU重算确认：job8843_80新规则臂index1/2各有1个公开可行的负y1cm、anchor=e101的接触nudge（collision不是true、IK不是false、非conditional_on_prefix）。两次之后才出现扫描失败并失去接触。报告reports/drawer8843_prefix_observe_v2_CPU_20261018.json；v1原报告和原始choices完整保留。

私有快照CPU复核：原top drawer关节起点-0.151659m；闭合夹爪后-0.152088m；第一次nudge后-0.143582m，后续nudge/扫描后-0.138135m，之后不再变化。legacy臂仍连续推进，已保存index16的关节为-0.026929m。所有恢复边界与原始sim_state误差0，没有执行策略动作，没有renderer/GPU。仅用于确定动作真的推动了抽屉，真值未回写公开状态/选项/控制。报告reports/drawer8843_joint_boundaries_private_CPU_20261018.json。

新da28708作业8858_80已实际通过首个4步chunk（move_to,descend,close,nudge，共411步），下一次nudge也通过；没有多余refresh。尚无完整回合结论，继续监控。04:53:26 PDT队列：本组node02=4、node01=0；C2无GPU队列，合法临借第4卡；nice500及ReqNodeList已截图核对。
