# job4484 微波炉 capture8 的真实启动与测量

`COMPLETED 0:0`，实际 16 块 / 80 controls（setup close 8 块 + 首次 open 8 块）。launcher 实际生成 physical_startup_contract PASS；这证明采集/退出链跑通，不是开门技能门槛。

11 条双帧时序记录、22 帧；22/22 都有活动门平面和固定框架平面，贡献均来自 agentview，腕部视角未贡献几何。22 帧均记录 arm_withdrawn=true；遮挡证据 17 帧为 false、5 帧为 null。

开局基准最多重测三次，全部未能建立无遮挡的两帧：前两次首帧 robot mask 缺失，第三次第一帧可用、第二帧 robot mask 缺失。后续八次端点判定均为 unmeasured，reason=`unobstructed_after_withdrawal_not_measured`。没有把缺测当无遮挡，也没有让未知端点触发停止。

因此目前瓶颈是偶发 robot-mask 缺测使成对基准失效；门和固定框架的平面本身已能拟合。所有单帧公开平面、mask证据和时序测量在 report.json。不能用融合版本字符串声称两视角都有效。

私有 open 谓词动作前后都为 true，关节角都为 -1.501553。setup close 未关门；公开原 articulate receipt 的 verified + no_effect 不代表完成新的一次开门。仍须建立可测基准、停止接线、独立选择与确认技能结果。私有关节只作报告标签，未进入运行时控制。

显式原 ledger SHA：`d035d9293ad12ce6f6ff7798e2eb84ef341703ebdd50a59b791487658effddd4`；真实 startup contract SHA：`cb098804d8cc19105e75dda5fb59c0bbdc4851c43b4b5c7094ff2f69a1d6e311`。未扫描 artifact 目录。
