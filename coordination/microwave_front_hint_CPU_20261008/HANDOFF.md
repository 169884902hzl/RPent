# 当前机壳正面提示：默认关闭，开发单局4529

旧hint（`v5_fixture_parts.py:adjacent_panel_prompt`）显式只在机壳xy范围外找门板，所以关门后进入机壳范围的门漏测。`microwave_shell_front_hint_v1`只有在文本SAM查询、外部邻接面提示均失败时启用：从当前RGB-D独立重拟合开局已测固定patch，在其正面深度范围内找唯一全高面，取内部查询点；以实际RGB的测量ROI裁剪调用SAM，映射独立SAM掩码回完整视图。hint从不输出door成功或stop。

保存公开帧复查：12个帧/视角只读CPU定位；4508 block36/40主视角的完整图点SAM都误选整个appliance，原panel consensus正确拒绝（fraction .151/.216）。改ROI实际RGB裁剪后，两帧独立SAM与原panel consensus通过（4428/3542个真实深度面点；fraction .717/.891；残差0.121/0.160mm）。两帧只证明当前缺测路径可恢复，不授验证器资格；没有真值控制或人为造mask。腕部缺固定patch仍缺测，未强行补齐。

103项聚焦CPU测试通过。代码 `d98d0af` + `9f16edf`，CPU包 `03c7c84`。SOURCE基于4523显式643文件，新增hint模块和prep，共645文件；runtime只叠scene开关及SAM hint/crop分支，不叠live moving-target/cache改动。严格验证阈值、两帧/robotmask要求、staged gate、40×5 controls预算与launcher都保留。

## 5880物理单局

- job `4529`（父代理预约并提交，无node/dependency）。
- SOURCE `/public/home/sunyihan/rpent_libero_eval/source_v5_microwave_front_hint_20261008`
- identity `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_front_hint_CPU_20261008/r1/source_identity.json`，SHA `33613a51662cddad39d1964c9ad1bc3689951e2c8ae3c7c8cd50e042b46166e4`
- PLAN `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_front_hint_CPU_20261008/r1/close_front_hint40.json`，SHA `9490111c7e3d8930f92ad44e2d84174ad393a182ccdbd73e931919a40f536ef9`
- OUTPUT `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_front_hint_original_20261008/close40`
- 同launcher `SOURCE/coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch`，SHA `8cba334fa65b15d906b8c5cda055c5599804602d127131fd7e33c0935ad0d2bf`。
- 解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

同launcher CPU预检exit0；真实快照导入/MeasuredScene新开关constructor通过。新物理运行待报告；start前缺文件/错误必须非零，不能把CPU前检写成物理请求通过。开发状态仍为已使用原版LIBERO90 task33/init0，非确认批，不进训练。

工作量：保存帧复算及两次SAM查询已完成；一局物理检查按当前速度约6–8分钟。若候选通过而需要100局确认，按4523回合349.5s估约9.7 GPU小时/100局；独立状态和确认池按已有登记，不自行补用选择状态。必须以确认批实际精度/一致率判门槛。
