# 4463 公开微波炉时序核对与修复

原始物理请求已发生：服务器 ledger 为80 requested/80 executed controls，first
attempt标记physically_executed=true。作业非零退出来自launcher读错controls所在层。
此处不改launcher、source581或原始ledger，也不将这次已开门状态算首次开门成功。

原始9条temporal records为1对before和8对after。每帧都有agentview独立fixed-frame
与door的mask/平面，overlap=0，相对角88.36–88.53度；公开门平面并非全部缺测。
真正的停止判定全部拒在before的第2帧source_step21：机器人SAM返回0个mask，
occluded=null。这个固定缺测baseline使后面8块即使重新测到无遮挡也无法判定。

| record | phase / chunk | capture steps | 原始endpoint / stop | 原始判定与拒绝位置 |
| --- | --- | --- | --- | --- |
| 0 | before | 20,21 | 尚未判endpoint | 第2帧遮挡证据缺测 |
| 1 | after / 1 | 22,23 | null / false | unmeasured；before index1 |
| 2 | after / 2 | 24,25 | null / false | unmeasured；before index1 |
| 3 | after / 3 | 26,27 | null / false | unmeasured；before index1 |
| 4 | after / 4 | 28,29 | null / false | unmeasured；before index1 |
| 5 | after / 5 | 30,31 | null / false | unmeasured；before index1 |
| 6 | after / 6 | 32,33 | null / false | unmeasured；before index1 |
| 7 | after / 7 | 34,35 | null / false | unmeasured；before index1 |
| 8 | after / 8 | 36,37 | null / false | unmeasured；before index1 |

8条原始reason均为`unobstructed_after_withdrawal_not_measured`；不改原判定。离线
单独检查每个after pair时8/8都是公开pair ready，这只说明该对可测，不等于已证明
技能成功或改变8个null。每帧EEF实际clearance均达标，17/18遮挡状态false，step21未知。

只有agentview贡献的原因：wrist固定frame query为18/18零实例，几何补全也18/18
报`distinct_open_door_or_shell_profile_missing`。door在前4帧有SAM实例，但缺独立
固定patch，panel_filter报`no_independent_fixed_patch`，最终4帧均outside_parent；
其余14帧SAM无door实例。wrist最终frame/door有效平面均0/18，不会被强行融合。
主视角frame query也18/18零SAM实例，但公开RGB-D几何固定patch18/18成功；door
18/18独立SAM/平面成功。核对依据在`public_records_v2.json`与`diagnosis_v2.json`。

修复commit `db8d49c`：`MicrowaveEndpointCapture.start()`在接触前最多采3对（总计，
含首对），每对都有现行6个真实neutral hold controls。通过公开mask、withdrawal、
plane、来源和时间检查即采用这一对；保留每个被拒pair及原因。3对都缺测则保留
最后缺测baseline，后续不停止。SAM零mask仍是未知，不能被私有joint/predicate救回。
`measure_microwave_capture_pair`与最终时序判定共用同一公开观测检查，无阈值放宽。

CPU验证：77 passed，包括真实step21结构回归、首次缺测后真实12个hold controls
再采用第2对、3对全缺测18个hold controls的上限、缺frame/door继续未知、私有标签
不影响判定、完整首对不重复，以及原有门平面和放置停止测试。尚未物理验证新修复。

下一最小物理方案：新不可变source包含capture、door_temporal及launcher实际边界
修复，重建source identity与manifest，不修改581。沿用已访问原版task33/init0做
一局8块capture smoke，先看before attempts是否取得完整pair、实际hold数与下一块
请求；预计该一局约5–6分钟，额外pair约增加半分钟一对。若仍缺测，保留并定位
真实机器人mask，不把unknown改为clear。之后从已访问的原版microwave close用例
验证端点变化及stop，不将已经开着的open回合计为成功。公开before/after决定stop，
私有关节只用于独立测量标签。新包准备及两局开发检查预计1GPU 30–60分钟。

本报告的单对ready不考核首次技能门槛；没有新增训练行、确认状态或PRO输入。
raw远端SHA为`da104c9571059f48a30ac4017825ce8861e4925e5849f900c6c78ec29eeb216d`。
