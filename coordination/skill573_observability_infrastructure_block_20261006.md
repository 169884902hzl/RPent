# Codex3 skill573：完成结果、公开观测缺口与node01阻塞

已读取并接受10/06本轮目标与所有门槛，不降标准。4311/4319/4327均物理完成且正式结果已交Codex1；新4335保持原5状态，不删除失败或重跑确认。没有重复提交旧链、没有节点绑定、没有启动新训练或大规模采集。

## 4335 有效完成3局，另2局基础设施阻塞

4335_0–2在node02全部COMPLETED0:0（8:33–8:34），各160公共off观测、322私有评分、6阶段标签、640 raw RGB/world引用核对有效。三局都曾到off，接触160末1/3 off，release后1/3、retreat后1/3；没有release/retreat失去off。s0 q接触−.0056287→release−.0050057→retreat−.0048807一直off；s1/s2曾off但在继续contact时丢失，非恢复阶段丢失。Wilson仅对这3有效开发局描述，不能替代注册5分母或独立确认。

4335_3/4在node01仍RUNNING，off公开记录停在8/9、私有9/10块，mtime几乎同刻停止并持续超过10分钟。保留全部已执行前缀，未作物理成功/失败判定、未补造endpoint、未重跑；也未取消/重提。2/5注册局疑似受同一节点基础设施阻塞，超过用户“基础设施故障率>2%先修”处理线，先停止新增GPU提交定位基础设施，不把故障当模型成绩。

原先hostname/GPU查询超时发生在SSH认证之前，不能据此认定GPU driver坏。独立TCP/banner两节点均约9ms正常；node01 SSH kex/service_accept完成，但停在offer public key后、未Authenticated/未Sending command，15秒超时。node02相同参数认证+hostname0.868秒成功。controller仍报node01 MIXED，CPU load有更新。现有证据指向node01认证/PAM或用户home/authorized_keys文件访问路径；仍需节点侧核查，未擅自修改共享认证/NFS、reset GPU或重启节点。正常命令尚无法进入node01，当前无法从会话内定位或修复其节点侧服务。

明确交Codex1/Codex2：请节点维护侧恢复node01认证/文件访问链，恢复后核对原两片是否继续；必要时仅按基础设施补跑协议保留前缀、另建attempt1。不可覆盖原记录。节点恢复前不通过ReqNodeList/ExcNodeList绕过当前规则。

4335中间包 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove568_monitor_CPU_20261006/interim_4335_first3/manifest.json SHA256 3d0a7fd3c2585accf3d57156642bacad165875e9a188b3e30db9407c20e2dc7b；commit f66331a826e244724d5b5e34e3f65bc67b63077d。节点诊断 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove568_monitor_CPU_20261006/node_access_diagnosis_4335/manifest.json SHA256 c5e383d6e3b80cef91699811fdefcf5e10cbe313b968fded6c8fdf37b97500b8；commit44c75d0d73fbfa514d43184502ab518a3afdcb39。脱敏日志不含key material。

## 抽屉观测与动力证据

同一t22/s20在4319的chunk30 strict真q=+.027160mm、chunk35 strict假q=−.113161mm，public signed完全相同+.244140625mm且稳定门通过。单scalar阈值不可能区分这两帧，不通过改阈值冒称修复。原200 close100仅31可测/69null（24TP/7TN/0FP），且同10close状态仅2可测/8null，旧校准覆盖很窄；新callback帧不能当独立样本。4319 75帧28可测47null（16TP/8TN/4FP）；4327 121帧46可测75null（14TP/23TN/7FP/2FN）。close门槛尚未通过。

两次release丢端点之前jaw已80.871/82.840mm张开，40个零EEF/open控制步推进2秒，EEF端点漂移1.057/3.507mm；支持持续接触动力/松弛假设，缺逐步接触力记录，不能定唯一机制。公开state不加入这些私有标签。

观测分析 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer4319_4327_close_observability_CPU_20261006/close_observability_report.json SHA256 ee4f49b895fcefe48c5a3b9daac74def4719ddcd5345f71c2f20772f635edb8f；commit ab9d614。

## 微波炉已CPU-ready，尚未提交

原4178完整open5/close5（5唯一原状态）保留。唯一当前visible microwave父实体+原版open/close句，current160不要求先测handle；门plane严格验证不变，缺测仍null。12测试+compile/bash-n/diff通过，24SOURCE571文件逐字节SHA一致，真正/tmp五分片preflight全0。新GPU job尚无：等待基础设施恢复后登记实际号，不提前填号。

handoff /public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_public_parent_CPU_20261006/handoff.md；SOURCE571 commit5da67d19fe8dde8564e06c39266bb1fedc330d2a；archive SHA256 41afc849c146eae7db2220960d2057da95c03fba23465b15fa61d0caa7bed718；manifest SHA256 f9a8b3532b169c0cf93e3d78445e11e96c8beeb343ec36b76ad96c491b9a2296；adapter SHA256 fb648b99d3fb3304619fc805a656e77ed3a4912d740b1787626f53c8dc05e599；launcher SHA256 ec3fc05c4d0c31b4b3090043efaebe2360fba94f2bf3bc2f6af56794bd61cd6f；preflight SHA256 62e7fda52a29a57b8aa5f1fbe795e714f4ebfb15c090e252ad0422998b875a6c。准备commit bafdf40。完整拟提交命令在handoff，无节点或依赖绑定。

## 后续门槛和采集依赖

摩卡壶五种真正不同方法已报告：reset短63/100、中心短40/100、handle短17/66首次物理+34未测handle零物理、中心完整在执行中持物41/100、handle完整31/100。各50官方状态重复2次选择，不能作独立确认；全部低于90%。原确认60/100未过门槛；新macro On95/100是转移子目标，不能替代持续夹持。原始证据表和index e411a54a…保持不变。

全技能独立确认、专家≥190/200、三模型旧/新80与两风险消融依赖尚未解，因此不冻结、不开采新LIBERO/LIBERO90训练数据。容量估算已交Codex1：公开训练上界2593状态、专家+DAgger约5186局/135.44GPU小时；关键帧3候选×4种子保守约1870.3GPU小时总量。公开sealed排除metadata和新增确认状态需继续登记，不打开sealed内容。成功率预测先前239预测/152公共标签的AUROC .772已交Codex2，非sim-truth AUROC，不冒称真值。
