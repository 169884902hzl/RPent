# 盘子方向接触：实现与验证

1. 9534_160 的公开源和目标绑定正确；默认接触点位于盘子 +y 边，随后 +y 推移离开盘沿。它缺少方向接触选项，并非没有碰到盘子。
2. 薄水平表面的 front / left / right 从测量点云生成，沿用完整闭合、路线碰撞和 IK 筛选；默认 above 不变，不用任务目标筛公共候选。
3. 选中的接触点在实际执行和前缀预测中保持一致；私有 oracle 按推移反侧选现有方案，judge 升至 /12，公共 schema3 / legal2 不变。
4. 原状态 CPU 几何对照有可筛选的三个方向；265 项 CPU 回归通过，补充异步前缀后的 41 项受影响回归通过。尚不代表物理成功。
5. Codex3 完成回归、部署和真实启动后复验；Codex1 / Codex2 按源码和 judge 版本核对标签。

旧物理记录：9534_160，false，31 决策、2863 tick、2526.713 秒，contact_failure，源码 5249d5d。原件保留。私有接触诊断显示确有水平与上表面接触，不能称为“全程未接触”。公开绑定 plate e99、front-of-stove e6，来源见 `reports/plate9534_public_goal_binding_CPU_20261018.json`。

同一保存状态的几何诊断 `reports/plate9534_directional_contact_CPU_20261018.json`：默认接触点 [0.0550, 0.0347, 0.91817]；front [0.1145, -0.0350, 0.91642]，3.563 秒；left [0.0942, -0.0772, 0.91542]，1.353 秒；right [0.0550, 0.0347, 0.91817]，0.450 秒。三者均保留原闭合、路线和 IK 检查；该诊断先于生产实现、无物理步进，不冒充生产回放。

回归覆盖选 left 后预测和执行的 descend 保持同一接触点、live adapter 不被预测改写；私有 push 选择反侧且 acceptable 排除离开盘沿的一侧。旧两项表面筛选测试原先把最后一次筛选当作默认选点，新增方向分支后这个索引假设不成立；现针对默认首次可行方案保留原碰撞及对称手腕检查，没有把额外分支最后一次的结果混入默认断言。

首次完整回归为 `test_bounded_skills.py`、`test_bounded_chunk.py`、`test_bounded_offline_labels.py`，265 passed / 205.70 秒。之后检查发现执行中前缀走 commanded_endpoint 分支时也必须保留所选接触侧，已一并修复并增加该情形；受影响 chunk/offline 测试重跑 41 passed / 63.07 秒。receipt 与源码 SHA 在 `reports/directional_contact_cpu_20261018.json`，完整后一次日志在同名 `.log.gz`。唯一 warning 是本地未安装 pytest-timeout 导致未知 timeout 配置，没有测试失败。

旧源码的第二状态 9534_161 同样失败：6 决策、408 tick、346.911 秒，verification_error；与 9534_160 分开保留，不根据已观察结果换状态。
