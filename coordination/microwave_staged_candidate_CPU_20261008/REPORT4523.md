# Job4523：跨实际动作块门控，开发单局

完成：Slurm COMPLETED 0:0（5m56），回合349.49s，40块×5=200个controls全部真实执行。只读诊断曾确认17块/85个controls；startup通过，无基础设施故障。

官方关门谓词第37块首次为真，随后4/4即时块末与最终release/retreat后都为真；最终关节约0。私有关节和谓词只用于事后标签，不控制执行。本局为已用原版LIBERO-90 task33/init0开发复查，不是确认批。

新门控没有产生withdraw或stop：40次只读采样中0个公开endpoint候选，0个staged候选，0次释放/移动干预，只有baseline的6个真实neutral controls。42个公开帧中37帧有独立固定面和门面；最后几帧关门后SAM漏门，导致完整时序验证无法控停。0误stop，0成功后回退。普通最终articulate回执为verified，与本局物理成功一致；该回执不是本局temporal stop资格。

腕部ROI尝试40次，仅1次当前固定面拟合，未通过无遮挡证据晋升；腕部完整双平面+无遮挡0/42。全部融合结果以agentview为主，source camera总计agentview42、wrist2（单面贡献），不声称双视角已经完整修好。

4516失败（最终关门false、第36块单候选撤离）完整保留。CPU复算证明staged规则会拒绝4516的单帧撤离；4523本局0候选所以没有实际触发staged withdraw。首块相对4497最大动作差0.185884，和其他版本也未保持完全相同的政策输入/噪声，不把这一局的物理改善归为单项因果结果。

下一项是默认关闭的shell-front ROI→SAM提示：旧备用hint只找机壳外部面，关门后进入机壳范围而缺测。保存公开帧的完整图SAM点查询选整个appliance，被原plane consensus正常拒绝。已改成测量ROI内实际RGB裁剪再SAM，掩码映射回原图、保留原独立面/plane consensus/完整时序阈值。待真实SAM保存帧验证通过，再提交独立immutable单局。

产物：`records.json.gz`、`diagnosis.json`、`manifest.json`、`live_physical_request_receipt.json`；源码和manifest见HANDOFF.md。无训练行、无冻结/技能资格主张。
