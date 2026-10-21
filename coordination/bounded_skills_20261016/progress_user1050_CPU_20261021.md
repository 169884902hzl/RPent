本轮接续 USER10/20 10:50 + M7；不训练。当前runtime HEAD=645c4d22958fa77e3fccc346d909f41a9b2eaff2，CPU680通过、固定10首物理面板10973已COMPLETED0:0。以下旧记录按各自SHA保留；首物理不等于技能/整局上限通过。

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

当前接续：645c4d22完整archive SHA9c83d2cbcdc757abdcc92c612a0ae72eb7a185d98be158df8abfebcae8c09849，两端核同；CPU r16=680 passed315.12s。10973固定10均有物理步；碗首chunk move128/descend47/close15/lift32全部成功回执。容器lift payload拒、杯lift sweep拒、开关抽屉/微波炉nudge sweep拒、stove_on descend31tick braking拒等仍保留。三轮固定面板完整初态SHA不同，仅同case/seed开发诊断，不当严格N1或成功率对照。cpu/fixed10_645c4d22_closed_r1.json。
C4同帧fringe CPU10972：32个机器人表面一致样点全部滤除，47个box/drawer_close障碍样点全保留；79总样点，微波炉IK无几何点。源自cpu/fixed10_self_pixels_fringe_r1.json，不是物理FP/FN率。
B1 index_r4 CPU10974已120事件/54不同物理状态+动作；19条由paired.trials对应的登记branchpoint恢复，拒绝动作之前0控制步。计划B1_collision_forks_r2.json共54（prep29/scan19/move6），永久确认排除已CPU检查。初版CPU发现4个旧原版case缺夹爪标定字段；误连提交10975已1秒FAILED1:0，无物理步，原件保留。补同机器人已校准引用、保留源case，CPU预检通过后10976启动。首同完整起点对照ON0步sweep拒/OFF117步endpoint、私有无新增碰撞且payload保持。已闭合若干条；case015触发点提示SAM但诊断未提供客户端而程序错误，其他继续；正在给诊断接共享SAM服务，仅补程序错误状态，core645c4d22不变。
M7新oracle CPU24片10945/source031287f0运行，B2仍OFF，三端ACK未见。旧bcc完整4439（train3248/init798/task393）已共享C1核同。C4后续改动不参与M7的保存点云静态过滤重建，M7保持它自己的真实SHA。

重要修正（最新接续）：10977已0:0完成6个程序错误补跑，B1 r2共54/54 closed、53 OFF实际运动。cpu/B1_collision54_closed_r1 原始统计FP40/TP5/TN8/unknown1，**该检查器统计无效，不得当当前source误杀率**。CPU10978/79/80 replay前三例held_pixels均0；10981进一步证明：从旧checkpoint恢复的实际EEF与原回执before逐值完全相同，但live EnvState仍是工具包构造时step0（开局EEF），而已恢复scene实体source_step为154/199/180。旧checkpoint缺artifact_state，我新写的B1诊断器漏了旧观测恢复，导致拿开局RGB-D对当前持物位姿判碰撞。是诊断器错误，不能归咎runtime或放宽collision。旧全部物理/计分原件保留并将另加validity note。下一步CPU恢复旧frame cursor和真实已保存RGB-D：从choices路径定位源states.json，按已恢复scene的source_step/measurement views找真实capture；核该帧的公开EEF/quat/开度与恢复本体匹配后，将真实StepRecord前缀和所需artifact复制进自有目录，再保存两臂common完整checkpoint。若旧观测缺失/不匹配，单列，另登记fresh dual-view reconstruction；不再使用开局帧。可复用EnvState/StepRecord（rpent/session/base.py）和已有restore_original_subtask的fresh public reconstruction。B1 probe_r2.py是当前已运行脚本（core645不变），本地run_zero_step_collision_forks_20261021.py已接共享SAM并能按attempt summary resume；修复图像恢复后需新script/manifest/output，不混入无效r2。
M7新031287f0 job10945最新22/24 manifest、2597父请求、0错误，尚待全量聚合。CPU r16=680、fixed10 10973=0:0是真实core645证据，不受B1新诊断器错误影响。B2三端ACK仍未见，catalog OFF。旧10699/10777/10833继续，借卡watcher本地63075/ledger每30秒运行，C2出现时实际取消10833。

M7新oracle全24片10945已全闭合，聚合cpu/M7_031287f0_closed_r1：2966请求/5472位置/4907有效/4427源status可用=train3238/init796/task393，对旧2414增2013；0错误/RPC/物理步，VLA仍unknown。逐位置gzip SHA5302fd829f0693552deb55f738503cb1e7b7e88b5614eef4484814949f9b7bd4。新版替代bcc归档供使用，不能盲合并同record_id；C2继续重算跨split别名。

接续（2026-10-21 07:xx）：B1 新 probe r4 用同物理恢复状态重新采双视角，校验公开 EEF/quaternion/夹爪与本体一致，保留历史 gripper_command；点提示测量在共同状态保存前完成，两臂公开 screen 数组也验 SHA。真实 startup 后运行10984：COMPLETED0:0，54/54闭合、53条OFF有控制、完整初态0差异。结果 TP5/TN44/FP4/unknown1；clear被拒4/48，Wilson3.29–19.55%，仅旧拒绝子群。新独立原件cpu/B1_collision54_fresh_r4；旧r2错帧统计继续无效不覆盖。4FP为D2腕部扫描link7一次、原版杯子s7/15/11预备路线三次；CPU几何归因已准备，不改4mm间隙。

全技能CPU r19：685 passed/305.03s（/tmp/user1050_CPU_panel_r19.log）。r18运行期间修改测试/launcher，混用旧已加载测试与新函数产生1失败，原日志保留；冻结修改后的r19全通过。帧恢复/N1启动专项15项通过。M7仍为031源5472位置/4427源身份可用、train3238，已登记。

N1严格配对另修：只共享完整物理状态，每臂保留自身源码公开runtime并刷新，刷新前后均核完整SHA，避免把基线公开缓存带到优化臂。实际10698基线为6a2d6bb8（不是3968）；基于其完整源只移植D3快照运输，登记source_N1_6a2d_D3transport_20261021_r1。10985启动因缺PI05_CHECKPOINT_PATH退出1、无物理；已加入模型资源绝对路径CPU预检、补环境变量，失败目录保留。两端CPU preflight均0；10986只做两臂真实startup，不是32局完成。新代码/正式N1不能和旧非完整初态配对数字混用。

接续（07:5x）：10986两臂真实startup已COMPLETED0:0。共同完整初态a176318f3cfd7c73d930f988e28692e24c3a671f5ccb6de54c6af11ddbf874fe，积分5db9db2a...，各臂refresh后完整SHA也相同；baseline186/optimized222ticks。严格N1正式10989已跑（先baseline32再optimized32），另有10996单独pair0开发预览，依赖10993全部退出后启动，结果不与正式32重复计数。baseline首局成功，433.078s/284steps/2decisions；不是after提速证明。算法基线6a2d6bb8+D3transport。

原版默认call_vla标签：9个冻结train+ok原版初态/9类，按固定登记序首个可用状态选，不看新试验结果。stove on/off源220身份全部task_holdout，未采作训练pilot。source645不启用B2扩展目录。CPU预检全部0；startup10991_0真实1次π推理+1控制步；正式10993_0/1均COMPLETED0:0。8状态各3π+1self闭合；container前置self失败没有到达分叉点，保留unknown。π结果：碗3/3，盒1/3，杯2/3，开/关抽屉3/3，开/关微波炉3/3，推盘3/3；self仅碗1/1，其余7个0/1。都是每类1个状态，不能称类别可靠性。

新CPU exporter已实现完整状态/request/prefix/outcome/source绑定、实际wire prompt核验、policy权重SHA、later-recovery选择不贴回旧上下文、私有计量成本单列。两项回归通过。CPU_preview_r1先5位置20试次；实际C2 consumer measured_labels.py（SHA9e79b4cc...）5/5均status ok、coverage_issues空，source contract a0fef740。已通过共享登记交C1/C2；非B2三消费者ACK。CPU最终导出10997已完成，待读CPU_closed_r1并作同样consumer核验后交完整8位置/32试次。preview与full同record_id，不拼接双计。新捕获没有原规则annotation，source_rule_result明确unknown，不复制M7旧规则集合。

B3新原版证据：杯trial1/2私有v3成功但公开completion_lost；rise4.73/6.80cm，1cm向上验证移动在0步被payload margin拒，随动第二帧为0。盒trial3公开成功、私有v3失败：全11帧缺双指接触，支撑间隙5.4cm、TCP相对位移<1mm，不能以共动替代双指真值。旧结果保留。当前本地新增通用_hold_verification_motion：向上被拒后，只从公开筛查通过的其他固定1cm方向选一个，下降不得把测得rise减到3cm以下；不改间隙、力、总预算和共动判据。专项2项通过，全CPU r20=689 passed/319.18s。尚无新方法物理结果，待新快照与10物理面板，然后同cup三seed重放；不要提前声称修复有效。

恢复后已核11000_0三条均COMPLETED0:0，两个杯私有持物成功仍公开FN：e4六方向均0步payload拒绝，后续虽能生成技能但开夹爪释放物体，不算正确继续。新capture/profile launcher先不改runtime，仅存同帧RGB-D/本体/scene/payload及函数profile，CPU预检通过后提交同launcher真实startup11001_0。尚未放行full capture。原版完整标签CPU_closed_r1已8/8实际C2消费者接受，并已追加共享登记，替代5preview不相加。M7已独立交付，不重采。strictN1首对433.078→166.410s两臂成功/完整初态同，仅单对，不作32均值。

当前提速源码已按文件提交并推送6e3e796b6587c3f2cf6296bc0f94d4f726ed3897：高度带内才投影对夹点、同采样复用KD树、surface_measurement内部保留数组避免深拷贝嵌套坐标列表。CPU r21(采样)=689/302.39s；r22(含数组)=689/314.76s。CPU11003保存四输入共18实体完整采样记录字节同，9.722→8.121、11.598→7.482、4.142→2.603、10.176→8.193s；不是N1。新完整请求CPU11009碗14.965→13.145、杯17.919→14.222s且字节同；微波炉两臂缺sam3.segment原响应，同样未闭合，不填成功；D2首次缺frame-root启动失败，原日志保留，补原记录目录后25.757→22.329s且请求字节同。source_CPU_speed_arrays_20261021_r1只是CPU候选目录，正式完整Git archive88ea50bdf607f5c42a93402ac5dee097f16719c6a10f18b2afff3b3052b0a593已两端核同并解到source_speed_6e3e796b_20261021，固定10待物理结果。
持物根因CPU：旧杯轮廓及腕部遗漏点被当静态障碍；光流只确认1个旧点、射线自由空间未清关键点，均不足以修复，未上线、不改4mm。进一步保存π动作块已有的低分辨率公开RGB-D，试验从已发生的运动验证共动，避免为观察再发被拒位移；仍是e4执行源的纯记录诊断，startup11017完成，formal11018运行。原始e4两FN未被宣称解决。

源6e3e796b固定10物理11019已COMPLETED0:0、5:16；10项均startup_physical（首chunk），不是整局成功率。新严格N1同shared完整初态单对6e preview11020运行，预检及同launcher真实startup已通过；新source仍只占借用第四卡，watcher63075保持，C2无GPU作业。
杯子动作块诊断11018完成0:0、2:46。原版同两FN的低RGB-D回放在有效夹爪开度下找到共动：seed1 step132→148，手4.929cm，相对误差主1.077mm/腕0.782mm；seed2 step47/52→70，手7.885/6.040cm，误差5.350/4.167mm。仅CPU测量依据，不当新物理修复。公开旧障碍点维持不动，4mm碰撞/3cm抬升/15mm共动/空夹爪校准/力预算都不改。
据此已提交并推送1fd0e18070eccf2d6126a2dbdf1e168b4f945208：新bounded_vla_hold在π每个预测块前、有效开度下保留native RGB-D最多8帧（0 SAM）；最终实测目标反向光流/深度跟踪证明既有共动，再建立held，不需要额外动作。只有缺证据才用旧1cm筛查位移。匹配传感器对保存.bin+SHA，传感器复制时间归public_observation而非inference。不修改障碍所有权。新4项测试、23专项通过；完整CPU r23=693passed312.33s。尚无1fd物理结果，snapshot正在上传；后续固定10，然后同cup3状态/种子重放核两FN和首个自有后续技能。
新增代码：robots/libero/bounded_vla_hold.py、tests/.../test_bounded_vla_hold.py、coordination/.../scripts/analyze_vla_block_hold_CPU_20261021.py；尚未提交的prepare_vla_hold_replay_CPU_20261021.py和default8三份报告/本progress需按文件提交。源码1fd包含runtime+spec，不含这些收尾报告。B2目录仍OFF，未见C2三端ACK。M7保持已交031287f0（train3238、全split4427），不要重复采。

接续更新：1fd三杯种子11023已全部COMPLETED0:0，公开/私有成功、成功、失败全一致；两个真持物接carry_to/release成功，整局结果未评判。完整配对交付cpu/cup_hold_1fd_closed_r1，manifest SHA f0f213fc0a03d330a6879ae49eaa794f9307b5fad0a07f3a46550cde7b876749；已flock交共享登记。6e严格N1 case0 166.381s，与645 166.410s无可见增益，均成功；不能把CPU sampler提速当N1收益。
001363ee已推送：跳过将被丢弃的默认变体筛查，复用同控制步/capture的VLA末次观测。CPU696passed319.76s，archive SHA916faa5d18e2f52b6d2d35a6ed95a58276d0fb0557b6988eabfdb02ad0500479，两端核同，source_speed_001363ee_20261021。固定10物理11034(5:09)及同launcher启动11035(1:19)均COMPLETED0:0；正式杯回归11036运行，结果待收齐。
纯记录11025已COMPLETED0:0(5:17)。case0 profile实际热点：96次_cloud_and_ik累计79.897s，48次_instance_pixels累计58.447s，8次refresh累计52.150s（嵌套累计，不能相加）。已保存公开逐次刷新输入和实际291步轨迹。发现旧增量用20.4cm包球、计划路线、盲目touched、首次发现当支撑变化。正在改真实控制流/手部几何的扫掠刷新，并给N1换物理保留runtime的入口强制第一轮刷新。6项针对性CPU、16项含launcher回归已通过；旧尝试日志保留。r26手动通配测试错误地先导入MuJoCo导致collection失败，已换已有带GL设置的CPU面板脚本r27；不改测试判据。C6保存输入审计只支持5个非持物窗口：name重测20→16，缓存5个实体，其中1个table公开mask测量有21mm中心/35mm尺寸差，未把它认作真实静态证据；持物/释放因旧记录缺payload输入不作CPU通过结论，仍待物理核对。

最新：001三杯回归11036_0全闭合，2:50，3/3记录完整初态/请求/推理/控制前缀相等；公开/私有与1fd相同(TP2/TN1)，后续回执仍carry123+release15、carry32+release15，整局unknown。交付cpu/cup_hold_001_closed_r1 manifest cb9ac32e0ea25ccd0f5ec771ed323b141b2cc66ff60fbf40296fd7b65d99b1d8。
C6新源63fd9e9e6050a46b0525c006dc4c70b33d4c8c73已逐文件提交推送；CPU全技能面板r27=702passed313.13s。archive68c56767250a6f61685139b6244fc2c43d518b2102d9ac41e4db8acedc37b807核同，source_incremental_63fd9e9e_20261021；固定10物理11037运行。N1 pair0预览已登记，等待面板通过才提交。报告及未完成项已flock共享C1/C2；B2目录继续OFF。盒子旧3种子回归已CPU登记，将验证新公共输入检测是否仍有FP，旧真值不改。
