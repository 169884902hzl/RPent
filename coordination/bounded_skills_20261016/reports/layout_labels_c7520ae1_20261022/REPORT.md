20个新增资产扰动世界的CPU构造和输入校验已经闭合；策略小试尚未闭合。
新增世界初始化和完整轨迹采集已接通，精确快照CPU778项通过。
固定10状态加新增世界π调用面板11396已闭合0:0，11项均真实控制。
原资产重复类型覆盖问题已修复；旧失败和歧义取消记录全部保留。
20状态π小试11397已启动；真实前缀采集11398等待D2作业11335完成。本轮没有训练。

| 项目 | 已核事实 |
|---|---|
| 生成源树 | 8a0f380a2403293be5423d596b3554427c3c0c9e |
| 采集运行树 | c7520ae1219e4b67549b418b9438b271109dd49a |
| 运行归档SHA256 | 26abd8a4aef9a43767fe69a42a23cd84f6e2f62250121c9f2c008027b7cb4cce |
| 新布局 | 20，11020600–11020619，原版train父任务 |
| CPU有效性 | 原谓词见证20/20、无穿插20/20、源指令身份一致20/20 |
| 永久隔离 | 确认种子和几何继续排除；XY/body-origin距离≥5cm；不使用PRO/MAX/D2 |
| 额外资产 | 只选非任务目标类型，原任务句/目标字节不变 |
| 新世界身份 | 模型变化后按名称迁移状态，再捕获新完整physics；不称与原模型同完整初态 |
| CPU快照面板 | 778通过；后续实测manifest工具聚焦8通过 |
| GPU面板 | 11396完成0:0；10个固定状态真实控制，新增世界527controls/104推理；该任务失败保留 |
| π小试/实测标签 | 尚未完成；CPU构造和prefix捕获不充当方法标签 |

原件根：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/layout_runtime_c7520ae1`。
世界根：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/layout20_assets_unambiguous_8a0f380a`。

旧资产批11339/11340有5个失败，原件不改。LIBERO parser对重复typed声明覆盖已有实例；da5abe22改为合并原typed group。修复后同输入6/7完成；2/3/19添加同款Soup后原指令不能唯一绑定，已知循环取消，不能记成功。新20个recipe根据原任务目标类型确定干扰物，未依据新π结果筛选。

实测manifest工具以每个真实前缀的physics、annotation、checkpoint及构造报告SHA绑定。每状态自有2次，in_place/initial_pose/full_task各3次。原版train parent仅保留split lineage；实际分叉初态来自新世界捕获。没有测到的分支保持unknown。
