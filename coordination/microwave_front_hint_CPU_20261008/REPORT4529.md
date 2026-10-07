# 4529：关门物理成功，公开门面跟踪仍缺测

本回合是已访问过的原版 LIBERO-90 task33/init0 开发诊断，不是确认批，不进训练。
`4529 COMPLETED 0:0`，Slurm 用时 5:58，回合墙钟 352.554 秒。
同一 immutable 快照、同一 launcher 真实执行 40 块、200 controls；原始记录的启动合同通过。

| 指标 | 结果 |
|---|---:|
| 真实接触 controls | 200/200 |
| 公开捕获帧 | 42 |
| 独立固定面与门面均可测帧 | 37/42 |
| 腕部完整双面、无遮挡 | 0/42 |
| 公开近终点候选 / 撤离 / stop | 0 / 0 / 0 |
| 误 stop / 成功后回退 | 0 / 0 |
| 最终 articulate 回执 | unmeasured，articulate_verified=null |

私有事后标签：第37块首次 close=true，第37–40块和最终 release/retreat 后都保持 true，
最终关节值约 4.64e-39。这些标签没有参与查询、撤离或控停。
物理成功不能抵消公开缺测，也不授予时序验证器资格。

43次 shell-front 查询记录中，37次腕部固定patch缺测、2次主视角当前正面候选缺失或不唯一，
4次生成实际SAM查询点。第37/38块裁剪SAM有独立mask，但仅选择狭窄部件，原宽度检查拒绝：
`moving_panel_width_not_measured`。第39/40块SAM未命中。
保存的第37块RGB可直接看到查询ROI落在门把手区域，点位在把手上。

随后只用同批公开保存帧试了4帧×5种查询：3个高度分位点、`door`和`microwave door`文本。
20/20均未通过原门面检查。文本查询全缺测；点查询选窄部件或无法支持完整主平面。
所有5cm宽度、0.55面占比、8mm残差、独立mask和机器人遮挡检查保持原值。
停止继续对同帧做词/点微调，下一条路径是已测开门面的RGB-D多帧身份跟踪。

运行输入：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_front_hint_CPU_20261008/r1/close_front_hint40.json`，
SHA256 `9490111c7e3d8930f92ad44e2d84174ad393a182ccdbd73e931919a40f536ef9`。
快照：`/public/home/sunyihan/rpent_libero_eval/source_v5_microwave_front_hint_20261008`，
source identity SHA256 `33613a51662cddad39d1964c9ad1bc3689951e2c8ae3c7c8cd50e042b46166e4`。
原始结果目录：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_front_hint_original_20261008/close40`。

逐次记录、公开/私有分开的汇总和输入哈希见本目录 `manifest.json`、`records.json.gz`、
`diagnosis.json`、`public4529_inputs.json`、`saved4529_SAM_variants.json`。
首块动作与之前几版不同，尚无π0.5输入张量/噪声哈希，不能将物理差异归因于单项查询改动。
