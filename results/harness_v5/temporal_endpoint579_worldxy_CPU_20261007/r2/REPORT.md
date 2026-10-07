# Temporal579 CPU 开发记录

世界 XY 网格已在固定的原版 Goal7 三训练/两验证状态上完成重编码及 CPU fitting。共有 815 行，483 条训练标签、322 条验证标签、10 条 unknown；标签文件 SHA 与 578 相同。默认停止关闭，无新增 GPU 或 Slurm 作业。

|公开编码/模型|验证 AUROC|Brier|固定 .5 的 FP/FN|固定 .5 精确率/召回率|
|---|---:|---:|---:|---:|
|原始 image crop|0.9758|0.3035|0 / 154|无正预测 / 0|
|image crop + 初始帧差分|0.9888|0.0446|2 / 13|98.60% / 91.56%|
|world XY + 初始帧差分|0.9933|0.0321|5 / 8|96.69% / 94.81%|

仅按训练行选择阈值 0.63661855；验证精确率 97.20%、召回率 90.26%。逐原始状态的首次 stop 回放却为 0/2：seed4 在 chunk16 误停，seed3 漏停。帧级提升不能当作停止资格。

已定位到可观测性缺口：seed4 chunk16 的炉圈已黑，但官方 turn_on/turn_off 都为 false，按钮处于中间档。直到 chunk19 才满足 off。相关私有关节值单独存在诊断文件，只用于解释，不进入模型特征、状态或运行时控制。不得把“退出 on”改判为“off”。

首次 CPU 启动用了早于 CLI 接线的快照，argparse exit2；原日志与源码保留。修复后 r2 的 prepare/train/summary 都 exit0。源码、实际命令、逐条 FP/FN 证据及 SHA 见 handoff.json。

验证状态已参与早停，仅两个原始状态；确认排除表完整性仍 pending。下一步需可见按钮几何、撤臂后端点时序及独立原版状态物理验证。未打开默认 stop，也未修改原判定。

开关本体可用性：5 个 before_off 状态、10 个相机视角均无有效 control_pose、directed_lever 或 reference。seed3 主视角有两个“switch handle”原始 SAM mask，但与测得炉体 XY 包围盒均不重叠，距炉体中心约 0.438/0.441 m；它们不是合格的开关 ROI。下一轮最小字段（细化控制本体双视角 RGB-D、清遮挡撤臂后的三帧、公开命令与 EEF 位移/停滞）已写入 public_control_availability.json。此次检查没有用私有 qpos/targetpos 选择 ROI。
