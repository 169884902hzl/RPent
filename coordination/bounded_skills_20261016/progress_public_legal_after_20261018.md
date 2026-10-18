已提供唯一公开合法集合函数 rpent.skill_package.contract.legal_after(request, prefix)，LEGALITY_VERSION=public-request-legal/1。只读取冻结请求，按原顺序排除重复ID、已承诺ID/身份，以及K和静态交接边界；不调用规划器，不用任务真值，不以预测碰撞/IK筛选legal。预测后果仍在执行前重新计算并检查。oracle每位置legal及selected校验都调用它，private evidence保存selected/acceptable越界计数，越界拒绝；validate_labels要求legal与函数输出逐项相同。judge升至libero-private-task-progress-rules/5；wire字段形状不变，schema仍bounded-skills/3，旧预测路径legal标签需重生，不能混用。

256项CPU测试通过（164.27秒）。Codex2当前bridge已直接委托本函数，8候选目录的309个可达前缀顺序完全一致（含已承诺动作重新编号）。首轮测试fixture误用pytest保留名，已修复重跑，错误日志保留。没有训练或新的物理成绩。

源码SHA256：{"rpent/skill_package/contract.py": "634b1358cfb3c0bcd468349dc687d99d77cb0430f65b786f120fa3a076159f57", "rpent/skill_package/schema.json": "27ec48d6e8a372be665741806813fc807caf09aa348111f32b490bb40106f564", "robots/libero/bounded_oracle.py": "10e82d4a20fa7cf8871a9d5200b58e24750091e4a6b8b3ce560b1744bfd72a81"}
