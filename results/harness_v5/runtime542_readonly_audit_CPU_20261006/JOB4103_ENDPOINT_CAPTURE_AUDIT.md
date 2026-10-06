# Job4103 原版末态缺测：公共证据与最小修复

原版 10 局、46 个决策中，5 次回执为 unmeasured。所有这些时刻都产生了新 capture，并执行了选中物体的类别查询；同类别没有转移到新 ID。因此不能把缺测归因于未 capture、未查询，或距离阈值导致身份关联拒绝。SOURCE544 的 nearest 配对本身没有距离拒绝阈值。

所有五局未开启 record_sam_masks_v6。旧 SAM 原始 reply、候选 mask 和候选剔除计数没有保存。measurement_history 的 entities 是关联后的结果，perception_measurement_evidence 中的旧 evidence 也不能证明末态 SAM 仍检测到物体。以下原因不会被写成已证实的零召回。

| 回合 / choices 行 | 已证实的公共事实 | 能确认的原因边界 |
| --- | --- | --- |
| spatial t2 seed0 / 5 | plate 查询在 frame5/6 执行；旧位姿 agentview 深度支持从12,424降到44点，腕部支持为0；末态图像夹爪覆盖原 plate/bowl 区域 | 明显遮挡，不能用旧位姿验证末态；无法再分 SAM 零候选、过滤或错类别 |
| libero_10 t1 seed0 / 2 | butter 查询在frame4/5执行，含腕部查询；旧位姿两视角深度支持均为0；basket 当前可见 | 物体已经离开旧位姿；不证明是否进入basket或检测被placement筛掉 |
| goal t0 seed0 / 1 | cabinet/drawer 查询frame1执行；cabinet旧AABB仍有112,818个agentview支持点，drawer新实体e66可见；柜体旧ID变不可见 | v1未得到新的cabinet类别测量；新drawer测量并未供v1端点判定。该局未启v2，不是新端点验证器的质量样本 |
| libero_10 t0 seed0 / 1 | alphabet soup 查询frame1/2执行；旧位姿两视角支持为0，basket当前可见 | 已离开旧位置；精确SAM候选缺失，无法分漏检与关联前过滤 |
| object t1 seed0 / 2 | cream cheese 查询frame4/5执行，含腕部查询；旧位姿两视角支持为0，basket当前可见 | 已离开旧位置；官方物理成功另记，不能用它补视觉证据 |

放置/宏动作的两帧间隔是3.34–4.23秒，不是间隔不足。旧缓存不得补成当前可见测量，5条原回执和所有物理结果保持原样。

## 可复现的代码缺陷

SOURCE544 robots/libero/v5_runtime.py:569–575 在身份关联之前，删除目标xy包围盒外的所有测量；有两个目标内候选时也全部删除。独立脚本直接抽取并执行旧源码 AST，得到：唯一目标外候选1→0、两个目标内候选2→0、唯一目标内候选1→1。这个代码路径会把可见错放变成缺测，削弱恢复信息；由于旧候选未保存，不能声称它造成了上述五次中的某一次。

最小修复只改 MeasuredScene.refresh 的 placement 关联段：唯一场景类别且唯一新测量保留，即使目标不可见或物体在目标外；多同类或多候选均保持未知。辅助类别（例如用于排除的pan）恢复正常类别配对。目标满足与否仅交给物理/视觉放置验证器，不供身份判定。未修改place/execute_subtask，未更改查询或schema。

已知独立限制：can 的 placement 查询仍是泛类 top of a can，会跨类别产生歧义。该查询本轮未改，需新smoke原始mask证据后定位，不再用目标位置挑中某个罐盖。

CPU 验证：test_v5_placement_measurement_identity.py、test_v5_moka_scene_ladder.py、test_v5_runtime.py 共161 passed。这不是物理技能通过结果；根代理将修复合入新快照并做物理smoke。

产物：

- job4103_original_unmeasured_capture_evidence_CPU.json：d0ade569baf16c89de1afa27c5e58e2f445c0244fb3dc9386e5eea791d23f2ea。
- job4103_original_unmeasured_public_views.png：见JSON逐文件SHA与注册frame；粉色/青色框仅是旧物体/旧目标测量的投影，不代表当前语义检测。
- audit_job4103_missing_endpoints_CPU.py：只读显式旧report、choices、states注册capture及measurement_history；无模型调用或物理重放。
