65个扰动原版train状态已完成715条实测分支，全部同状态11次的完整初态和请求SHA一致。
692条分支绑定原请求，23条保留unknown；完整包已交Codex1/Codex2共享登记，消费者39ok/13unknown/13ceiling_outside。
20状态π0.5强度小试为6/20；四个正式采集分片全部COMPLETED0:0，本轮GPU队列清空。
修复了提示变化续跑与实际候选/种子重复导致的导出错误，未重跑物理结果或补造标签。
本轮没有训练；PRO/D2/确认池均不进入训练，既有确认排除继续有效。

| 协议 | 完整结果 |
|---|---|
| 状态 | 65，9类；20初态、44中途、1公开持物 |
| 分支 | 每状态自有2次；请求in_place/initial_pose/full_task各3次；总130+585=715 |
| 完整初态和请求 | 65/65状态各11次都一致 |
| 原请求绑定 | 692/715；未绑定上下文23条不填负例 |
| unknown原因 | 14未选择初始绑定候选、6执行中提示变化、3实际候选和种子重复 |
| 消费者 | 39 ok、13 unknown、13 ceiling_outside；8状态有coverage issues |
| 作业 | 11400_0/1、11403_0/1全部COMPLETED0:0 |
| 原始布局 | 20个11020600–11020619；原版train父任务，新增非目标LIBERO资产 |
| 隔离 | 不读PRO/MAX生成；2165个已知确认几何和种子隔离，world XY/body-origin ≥5cm；本轮不训练 |

完整包：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/layout_runtime_c7520ae1/CPU_C2_measured65_r1`。
数据SHA256：`00051505a9c477b7cc8b31015e6fd3b7ce07480c8923d6ab5fef15613e2f279b`。
消费者代码SHA256：`06534f6ab1d4abaf08ecbeebc87db931c3f1da7e7ce6d4822d100b380001597b`。
[C2_delivery.json](C2_delivery.json)记录完整路径和每个产物SHA；[manifest.json](manifest.json)绑定两个不重叠来源包、策略权重和每包导出工具；[protocol_and_raw_attempts.json](protocol_and_raw_attempts.json)保留所有715条尝试的分类汇总与65个分叉不变量。

按请求变体、类别、Wilson区间见 [requested_variants_table.md](requested_variants_table.md)。按实际候选、已绑定标签统计见 [actual_bound_variants_table.md](actual_bound_variants_table.md)。二者分母不同，不把requested preparation当作实际执行，不用消费者unknown补齐。

这些是原版train任务自生成扰动的开发分支，不是确认结果、D2成功率或训练效果。成功是该分支继续执行至登记子目标或预算的结果，不能冒充首次原子动作成功；full_task按未改的native结束评分。每状态多次尝试相关，Wilson仅为尝试层描述，不证明独立布局泛化率。

20状态π0.5整句小试11397成功6/20（30%，Wilson95 [14.55%,51.90%]）。分类：碗0/3、盒0/3、容器0/2、杯0/2、开抽屉2/2、关抽屉1/2、开微波炉2/2、关微波炉1/2、推盘子0/2。处于用户20%–80%强度检查区间；未根据本批结果重挑布局。

精确物理运行树：`c7520ae1219e4b67549b418b9438b271109dd49a`，归档SHA256 `26abd8a4aef9a43767fe69a42a23cd84f6e2f62250121c9f2c008027b7cb4cce`。执行/碰撞/oracle/chunk与N1达标9d00ee63逐blob相同。新增世界初始化、完整prefix轨迹采集面板CPU778通过；fixed10+新增世界π11396共11项真实控制、退出0:0。实际measured launcher启动11399_0和11402_0均1次推理/1控制后退出0:0。后续导出工具修改没有混进物理运行源。

额外资产旧批typed-group覆盖失败5条保留：da5abe22改为合并原typed group。同输入2例完成，3例添加同款Soup后原指令歧义，已取消已知循环，不称通过。新20个recipe按原目标类型选非目标干扰物；CPU谓词见证、无穿插、源身份一致均20/20。native作者侧见证不等于π策略成功。

edc0d36d将提示变化续跑标unknown；eb801e07将相同实际候选/种子的重复物理尝试标unknown，原始11条尝试仍全留。没有删失败、放宽私有判据或借旧状态标签。完整包以record_id替代第一包预览和30状态分包，不把它们再次追加成95状态。

资源监控曾用isdigit拒绝数组任务号，9d35620e修复并通过3项测试；重启后连续squeue正常，最近两小时账本无C2 GPU需求。最终watch记录c3_running=[]、done=true；没有伪称做过真实取消。本轮没有触碰其他项目和旧held任务。

交付回执：[shared_delivery_receipt.json](shared_delivery_receipt.json)。共享登记为fcntl锁定追加，未整读大文件。
