## 停服标记已拆开，避免试点收尾时12318被提前结束

RUN/sidecar_pilot_verified.json 只代表物理5世界/源legal/存档参考选择验证通过；新模型分片据此切边车，C2尚不能停12318。
RUN/sidecar_switch_ACK.json 由主代理在共享step完全退出、显存和日志已落盘、旧18065使用者已全部退出后再写，随后明确通知C2停服务。试点验证器不会自动发最终停服ACK。

## 边车r2环境修复已同步（等E1进程退出）

- C2交接SIDECAR_HANDOFF_r2.json，SHA620397e3cb76e57492204ab0dea1cf5956694c0b9e7e3a0a011f0f7a2fe3f0b1；with_selector SHA39af2fc2190482697f4d16522ca23860a427707526b8d8e08981709ebd57e66a。旧包装器会把C2Python3.12的PYTHONPATH传给C3Python3.10，C2已修并完成真实子进程CPUfixture；权重、模型输入和GPU2请求parity不变。
- 12385调度器和共享试点都显式给评测PYTHONPATH=9612源；选择器单独用C2环境。验证器读r2交接。尚无GPU物理结果，12318保留。
- 安装器现在读RUN/active_queue.json的queue_directory/array_job，不能再按旧12380或unlock_queue_1300重装。当前新调度器SHA写回active_queue.json。

## 共享试点窗口已获C2提供（准备就绪，未启动）

C2于20:54UTC提供12318内 `srun --overlap --exact` 四核窗口，等E1实际训练进程结束后启动，不能只按20–30min估计开跑；其E2会延后。
- 已编译及bash校验：RUN/shared12318_pilot/run.py、run.sh、preparation.json。用同一9612源和盒类5布局，episode并发2，预算/初态/策略种子不变；不是N1时延测量。
- 开始前只取消自己的PENDING 12385_0，数组暂降%2，与共享单卡合计<=3；共享步骤结束恢复%3。12318及保护作业均不取消、不改配置。
- pilot记录完整GPU峰值会包括旧A参考服务+新A边车+pi/SAM/完整机器人渲染；不能当正常单A生产峰值。
- E1结束信号尚在等；GPU步骤尚未开始。实时尾随会话在交接摘要记录，旧12380尾随已停。

## 最新队列补齐 DAgger2 的 300 对照（2026-10-24T20:55Z）

活动数组为12385，0–41%3；不是12380（从未启动，已保留记录后替换）。
- 0–8开发五次面板，9–27模型首选577，28–37确定性对照300，38–41接触/N1/E。各任务独立，无因果依赖；总计最多3GPU/36CPU/360GB，node02、nice500。
- 首边车物理试点是12385_0，使用C2 legal8包。源码仍9612e316，未改变物理执行栈；没有新的物理结果。
- 对照不是模型首选；两份查询SHA与C2登记完全相同，原source/state/request/prefix/outcome不重绑定；旧569不作为新数据重复采。
- 对照CPU12383：2个真实历史源保存输入全部通过，300条登记、0控制步。原worker及producer与577首选的逐字节相同，导出额外保留deterministic_contrast/provenance/model_selected_id。
- 活动登记：RUN/active_queue.json；新队列目录RUN/unlock_queue_dagger877；对照产物RUN/dagger2_contrasts_exact。物理采集未开始，C2服务12318保留。

## 10/24 13:00补充接续点（2026-10-24T20:25:03.367666+00:00）

本轮未完成，GPU排队时继续独立CPU工作，不因等待交回。
- 旧非因果链只替换7个自有PENDING/0运行作业；新12380为32个独立数组任务%3，0..8开发五次面板，9..27训练DAgger577，28接触、29旧N1、30新N1、31几何N1。node02 nice500，最多36核/360GB。保护作业未改。
- 失败黑名单根因：identity本来就是skill+parameters；0控制失败本来已计数。激进循环keep_retryable=True明确绕过二次屏蔽；原场景解锁还认掩码中心移动。已去旁路；无物理步不解锁，有物理步还须公开表面拟合完整兼容区间支持>1cm物移；新ID/中心抖动不解锁。
- CPU旧46局/1192请求重放：move/VLA失败后同参数紧接438，规划不可达后231，最长39；源实际计数>=2却选择764，准确无物理步段可阻止636。不是新策略回放成功率。原件RUN/CPU_blacklist_replay46。
- 新物理快照9612e31636706aef8e7eaab49528c35994002e89；CPU本地329通过181.67s，node02 CPU12381 329通过149.37s；另端点迁移CPU2通过。没有GPU新结果。
- 开发活动目录改为RUN/panels5_blacklist_v1；新N1 RUN/C0_N1_blacklist_v1。旧panels5_v4保留未跑。DAgger冻结历史绑定及接触配对原源码不变；不把主树整提交当物理SHA。
- C2原A legal8边车已交：/public/home/sunyihan/rd_instruction_20260923/c2_next_e_20261024_1300/sidecar_legal8；handoff SHA69ae14f22488532f458b0aba3d536f5c3615698bd6d210bdbf439dae5e59867a。12380_0先用边车验证5个模型臂；其余模型臂在ACK前仍用12318。同卡pilot完成后核对全部source legal及C2存档请求的选择/概率，登记ACK；待核查旧18065使用者退出，再请C2停12318，C3不取消该服务。完整同卡GPU峰值尚未实测。
- 本轮开发只PRO40–44与train布局；其他PRO种子不跑。已经做完的最终种子0–4只CPU构建/hash，不重复、不跑策略。

## 当前接续点（2026-10-24T20:04:10.905705+00:00）

本轮未完成，不因排队交回。最新实现与待运行队列只按此段及scope4_active.json。
- 主树已推：4195a373（ID关联）、066513a4（C0回填/面板）、3cd85d4661c38b74561d48ef732615104e7bc773（按raw query增量/显式刷新）；逐文件暂存，原guided-mask dirty仍保留。
- 物理公共源：b61f357604414fc45b2f019702a04ede6c6436d0；接触开发草案：2e6bdbb10b11f399ec7ee9901e298bc3b1abb34e。主树有先前已提交selected-grasp等额外改动，不能把主树整提交当物理快照引用；publication_scope4_identity.json逐文件已核。
- CPU：公共源299（node02 147.56s、本地201.30s）；主树301（181.43s）；完整接触组合12378，356通过147.79s。全部无模型训练。
- GPU最新顺序：12374盒5（oracle+原A）；12375其余8类%1（等盒5）；12376三类各5布局的接触修前/后配对（等盒5）；12308旧N1等12376；12377公共C0源N1等12308；12368纯几何E源N1等12377；12314训练DAgger577单次%1等E。C3总上限3GPU，与C2合计80CPU/600GB，全部node02 nice500。
- 20:03 UTC实时：三个受保护p3作业（12349_3、12349_5、12358）+C2原A服务12318占满4GPU；C3物理仍全PENDING/Resources或合法依赖。未修改保护作业。模型服务仍需，不可自行停12318。
- 活动面板 ROOT/results/bounded_skills/task_ladder_20261025/panels5_v4；45train世界oracle/model、PRO40任务×40–44共200世界oracle/model/pi已准备；PRO脚本未提交，先等开发5验证。C0模型D2+原版46臂在C0_model_D2_v4/preparation/run.sbatch已准备、未提交。
- C0实际证明已闭合：12361/d5同完整初态ea6121c3…，e9 move0步IK失败，下一请求该ID recent_failures1、IKfalse、不在legal；不是整局成功。
- 旧面板实际：碗3/5、盒oracle5/5/model3/5（已交C2选择修复）、容器3/5、关抽屉1/5，均ac源。修后尚无物理分数。
- 新修复：raw分割类与crop公开语义分离，2个实际调用路径CPU先FF后通过；不再对unknown额外SAM查询/遗漏增量记录。接触准备保留中间点、远侧实测推点；push完整向量（旧30条偏目标27–33度），方向表面配准同向；弧线控制未接入（微波炉现最多2次有效测量更新不足验证）。
- N1全30初态CPU12371已核integration/native_data/observation_state与SHA，0策略/0步；物理每臂仍必须严格SHA相等。最终PRO0–4的200实例CPU构建也已闭合，无策略评测。
- E纯几何源0bc4633f：4保存输入请求/几何数组逐字节相同，碗12.3915→10.6142、杯11.0399→9.3477、微波炉6.4681→6.1534、D2 1.9242→1.8071秒；仅保存几何构建，不是完整循环/N1/N8。top20已生成CPU_geometry_profile_comparison。实际N1待12368。
- 尾随首批日志的本地exec session会在交接摘要列明；若消失用tail -F ROOT/results/bounded_skills/task_ladder_20261025/C0-box5-scope4-12374_4294967294.log。正常资源等待，每15分钟核队列，有空自动开跑；不要因等待结束回合。

# 10/24 08:05+08:25 分级任务面板

用户要求上一轮三件先闭合，现已全部闭合：
- 模型A+A：D2 11/40，原版6/6（3独立初态各两臂），源3605901c；12195结束已写共享登记，C2自己停12193。
- 修正oracle+A：源b96cf55f，40/40闭合28/40（54.6–81.9%），对旧28/40改善3/退步3，对pi21/40改善10/退步3，有限自有方法并集33→34。三绑定局t0/t4成功、object_task_t3失败；两储物规则均已覆盖但物理仍失败。原件见option_expansion_20261025/CPU_oracle_A_option10_r2_closed。
- 新60布局660分支闭合，623请求绑定、37unknown；C2消费者有效621，已确认全部60接收。源c7520ae1，整句pi71/180、所有试次均有控制；PRO/D2/确认集未入训练。

实际repo /home/agilex/cobot_magic/rpent_libero_eval；SSH gpu5880-ts；远端ROOT /public/home/sunyihan/rpent_libero_eval。
旧轮RUN=ROOT/results/bounded_skills/option_expansion_20261025。
新轮RUN=ROOT/results/bounded_skills/task_ladder_20261025。
发布分支harness-v5已推dd8031a3；仅19个目标文件逐个暂存，原dirty guided-mask cache未提交，其他dirty未动。
本地上一轮报告 coordination/bounded_skills_20261016/reports/option_expansion_20261025/INTERIM_REPORT.md。

## 资源

node02 nice500，C3<=3GPU，与C2合计<=80CPU/600GB。p3/c5/c6/rf/RVRT/旧held不动，不release。
当前p3三张GPU+C2训练12279一张，占满；C3物理作业全部正常排队。不是基础设施故障。
N1 12256依赖已改after:12279（其现在已运行，仍Resources等待p3），确保C2先拿下一张卡；N2 12257依赖N1。
分级开发数组12294 0-8%2，12CPU/120GB每任务，依赖afterany12256。与N2最多3张C3卡。
不需要改任何C2或其他项目作业。
共享COORDINATION.md已去重为约8MB，照常flock append，不写archive。

## 新源码

隔离实现 /tmp/rd_task_ladder_20261025，从完整合格b96目录硬链接展开；修改已有文件前必须unlink再写。
首次源87f46dc6db6e4c4cbcb23aa51748b4e17fc0fde0：CPU12291 356passed，196.49s。
随后仅补C2看板接口/完成世界后自动更新看板，源ac6c68b39fe043ae6e7be6f5ef80ddbf54c27b79，CPU12293新5项通过，45train+200PRO已登记。
远端source_task_ladder_ac6c68b3_20261025；/tmp/task_ladder_registration.json；冻结/tmp/freeze_task_ladder_20261025.py。
所有物理分级作业使用ac，不原地改快照；尚无分级物理结果。
新源还没集成主仓库或推送；dd8031a3是已发布本轮菜单/绑定修复，ac是下一轮开发源，不能混称。

C0原件审计RUN旧轮/CPU_C0_model_A：713 move，675 planning_unreachable；643零步（sweep522/IK121），32实际控制（tracking25、制动5等）。618候选已有正recent_failures，216次连续move起点本体+锚点完全相同。
实现bounded_route_feedback.py：只有空手/无活动接触、零控制、完整筛查失败才记忆；哈希覆盖实际RGB-D、本体、测量点云、接触plan/承诺、导数历史和配置。相同输入下回填碰撞/IK后果，legal_after排除；任何输入变化释放。候选顺序不变，无私有真值。route_failure_feedback旗标默认false，新开发面板明确true。5项CPU行为/种子/看板检查通过；待5局物理验证，不称已证明提分。

## 面板和协议

RUN/panels5_v2/preparation/development_all.json：9类各5个不同新布局，45世界，先oracle+A。原65+新60没有stove，登记里明确缺项，考虑用同一生成器扩10个train炉灶布局，不能拿未扰动成功替代。
RUN/panels5_v2/preparation/pro_all.json：8suite×task0–4×seed40–44，200世界，oracle+A与pi+A，模型线待C2同步服务。
public helper pro_development_session只准40–44；原d2_session仍只准40；0–4绝不开发跑策略。最终协议CPU构建200实例留最后。
统一40决策/10000控制/7200秒；pi104块/520控制，no_progress_blocks5；无跨局记忆、失败不重置，只基础设施故障补跑。
runner run_task_ladder_20261025.py，每世界独立进程/EGL，共享每job SAM/pi服务；同世界各线restore同一完整checkpoint。
TASK_BOARD.md/task_board.jsonl位于RUN/panels5_v2；初始SHA1b8417380e45051c505d0b1cccd9eed0870665196605499545bb2a41a661f75a。
字段兼容C2 task_key/layout_seed/seeds/oracle_A_successes/model_A_successes/n/results_path/training_admission；未完成的成功数alias为null，原始逐线n单列；PRO永不train。
每world闭合自动更新看板。还需给外部launcher加“每task一级闭合写共享登记+SHA”的通知（不必改冻结执行源码）。
C2已ACK schema10（schema9a33e50.../contract5d823f.../legal7），服务等待12279训练和离线选择；不能用oracle替模型线。
C2 DAgger2（569条，每条1次）新清单：/public/home/sunyihan/rd_instruction_20260923/c2_next_d_20261024_0805/dagger2_saved_view_bound_v2/C3_DAGGER_ROUND2_TRAIN.jsonl，SHA e168abf36cbaa20ccb23ceef4acf8edc2e08a3e7dc09f2c90b98ddf6f612d45c。按F排后续。
C2还需训练布局model aggressive失败历史位置，完整预决策snapshot+绑定+>=2实测候选；现runner未加按失败历史保存，每world仅保存初态，需后续加，不能把D2当训练。

## C1 CPU根因与未采用草案

已宣布/读control-dynamics-contact技能。
旧轮RUN/CPU_contact_root_causes：
- drawer_close30/30、plate_push30/30至少一段准备耗200步且误差>12mm。
- microwave_close27可测里12条准备不到位后推进停滞，15条无公开plan。
- microwave_open30：扫掠24，无plan3，无锚点3；其中6条准备超步/不到位。
真实代码bounded_contact_setup和bounded_permissive.prepare只用_route[-1]，丢弃已算的抬高/横移/下降中间点；接触准备还可能沿用闭合空夹爪。
尚未改已冻结执行源或采用新控制器，下一步需在开发5状态上验证。

/tmp/rd_task_ladder_20261025里额外有未冻结、未接入的bounded_contact_geometry.py + test_bounded_contact_geometry.py（4项通过）：
- follow_arc 用实际3D把手位置SVD平面+圆拟合，只有非共线且残差<=既有3mm阈值才给后续弧线路线；直线不捏造铰链。
- push_contact_plan 用所选源点云相对所选目标的远侧3%实测边缘，实际边缘高度，45度斜指尖接触和两种腕姿IK余量排序；无物名/任务ID条件。
这些两个文件不在ac冻结包changed里，尚无物理结果、尚未接入，不要把它们算已修复。
需要先改准备保留经过点（同200步预算）、空手先开夹爪，再评估弧线/远侧推；运动增量仍4mm碰撞/IK/力/速度/预算不变。

## 后续顺序

1. 保存旧轮最终报告与40行综合表，补上三绑定/两储物失败回执归因；N1/N2排队继续。
2. 分级首5物理（12294开发oracle已排），模型服务就绪后模型线；PRO测量5级及pi基线（待提交，按同一源码）保留与开发修复不同域。
3. C0开发5验证、模型A重测D2；C1三类开发5，>=4/5采用后PRO对应任务重测。全部失败保留。
4. E函数profile最大的2–3项提速，要求不改行为，N1 30验证不降。可复用bounded_offline_labels FrozenSensors/annotation_state，避免自建假接口；尚未跑新profile。
5. 所有已毕业类每共享栈改动各5抽查；N1每日30；当前未有毕业类。
6. DAgger2训练split每项1，服务新模型替换模型线从5级。
7. CPU最终协议实例化/hash无策略在最后。
持续做独立CPU工作，GPU资源排队每15分钟刷新；不因队列未清交回。


## 16:35 UTC后的CPU草案更新

- C2已接收60新布局，621消费者有效；623源请求绑定的两条缺动作绑定由消费者保留unknown。
- M7父登记查询全部167炉灶位置都是task_holdout，无train父位置。因此不能从现有125布局造炉灶train面板，也不借用held-out；PRO测量仍覆盖炉灶。
- 新控制草案尚未冻结/采用：bounded_permissive新增move_route，保留已有经过点，同一200步总预算；接触准备空手闭夹爪先开，push使用远侧实测边缘并在直接准备后刷新RGB-D。原控制器推进/碰撞/力/速度仍未改变。
- 几何+准备相关12项CPU通过。follow_arc至少4测量位置，曲率偏离直线需超过既有3mm分辨率，不对直线或欠定输入捏造铰链。弧线尚未接入adaptive控制器。
- ac源物理仍排队；不要重新冻结/tmp源后还叫ac，其helpers现已有未冻结C1草案。ac远端快照保持原字节。


## E精确几何掩码CPU分支

原始固定输入profile：bowl构建12.786s（cloud11.897、instance7.627、numpy reduce2.980）、cup11.427s（cloud10.610、instance7.91）、microwave6.669s（cloud6.33、instance4.09、contact_surface1.29）；排除live SAM/渲染/控制。D2初始快照缺crop RPC缓存，首版明确unreplayed，没有伪造回复。
/tmp/rd_geometry_speed_20261025 从b96隔离展开，改精确finite_xyz/inside_xyz，避免逐像素3通道boolean reduce；保留长度1数组强dtype提升，防float64界限被float32标量弱转换。5边界/NaN/精度测试+原有geometry/skills共308pass（173.56s）。
冻结源47a194a5baa23a0dc4c2a72bfe580997bdd2c5da，远端source_geometry_speed_47a194a5_20261025；CPU12302运行308面板+四状态前后profile/请求SHA/全部已建pointcloud数组SHA核对。输出CPU_geometry_profiles_b96cf55f与CPU_geometry_profiles_47a194a5；两边一致关闭crop scoring，仅比较几何/候选，不把它称全循环时延。尚未安排新源N1物理回归。
新helper和两文件都未合并主repo，不能冒称已物理验证。


## 17:40 UTC 接续进度

- 12256 N1没有执行策略：launcher误指向旧common_starts，缺native_data，严格SHA在第0局启动阶段拒绝。旧目录保留；改用已有fulltask124c5654/native_complete_common_starts，重新提交12308（afterany12294_0），源b96不改。
- 12257 N2全部72试次闭合：screened任务谓词0/36，permissive6/36（开/关抽屉各3/6，其余0）；调pi6/36→36/36；permissive新增/加深>1mm接触3/36，均推盘子。盒子为pick分支但统计是放置任务谓词，局部私有抓取未知，不能声称pick0成功。原件旧RUN/CPU_N2_legacy_b96_closed；本地reports/task_ladder_20261025/regressions/N2_legacy_b96.json。
- PRO5级12309数组0–39%2已提交，afterany12294，200世界×oracle/pi两线；源ac，种子只40–44。模型线等C2服务。与串行lane12308→12310→12311合计最多3张C3卡。
- E ROI源0bc4633f34e8b24a781a7abd0602c39a96fcd4b6，独立于C0/C1；远端source_geometry_speed_0bc4633f_20261025。CPU12307：316passed、144.61s；四固定输入请求与全部几何数组逐字节相同。几何/候选构建秒：bowl12.3915→10.6142、cup11.0399→9.3477、microwave6.4681→6.1534、D2 1.9242→1.8071。不是整局/完整循环时延。N1 E12310依赖12308成功，复用同完整canonical及manifest，仅source更换。
- C1草案源7f5a9e41ee8c1d0367682f170a8ac213c1d77ea9，远端source_contact_routes_7f5a9e41_20261025；本地22项CPU通过，物理launch重跑同22项。主要是准备保持经过点、同总200步、空手先开夹爪、push远侧真实边缘+准备后刷新。弧线helper还未接入控制器；不称已修复铰链。12311 afterok12310：3类各5布局，两源ac/7f配对、同完整初态，own_contact_only无pi，40/10000/7200不变；不到4/5不采用。联系开发结果与主面板不同board，避免重复计数。
- 新runner仅可开关collect_failure_history；train/model线在真实失败历史后保存预决策完整snapshot+request+annotation+legal。尚无模型服务，没产生这批位置，后续还需>=2候选实测。
- C2最新DAgger2是577条当前A实际HTTP top，替代569历史清单，SHA7bc711b7da2838cfc89d7b383de01510fb455136002e108496c9a025726ff385。位置原执行源f698/f6ce/df589三种，单次、原snapshot/request/prefix/outcome精确绑定，不fresh重建后回填旧记录。准备目录RUN/dagger2_exact/preparation，19分片；CPU12313抽3源真实保存请求验证，尚未提交GPU。消费旧569为superseded，不能两份当独立观测。
- 最后资源：12294_0仍运行（5布局已闭合4个，3成功1失败，最后一局继续）；12279 C2训练运行；p3在node02占两张。没有取消或改任何其他项目/held作业。新PRO和N1等正常资源与依赖，不是基础设施故障。


## 19:05 UTC 后接续

- 上一轮结果提交0598b828已实际推送user-fork/harness-v5。
- 12361/d5真实零控制诊断闭合：完整初态ea6121c3…；e9 move_to数值IK失败0控制；下一请求同ID recent_failures=1、ik_reachable=false、blocked_at_current_prefix，不在legal。仅诊断，不计整局成功。
- 已复现同类重分类丢关联标签：关抽屉40决策7→163锚点、133→985候选，最后候选耗142.71s。修复保存原分割query类供关联，公开crop类仍为未知；两个碗重复5轮维持两个ID。Moka实际RPC不变，修掉二次计数。
- 完整CPU291通过：本地174.02s、远端12362/150.15s。冻结61619e68f00a8df94b8e57833aeb410343130740，仅C0/关联/回执公共修复，不含接触路径草案。
- 当前原A12318实测132候选HTTP200，1.45s，未数量裁剪。原件task_ladder_20261025/HTTP_initial132_capacity。
- 撤下自己的pending12294_5–8、12336、12309、12311；旧闭合、中断日志全部保留。新开发panels5_v3显式原版config，PRO显式PRO config，各记SHA。保护作业未动。
- 接触准备修正新草案f11d5964，12365：before616公共修复，after只加完整waypoints、开空手夹爪、远侧实测推接触；三类各5个不同train布局，无π，未采用；弧线控制尚未接入。
- 当前N1baseline12308在修前盒模型12355后；E12310已改等12365，DAgger577单次12314等E。C0开发5准备脚本仍在复制完整初态，提交号待收。
- 200最终协议实例CPU构建已闭合，种子0–4无策略/评分/控制。PRO物理开发仅40–44。


## 19:18 UTC：当前队列与源码口径

- 修前盒类模型12355全闭合3/5，对同源oracle5/5；自动看板已标模型选择（Codex2），未升级。新616五次12366还在等卡；当前3个p3作业+服务12318占满node02，未动保护作业。
- 45训练世界、200PRO开发世界的配置/预算/40–44种子CPU清单已核；原版config SHA4cd2fbcd…，PRO config33144f46…。PRO物理尚未开始。
- C0主树局部合并293CPU通过164.83s；4195和066513a4均已推harness-v5。保留主树原guided-mask dirty，以及主树先前已提交的selected-grasp等改动。
- 必须区分：公开提交066513a4的整个bounded_skills.py不等于物理616快照，它保留了主树先前已提交的其他执行修复；未把这些隐式混进物理批。616仍严格b96+登记补丁，291CPU。publication_code_identity.json已逐文件记录差异。不要把066当616引用或借用其物理成绩。
- 最新GPU串行：12366开发盒5 →12365接触三类配对 →12308旧N1 →12369回填源N1（显式route_failure_feedback=true）→12368几何E的N1 →12314训练DAgger577单次。独立开发其余8类12367%1；以后PRO%1为第三条lane。
- E12310仅pending，清单baseline_source误指b96，CPU预检发现后取消重提12368，完整初态未变、0控制，旧清单保留。C0模型46臂清单已准备，待五次训练验证；未提交PRO。


## 19:29 UTC：推方向CPU修复草案

- 对旧117条训练接触回执做公开测量审计：推盘子30条全部准备超步；实际所选目标向量被单轴控制偏转27.0176–33.4069度。微波炉开30、关27条都最多2次有效表面更新，无足够数据验证圆弧；不把圆拟合当铰链真值，弧线未接入。
- 新独立草案bb3318abc54d70ceadcdb0bead92e559a5c22324：保留准备经过点/远侧实测接触；push每段按当前物体→目标水平完整向量推进，方向表面配准沿同一向量测量，不再把y分量丢掉；其余关门/抽屉推进未改，阈值/预算未改。
- CPU新方向+原接触28通过5.39s，payload/core311通过168.78s；尚未物理、未采用、未合进主树。接触r2旧pending12365替换为r3新作业号待收，旧注册/源保留。
- 12371是纯CPU全30个N1完整输入审计，0策略/0仿真步；逐输入保存checkpointSHA、完整物理SHA、integration/native_data/observation字段，实际每臂仍须恢复后严格核同SHA。


## 19:46 UTC：原query作用域补齐，活动批次以此为准

- 扩展真实调用路径CPU复现出两项遗漏：显式按未知语义刷新时直接用unknown做SAM提示；增量刷新同时追加unknown、遗漏原类的刷新记录。两测试先FF，修后25通过。保存raw类别做关联的修复补齐到增量选择和实际分割query；公开标签仍可为未知，不捏造类别置信度。
- 最新公共物理源b61f357604414fc45b2f019702a04ede6c6436d0，接触方向/准备草案2e6bdbb10b11f399ec7ee9901e298bc3b1abb34e。公共源299CPU本地201.30s、远端12373/147.56s；接触方向组合46项CPU通过11.84s，尚未物理采用。
- 活动五次开发：12374盒（oracle+原A），其余8类12375%1；面板panels5_v4，45个train完整初态硬链复用，PRO200世界40–44三线准备但未提交。
- 接触三类配对12376：before b61 vs after2e6，相同完整初态/原版配置/公共关联与失败记账，15训练布局、无π；旧pending12366/12367/12372/12369已撤换，均0策略/0物理步，全部保留。
- 串行lane：12374→12376→旧N112308→公共源N112377→几何E12368→DAgger12314%1。12375%1是独立开发lane；以后PRO%1最多第三lane。固定D2模型46臂已在C0_model_D2_v4准备，五次训练验证后再提交。
- 新启动脚本的模板截取问题在CPU准备时修正，0控制；已核全部实际--source/--manifest路径、两配置、40/10000/7200预算和PRO40–44种子，未借旧源名藏新字节。
- node02仍3个受保护p3+原A服务12318，C3 GPU等待；纯CPU12371已完成30/30完整输入，0策略/0步。
