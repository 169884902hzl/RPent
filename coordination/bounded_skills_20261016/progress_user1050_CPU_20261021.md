本轮接续 USER10/20 10:50；不训练。HEAD 仍为 333d12c6；下列新实现尚未作为物理批发布。

- A 已执行：取消 10698 剩余优化臂及 10834/10835；旧结果保留。当前修前恢复0为 10831/333d12c6。10699/10777不变。借卡只监控10833，Codex2出现运行或排队GPU时实际取消归还。
- C1 CPU语料已封存：`results/bounded_skills/kernel_corpus_20261021/manifest_original_r1.json`（1160 route/15575 IK）；`D2_slow608_r2/manifest.json`（85/1783）；`D2_held_r1/manifest.json`（25/177）；`cold_ik1000_r1/manifest.json`（1000冷IK，显式清缓存对照）。输入为带SHA的可信pickle，D2语料禁止训练。原版4个旧snapshot缺字段的后续位置错误仍保留，不伪称全位置成功。
- D1/D2：目标导向 progress/2 已按实际保存的相机轴/把手法向完成原版220重算（10876四片0:0）。最终N11只截掉用户允许的 `stove_off_libero_90_t39_s8` 成功；N33保留全部成功。历史尾段节省分别159422.883和107791.890秒，不是在线提速。原件 `results/bounded_skills/schema6_20261020/cpu/goal_progress_v2_original220_r5_exact.json`。默认轴r3及旧progress/1结果另存，不替代本证明。
- C3：三份保存输入的接触面配准输出逐字节一致，3.812→1.360、4.589→1.708、2.734→1.496秒；仅函数计时。
- 保存帧碗请求新增共享障碍体素分区后，31.669→24.237秒；两次均为CPU冷重建、无SAM/新采集/物理步，不是N1。仍主要耗在实例边界和抓取几何。生产候选内容尚待四输入对照。
- 已实现：B1当前占位不加深侵入/12mm自身过滤；B5重复静止observe去重；完整积分/控制器/RNG保存；C4公开关节渲染机器人深度；C5后台写盘和每帧数组只读缓存；C6接触/扫掠/支撑变化刷新；B2原地/开局姿态、有限提示变体、无锚点整句调用；B4实例裁图对比分数。上述均待物理面板验证。
- C2内核已接入r11（包SHA `631c4561123199dbe89f995ead11684432737fb9e0b50e6e9277c7688a1fccd0`），保留原暖路线IK；真实语料上的本仓整合核对仍待完成。
- D2未知子任务不再默认为空失败回放：单独执行公开整句call_vla，以native信号报告实际回放；采样上界继续unknown，不补PRO专用规则。CPU回归通过，未有新物理结果。

待办：零步普查CPU重判与≥50物理分叉；四输入逐项profile/数值对照；CPU全技能面板和固定10状态物理面板；原版四提示×预备方式分叉/真实schema6标签；新D2 40×恢复0/1/2全闭合；完整初态共享的32 N1；Codex2服务就绪后的留出模型闭环。当前没有将旧schema4标签挂到schema6请求上。

最新CPU面板：`/tmp/user1050_CPU_panel_r11.log`，673 passed，300.51秒。
M7 preview_r3：3请求/12有效新前缀位置、0错误、44次VLA候选unknown；已交共享登记供C2适配。原2414位置分类/切分索引已从冻结C2行包核出；新采沿用该父行身份和排除，另报有效位置及源排除后有效位置，不将原始位置数冒充训练分母。
零步cold r3：同一保存点云/路线下旧/新冷检查均拒绝474/1160，0释放/0新增；旧录制缓存值为378拒绝，差异来自缓存口径。持物另25路线均通过。该语料只精确关联3条普查事件，不能据此声称解决406条拒绝或给出误杀率；精确事件及物理分叉仍待完成。
保存输入profile r3：碗候选请求28.243→17.259秒，杯30.424→20.086秒，D2为649.641→17.886秒；冷CPU重建，无SAM/物理步，不是N1。候选/筛查/进展口径随源码改变，并非等价kernel提速；after还关闭了旧捕获缺失的crop验证。微波炉保存输入缺少后续点提示SAM返回，离线冷重算显式报错；保留错误，待独立存储的实际SAM重放补齐。

后续记录：61个任务文件已逐个add并提交推送 `bcc224124b3cc9ac5b85a4823035876359c8028d`。经SHA核同的完整源码快照为 `source_user1050_bcc22412_20261021`；传输中发现的一份不完整tar未使用，另一个 verified.tar.gz 已与本地SHA核同。M7正式CPU24片为10897，固定父split，未测VLA全unknown，不用GPU。10832旧N1取消时保留13个闭合结果，待完整初态共享的严格重跑。
10921固定10状态物理预检首局0 tick失败，正式面板未放行，完整失败日志保留。根因是C4用视觉网格凸包表面代替原三角面，填平凹槽，又按整数像素而非OpenGL半像素中心采样，留下机器人自身点。相同保存RGB-D和公开关节输入诊断：旧renderer对40/46个主/腕碰撞样点均滤0；仅原三角面滤38/35；原面+半像素中心滤40/46。没有私有物体坐标、没有改4mm碰撞间隙。修复后3项针对性CPU测试通过；全技能r13面板与同状态物理重跑继续。M7重建走原保存点云的12mm静态mesh过滤，不调用该renderer，分母独立。
最新全技能r13面板已675 passed，303.58秒（/tmp/user1050_CPU_panel_r13.log）；上述物理重跑尚未通过前不放行正式批。
B3旧原版VLA开发分支138个：TP115/TN18/FP3/FN2；一致133/138=96.38%，Wilson95%=[91.80%,98.44%]。close37/39、open39/39、push38/39、pick16/18、on3/3；8个self和1个无trial结果另列。原件 `cpu/B3_original_vla_verifier_r2/`，没有改阈值、没有给schema6补实测标签、没有重判确认批。

当前接续点（2026-10-21）：新提交/推送336b7b6edb48618b24d18da54ac13e81bff52e8b。10932所用精简archive漏根模块harness_v5_eval.py，启动非0，记录保留；完整复制source_robot_depth_336b7b6e_20261021已完成且核心/测试SHA核同，CPU真实校准加载import链10条通过。用完整快照重提10934，先通过同碗首物理128ticks，随后固定10闭合6条物理请求（bowl128/container107/cup226/stove_on603/stove_off266/microwave_open339）。box/drawer_open/drawer_close/microwave_close仍0tick且退出非0，面板未过，不放正式批。逐局：box在第158个样点target/rightfinger9；drawer_open第2样点palm1（点[-.196605697,-.000719332,1.25437355]，要核是真实障碍还是剩余自身像素）；drawer_close第174样点scene/rightfinger6、target/rightfinger34；micro_close第232样点numerical_ik_not_found。四局均同动作重复两次后loop stop，下一步应核公开失败记忆的oracle恢复选择及真实拒绝原因；尚未改oracle规则。
当前完整源：/public/home/sunyihan/rpent_libero_eval/source_robot_depth_336b7b6e_20261021；精简runtime_同SHA路径因遗漏root helper不用于物理。最终源同帧CPU复核10933已闭合，按原三角面+半像素中心实际滤除40/40、46/46样点，原件cpu/robot_depth_failed_startup_336b7b6e_closed.json。
M7全量10897仍按bcc22412独立CPU口径继续，0错误（最近1787请求/3661位置/3197有效/2923源status可用，含train及holdouts，不能全部叫训练）。最终等24manifest后aggregate_M7_original220_CPU_20261021.py聚合；父索引/public/home/sunyihan/rpent_libero_eval/M7_parent_index_20261021.json。B2新枚举仍OFF，无C2三端ACK；不要宣布新D2/模型闭环已跑。
旧333恢复0批10831已0:0完成40条closed；实际成功7，采样envelope成功11；其中libero_10_swap_t3_s40、libero_10_task_t3_s40为空回放，是旧问题，不叫40完整物理回放。旧原件汇总333d12c6/D2_recovery0_closed_20261021.json；新源码的native整句fallback待B2同步后实际核全40。10699/10777按用户保持；10833借卡watcher仍在，C2需要且C3>3时实际取消10833。

接续更新：M7 bcc22412 全24片闭合，2966请求/5488位置/4923有效/4439源status可用（train3248/init798/task393），比旧2414增2025；所有VLA仍unknown，0错误。聚合cpu/M7_bcc22412_closed_r1，逐位置SHA8fb0b7694e205e3590e9ce3aa4abcd90247494f96dc0fe9912b028a5bf4bdcf0。当前oracle恢复修复改变rule acceptable，新版需独立重采。r14全技能677通过；另增arm-sweep拒绝恢复用例后r15运行中。stage真实CPU预检对完整336源10条校准加载成功，对漏root helper源明确FileNotFoundError退出1；未替代首物理。
最新r15面板679 passed，315.75秒（/tmp/user1050_CPU_panel_r15.log），含碰撞/手臂碰撞/数值IK三种拒绝转向回归。零步101条去重为38个物理状态+动作，不能冒充101独立状态；≥50物理分叉仍未完成。固定10首chunk逐像素同帧复核CPU10941已提交（不占GPU）；运行时新快照将保留12mm有限表面匹配，不填层间隙。

031287f09498abe79bdb3e23f311a1c3a1e2d75b已推送，完整Git archive SHA54c8863d4d4824909badb26099f2c07fe72a8521be29b6a1a0380c3a90ae6911，两端一致。真实CPU导入10校准及manifest预检通过；物理面板10944已有首物理128tick，非技能/整局通过。新oracle M7为CPU24片10945，B2目录仍OFF。
C4同帧进一步定位：下降阻挡点离公开静态机器人实际三角面0.0015–0.55mm、投影偏差0.1–0.6像素；多层深度只能解决drawer_open那一点。box及drawer_close样点距当前机器人18–26cm，不当自身滤除。CPU10969已给79样点的精确表面距离（cpu/fixed10_blocker_surface_distance_r1.json）。据此新增一像素边缘覆盖，须同时满足到真实三角面3D距离≤原12mm，不扩4mm未来碰撞间隙，不填层间空隙。5个针对性CPU用例通过；全技能r16运行中。CPU10941曾因/tmp只在登录机可见而退出2，改共享路径10942完成0:0；失败日志保留。
