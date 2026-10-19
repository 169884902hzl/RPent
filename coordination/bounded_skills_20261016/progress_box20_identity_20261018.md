# 真实盒子：持物身份配对复验

1. 旧 9515_12 的失败是持物 ID 与另一块同名分割区域错配；保存公开掩码重放用生产 4db4ea4 已纠正，尚不能代替物理结果。
2. 前后都发布当前 RGB-D 实例坐标，仅关联排名使用公开 EEF 运动变换后的历史表面；没有用预测坐标填缺测。
3. 新快照已按原盒子 20 状态清单通过 CPU 预检；同快照、同 launcher 的启动 9578_12 已 COMPLETED 0:0，实际执行 193 tick 后放行正式数组 9579。
4. 20 状态为 seed0–13、31–36，保留永久确认排除；索引14实际是 seed31，不能称 init14。原版220状态清单的索引12则是碗，不拿它代替盒子。
5. Codex3 接着做物理配对；Codex1 核对状态身份与分母。未训练、未冻结，全部开发失败保留。

9515_12：旧源 ee42501，false，7 决策、367 tick、364.835 秒。第一次 lift 测得抬高9.83cm，bounds gap=0；carry 后同 ID e35 落在桌面区域，bounds gap=29.93cm，因此触发 public_hold_lost。当前夹爪附近的盒子却被赋予 e85。

`reports/box9515_12_association_saved_masks_CPU_20261018.json` 使用固定生产源码、保存的双视角最终掩码、深度及本体感知；零物理步、零 RPC、无私有真值输入。baseline 的 e35 位于约 [0.1581,0.0282,0.01765]m，transport_prior 的 e35 位于当前测得的 [0.01384,0.23791,0.26350]m，两个实例坐标集合完全相同，只纠正 ID 关联。它不是完整 SAM 推理重放。

快照：`/public/home/sunyihan/rpent_libero_eval/source_bounded_box_transport_identity20_20261018_4db4ea4`；代码归档 SHA `7834ff876d3946381a0af637db138bd55844ea5eda9346918e360283fe2c77d1`。清单：`results/bounded_skills/feasibility_20261017/preparation/original20_manifest_box_transport_identity20_20261018.json`，SHA `9e7c14799147f071d62e619985306b39b3587cd1447dab427da1d482a7c71c2d`。入口 `scripts.probe_bounded_feasibility:episode`，解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

启动只运行一次决策，move_to / descend / set_gripper 分别用了 131 / 47 / 15 tick，不能当完整任务成功。正式提交回执 `reports/box_transport_identity20_20261018_full_submission.json` 列出全部 20 个完整 case 和相同状态 SHA；19:35 PDT 已观察 9579_0 运行。源版本配对结果待这批完整终态，不把不同源码的单状态修复混入其分母。
