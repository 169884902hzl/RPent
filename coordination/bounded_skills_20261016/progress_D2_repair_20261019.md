## 最新续接：缓存兼容通过，等待3968同源startup

- 缓存源150的3条完整物理兼容已闭合：所有12项checks全True（π输入/动作字节、终点哈希、成功/停止、后继请求字节与动作/回执）。reports/sam_cache_full_branch_compatibility_closed_20261020.json。session26208结束0；benchmark26×3亦全字节相等。
- 后续D2的缓存登记已准备：results/bounded_skills/D2_cached_binding_hybrid_20261020/3968bdb4/preparation，manifest仍旧ecd48f...不换状态/种子/预算，只改计划顶层sam3_entry。5项CPU预检通过。真实startup在raw10684.6/session2339，两个原样startup案例中object_swap_t1已0、spatial_swap_t1仍规划；未全通过前不换派发。
- 通过后：停止唯一3896745，复制旧prep/dispatch.jsonl当前记录到新prep（保持已R10686_0），为已有输出建明确只读复用symlink，启动新prep派发器继续余3片。不可重提已R10686_0，不改10682；新旧SAM入口SHA分开登记。可复用source3968里的dispatch_repaired_d2脚本，新的startup-proof/CPU预检门槛仍需核验。
- 汇总发现真实计量bug：旧150的goal_swap_t0四分支都失败，full_replay=[]，但raw actual_full_replay_success=False。修scripts/summarize_bounded_hybrid_d2.py只在确有完整选择方法的实际重放时计whole-replay；没有执行/只执行选中前缀为unknown，四分支失败仍保留。27相关CPU通过（随后聚焦10项亦通过），reports/D2_replay_evidence_summary_CPU_20261020.json以真实记录证明0个整局尝试、不是1次物理失败。原始记录未改。该reader改动未提交。
- full40闭合后还需按原用户任务检查未实际整局重放的case；不能用raw false冒充实际结果。可用通用同保存初始态补一次择优方法重放（both_failed零比零按既定self并执行到失败）；不要写PRO专用规则，不混旧源或重选最好seed。当前先完成原版三分叉、s15修复三seed和新D2。
- 原版余39的r3：19worker闭合、78π分支，执行72成功64；杯pick8/8+6无π拒绝，cup on2/2，关11/14、开22/23、推21/25。唯一程序错误仍旧s15，修复补跑raw10684.2/session22167尚未闭合。原版10682三R+新D2 10686_0 R；队列未清。

## 最新性能诊断（不改变当前物理批）

- HEAD6755e1c8：新增只在独立启动入口启用的SAM多图像特征缓存原型；技能/规划/停止规则均未改。CPU24项通过。原型sam3_feature_cache_startup_20261020.py SHA2372a1c90496123c50e0ceb14395d86fc6496419d82027ffc6d1fce638d94751。
- 10684.3临时benchmark已COMPLETED0:0：26原版请求×3（off/on/off），响应字节全部相同，耗时6.574/2.956/6.498秒，图像编码23/4/23次。包括2个point RPC；不是整局吞吐。reports/sam_feature_cache_original_20261020.json。
- 新入口真实startup10684.4 COMPLETED0:0，1/1首π物理请求；随后源150同状态/种子三条完整兼容重放正在10684.5、工具session26208。preparation results/bounded_skills/sam_feature_cache_physical_20261020/15068167/preparation，indices[0,3,5]，full_owned10684。与旧150 full_owned10671比较π输入/动作/终点/后继；通过前不改现有10682/10686作业。
- S15绑定修复三seed复跑仍raw10684.2/session22167；约04:16首条19块，尚未闭合。这个父分配不能提前取消。
- 补了两条成功停止轨迹CPU精确重放：末端和终点误差0、unknown0；最早完整v3窗口为π54→handoff9和π56→handoff9（分别π开始后的64/66控制步），公开停止仍55/57。证据stop_success_first_windows_CPU_20261020.json，源150，不重评分任何确认批。
- 唯一调度仍PID3896745，日志monitor_public_binding_D2_and_original_20261020.log；旧3680760已停。10682三R＋新D2 10686_0 R，cap4因C2无GPU。后续D2三片待原版释放卡；新cache物理兼容通过后才考虑新入口用于尚未提交的片，来源/入口SHA分开登记。

## 最新物理启动与派发（覆盖下方旧PID）

- D2新源3968bdb4的startup10681.0已COMPLETED0:0，2/2实际首π物理请求，543.40s。新D2 batch0=10686_0已经R；其余3批由唯一派发器PID3896745接续。脚本快照内dispatch_repaired_d2_20261020.py，SHA04f7fbe725127ead2438ceb4c7cf9d724765c7563abaebbdbe4e93c1e84c794a；日志monitor_public_binding_D2_and_original_20261020.log。原3680760不在。
- 旧D2 10681_0已scancel，仅因为新源码替换，不改判。停止前37条π分支闭合、1个worker闭合、程序错误0，记录reports/D2_150_source_cutoff_20261020.json；其余partial保留unknown。旧源不混入新批结果。
- 原版10682三片仍R；s15新源三seed完整分叉仍在raw10684.2/session22167，首条π已开始推理，未闭合。父片10682_1不能在这个复跑结束前取消，因为它拥有共享SAM/π服务。
- HEAD7c7801e1已推送，仅报告和诊断准备脚本更新；物理执行源仍3968bdb4，不重建源。
- 下一步：确认10686实际π物理执行、盯s15三次完成、监控worker错误和C2资源归还；最终原版71状态按旧32/余39/程序错误补跑分源码交付。主报告D2_repair_status_20261020.md/json正在更新。队列未清不结束。

## 当前续接：公开提示绑定3968bdb4（覆盖下方旧PID）

- HEAD3968bdb4f5f88c63be1a60fc34d955ff169af5b3已普通推送。公开提示只对anchors可见/缓存实体消歧；不可描述候选省略，选中后失测返回unmeasured/perception/subtask_binding_unmeasured、0步且计入失败。schema字段不变，bounded-skills/4。
- 真实失败：10682_1的microwave_close_libero_90_t33_s15。腕扫后e2公开、e67失测且不在anchors，旧提示却用e67否决。捕获状态CPU重建anchors字节相等、旧报错复现、新提示close the microwave，保留e2。320项相关CPU回归通过；物理尚未通过。
- 快照source_bounded_public_vla_binding_20261020_3968bdb4；归档SHA bf0212555ae870ecd3c59aa910c9b17083a55ef69eaf9589b21d839cf334f0db。
- 新同状态验证CPU预检2/2，manifest SHA6986909fed0499bb2c2099018aaeee4dee77a3cfa4ae24ad6cda8a445240d8cc，输出results/bounded_skills/public_binding_repair_20261020/3968bdb4。首次物理startup在raw10684已有服务上启动，工具session53978；必须用新快照里的startup_on_shared_allocation，不用live根旧helper。通过后同三种原seed完整运行。
- 旧全局派发器3680760已TERM，无竞争控制器；10681_0/10682_0..2仍R，旧结果保留，等待新源实际startup后转移后续到新登记源码，不混分母。卡4/C2无GPU，80CPU/560GB，node02/nice500。
- 六例150交还已闭合6/6停稳和后继请求；3个私有真抓住都由bounded续接完成原生任务。三seed停止规则对照12条闭合；三个绑定歧义仍待物理消歧验证。不要把本公共提示bug称成Entity对象不等，它是未公开跟踪残留参与提示消歧。
- 优先：检查53978首次物理；通过后s15三分支、重登记D2/原版后续；监控并归因worker程序错误，不结束回合。所有PRO数据evaluation-only，永久确认排除有效。

## 最新监测与profile

唯一派发器现在PID3568107（3524921已停），代码cb103385；远端dispatcher_d2_accounted_20261020.py SHA04f7fbe725127ead2438ceb4c7cf9d724765c7563abaebbdbe4e93c1e84c794a。每分钟同时sacct/squeue、worker错误检测；registry可恢复，不重复提交。receipt reports/repaired_D2_dispatch_monitor_r2_20261020.json，log仍monitor_repaired_D2_and_original_20261020.log。当前四卡原版R，原版throttle3，D2无GPU任务已提交，等首个原版片释放。
Profile session96417/step10672.6已闭合0；首次D2空间t1的request约565.9s采样、grasp_geometry543.8、SmoothMotion.prepare517.1、screen427.9、geometry232.6、IK133.7，累计互相包含。样本命中不是调用次数。与未采样startup的首π输入和动作字节全部相同。完整前15项reports/D2_initial_request_profile_20261020.json；未改候选内容/顺序或规划源码。实际startup621.16s相对原544.64包含py-spy开销，不报成性能退步或提速。

## 最新闭合与调度（覆盖下文旧PID/待办）

150六例已全部闭合，完整π输入/动作与748基线6/6一致；6/6停稳和后继请求。两个碗carry/release原生成功；奶油奶酪改为carry189步+observe23步，追加同源保存端点续接为lower43步+release5步，两次决策260步、原生成功；至此三个π真抓住的例子都由bounded技能续接成功。其余三条原π抓取失败保留；17402000后继改为set_gripper成功，t3仍0步扫掠碰撞。紧凑证据reports/binding_handoff_15068167_closed_20261020.json、binding_handoff_inputs_CPU_20261020_closed.json。session42934/56963都应闭合，先poll确认。

D2两例真实startup10672.4 COMPLETED0:0、2个首π物理请求（544.64s；spatial_swap_t1初始规划约8分钟是新吞吐疑点，SAM只有22次共6.40秒）。已启动只读py-spy49Hz复现此例的首次规划：step10672.6/session96417，results/bounded_skills/D2_initial_planning_profile_20261020/15068167/profiled_startup，raw initial_request.speedscope.json完成后才写，profile.log有采样状态。py-spy0.4.2在本地uvx隔离cache安装，复制二进制到远端py-spy-owned-0.4.2；未改共享环境。只用原版父分配已有SAM/π，无额外GPU。运行中不改其登记helper脚本。

当前唯一全局派发器PID3524921；旧3171126已终止。代码commit09483422（普通推送），现HEAD1f69d857已推送（两个诊断脚本）；源码仍15068167不混。dispatcher_d2_20261020.py SHA23eb3270cb92fcd83cd53c57f05af8510cfcf224c886a5cefdd45e271b887582，记录reports/repaired_D2_dispatch_monitor_20261020.json；log reports/monitor_repaired_D2_and_original_20261020.log。它已验证D2同源startup和4项CPU预检；原版10670四R五PD时将原版throttle设3，等真实空位逐片提交D2；原版仍PD时最多1个D2，原版无PD后用满余卡。D2四个batch各10例、N8；未来提交逐行保存在D2_repaired_hybrid_20261020/15068167/preparation/dispatch.jsonl。现在还没提交D2 GPU作业，因为四张卡仍占满；不能说已在跑。C2 GPU排队则cap3，否则4；最多80CPU/560GB。不碰其他项目、node01、held。

原版10670 f909仍独立运行，最新r5：71注册状态、15worker闭合，94条π接口闭合，其中88真执行78成功、6预备碰撞无推理。开微波炉27/27，关微波炉16/25，推盘27/27，杯子pick8/12、on0/3（无π）；这些是中间分支、不是71/220整局结果，也不是确认批。无新worker程序错误。

62项CPU测试（共享launcher/调度、hybrid诊断/修复）通过；聚焦Ruff和py_compile通过。尚未提交主报告/进度/紧凑JSON/pi资产JSON，按文件add，不动无关dirty。下一步先收profile函数采样；继续汇总原版、盯dispatcher首次D2提交/首个物理请求；D2软件错误立即日志修复，物理失败保留。队列未清，不以提交或compaction结束。

## 当前续接：15068167（优先于下文旧状态）

- 用户10/19 10:30任务：修π交还、停止规则、source_binding_missing归因、耗时、重提D2、原版71状态call_vla三分叉；无训练。队列未清不能结束回合。
- HEAD1506816747489926709bc7fc49a0e730fd5da354已普通推送。快照source_bounded_subtask_binding_20261020_15068167，归档SHA1bff3a649f05bebf1808cfd25db474072bf5e5b21ec5c976161e1eafd19f7945。只补scripts/probe_bounded_hybrid_d2.bind_subtask的既有公开绑定记忆，43项相关CPU通过。首次新增测试fixture漏view_axes已补，未改判据。
- c023六例6/6停稳、6/6后继请求；两碗carry/release原生成功。奶油奶酪腕扫23步成功；再从保存端点跑4个bounded决策、92步仍4次observe。路线碰撞/IK均通过，实际问题是诊断入口未存源ID，oracle缓存同类误检使source=None。本次150修它，不为PRO写规则。
- 150六例实际startup10671.10 COMPLETED0:0、2个首π物理请求；完整10671.11进行中，工具session42934，输出results/bounded_skills/binding_handoff_20261020/15068167/full_owned10671。先poll它、读worker_summary，再与748/c023比完整π输入动作。
- startup10671.9调用了live旧helper写死standard，两个worker0物理失败退出1；已用不可变source150里的helper在新目录startup_owned10671_r2重试通过。后续一律指向快照helper，不调用ROOT的旧同名文件。
- 原版10670 f909源四R五PD、71状态，唯一资源监测PID3171126；reports/monitor_original_id_repaired_20261020.log。最新已保存r4：84条接口闭合，78真执行71成功，6无推理预备碰撞；6闭合worker。新持物/绑定代码不在此源，分开报。
- D2完整新manifest c9551b5df910fc77598ec38b40c8c26a8784433b37df940de5c92f90a0e76656，results/bounded_skills/D2_repaired_hybrid_20261020/15068167/preparation；40例、4个轮转batch、N8。CPU5项通过；真实startup10672.4进行中session15756。它复用独立冻结helper launcher_owned_d2_20261020.py（SHA56759911068e76ffe060493c77a8f9b9d2425d95980098b92497b679393a94df），只扩原复用helper的完整D2 admission，55项现有CPU通过。完整数组未提交，先让150六例续接闭合。不能同时起两个各自cap4的控制器。
- 偏离故障注入r3（脚本probe_vla_deviation_guard3d_20261020.py）10672.3 COMPLETED0:0，60.22cm触发原60cm left_target_region，13步停稳，后继请求；仅第一块真实π，后17块人工OSC注入，policy_success=null，永久不进训练/history/memory/策略分数。r2仅33.3cm未触发，退出1记录保留；r1身份适配漏接未进π也保留。不要改r3已登记脚本。
- c023奶油续接脚本probe_saved_handoff_continuation_20261020.py也已闭合，session75509退出0；输出saved_handoff_continuation_20261020/c0233712_cheese；其中4次观察的失败证据是150修复依据。
- 未提交：上述helper扩展、两诊断脚本与紧凑证据、主报告/进度/pi资产JSON；按文件add、不要add-A。其他dirty全部保留。
- 要紧的后续：150六例若奶油仍不能carry，沿新阻塞点修；通过后同源重提D2完整40。先实现一个全局资源控制器或原版释放后再启第二数组，node02合计≤4（C2有GPU排队≤3）、≤80CPU/600GB，nice500，保护c5/c6/rf和held。原版新闭合结果增量汇总，不以提交或compaction结束。
- OpenPI停止对照12条已闭合，55/57步成功；第三种子45/120/220均无v3成功窗口。三处绑定均公开同类误检歧义，仅CPU通用恢复验证；不能说物理消歧已修。π权重/metadata完整hash已匹配RLinf130-fullshot，训练含40+90，但无逐回合manifest。

以下保留分阶段历史，旧源/PID/待办不代表当前：

最新物理续接：af478781f7f14a9cb07964dae7944dc449872a96已普通推送。持物文字分割丢失时，由精确当前随手运动深度像素恢复点SAM；283项CPU通过。164保存公开缓存+同一图像2次现有SAM请求，+1mm/+1cm几何旧false→新true（非物理成功）。源/public/home/sunyihan/rpent_libero_eval/source_bounded_guided_handoff_20261020_af478781，归档49940b68dc07d6bd40504248816a8a997ca9e354b51674d1ab711f0dccdca5ba，manifest1dd17f9a382570a52d943f9f4e9a1b3600311c916c55db28e9b8a4ae8aa31619。两例同launcher真实startup10671.1 COMPLETED0:0，两物理请求通过；六同状态/种子完整重放在step10671.2（session67409）、results/bounded_skills/guided_handoff_20261020/af478781/full_owned10671，N6，共用原版10670_0已有SAM/π，没有新增GPU。先刷新本session、原版10670与PID3171126监测；继续，不等队列就结束。
原版10670仍f909源、四R五PD，与新guided源分开汇总。CPU中间汇总r1没有闭合worker，s4(on)/s7(pick)各三次是预备位测量碰撞0步、π推理0次；不能说π失败。s4拒绝点在路线早期仅移动约80nm，不能误认整个准备目标已到位；s7拒绝在3.5cm移动处，暂未改准备规则。当前只新改持物mask恢复，不同时叠加新停止/预备规则。旧杯子三成功是59源、原版新分母不混入。所有D2仅诊断不入训练；确认状态永久排除。
COORDINATION最新notice reports/guided_handoff_notice_20261020.json，offset6906137484，SHA5a5093e2…，已通知C1/C2测量值可能变化；旧COORDINATION巨大不能整读。

当前队列：新原版10670（f9096f79，manifest082f368f…）四片R、五片PD；PID3171126监测/限流，日志reports/monitor_original_id_repaired_20261020.log。四类真实startup10644.3全部物理请求通过，169秒、4worker退出0。旧10640_0..3与10662已因已知中性ID耗尽停止，已完成和部分记录保留；owned10641_batch0随父停止，杯子三成功、自身未闭合。旧session71229退出143，属于登记的停止，不是基础设施故障。新launcher仅替换等价SAM输出入口；技能核心仅ID池扩展，执行预算、真值判据不变。
新的CPU恢复缺口：164公开缓存中当前持物像素9629，但两视角都缺文字mask，_guided_payload_pixels因此拒绝点提示。正在验证用精确当前随手运动深度像素作为点seed，不从预测位置造像素；10项聚焦测试已通过，全相关测试session45620进行中。粗凸包遮挡6/6被精确三角面复核否定为只有1/6，未基于凸包删点；待真实SAM/后继物理复核后再登记源码。10670不含此WIP。

最新续接（10/20）：HEAD f9096f79已推送。原版杯子s1三条π结果均true，202/202/209步；self待闭合。原版微波炉两个旧worker因v5_runtime.refresh_fixture_parts的128中性ID池耗尽崩溃，属于程序错误。新new_entity_id保持首128随机序列，之后单调扩展，CPU两回归通过；全相关215通过、1既有SAM调用数断言失败（用修改前HEAD复现）。正在登记新source_bounded_original_id_20261020_f9096f79与launcher_shared_20261020_7ce53392，CPU预检session38339；正式startup须先真实物理请求。旧10640/10662和owned10641_batch0记录保留，不混新批。
SAM入口三条完整分支等价已闭合，输入/动作11/15/24次均相同，终点误差0、后继请求字节/选择/回执相同；基准4.236/1.173/4.077秒，不是整局吞吐。新正式启动器可选固定SHA的sam3_entry；51项相关CPU通过。当前π metadata与RLinf130-fullshot固定HF版本SHA相同，包含LIBERO-90训练域；未全量核权重。详细见主D2报告。

最新增量：原版杯子首个π分支闭合成功（20531000，56π+134预备+12交还=202步），公开measured_success与私有v3一致，1311.45秒中SAM1055.52秒。该状态1/3采样，全队列只1/213个π结果已知，其余未知。报告original_first_cup_branch_closed_20261020.json。自有step10641.0时限已延长12小时，父分配仍原18小时，仿真预算不变；session71229继续监测。原版全场/目标监测7对实际共有前缀相同（r3报告），完整轨迹尚未闭合。

## 最新续接（覆盖下文队列号）：10662 + 自有step10641.0

- 10653_0仅pending取消后，batch0在raw JobID10641的step0执行，工具session71229；输出results/bounded_skills/original_measured_forks_20261020/59f7daf8/owned10641_batch0。8个独立进程共用现有模型RPC；不新增GPU，父分配剩余十余小时，父0..3旧任务继续保留。
- Slurm在取消10653_0后无法再调整ArrayJobId10653限流，控制器2842910退出。已在数分钟内将余8个pending原样重提10662；新唯一控制器PID2904228，reports/monitor_original_measured_repaired_20261020.log，优先10662再10640。10653原始提交收据保存在preparation/full_submission_10653.json，当前full_submission.json指向10662并登记batch0覆盖输出。
- batch0已有杯子/开微波炉/推盘π推理，关微波炉仍完成准备。四个开/推首次π输入和动作哈希一致；sim_state差0，仅Python/reset sampler独立RNG不同。报告original_full_targeted_prefix_CPU_20261020_r1.json、original_fork_snapshot_difference_CPU_20261020.json；不得写整条轨迹已一致。
- 12个停止设置终点CPU物理恢复误差0，两个碗种子均抓目标；14401000基线近另一碗，延至120/220仍无目标双指接触，且无v3成功窗口。详见calibrated_D2_stop_actual_endpoints_CPU_20261020.json。
- Git已推送2bb1adb1（启动复用+显式batch输出汇总），执行源59f7/748不变。相关CPU14项通过。下一步：监测session71229及10662，逐分支闭合后增量汇总；原版旧全场源独立保存。汇总命令须带--batch-output 0=<上述owned10641_batch0路径>。

## 当前续接：10653 原版目标测量分叉；六例交还和停止对照已闭合

- 执行核心7484079b；保存原版起点入口59f7daf8；Git HEAD ae578bb3（修正持物阶段）。六例 selected10649：6/6停稳、6/6后继请求；13401000/13402000续接carry_to→release，原生成功；14401000/16401000/17402000后继扫掠零步拒绝，17401000 observe23步no_effect。
- 10625停止对照12/12闭合：两个碗种子55/57步成功；14401000在45/120/220步均失败，精确动作CPU重放没有v3成功窗口，unknown0。暂保留现有pick的3块/5mm默认；其他子任务尚属探索。
- 原版四类真实startup在自有10644.1（sacct显示10640_3.1）完成：4/4退出0、4个π物理请求，430.6秒。第一次未设LIBERO_TYPE=standard失败退出1，记录保留。新正式10653，9片N8/71状态；manifest SHA256 9a66314ef33e8a079d4dca44252ab23a935bc49b1db553b90595e6355d5b3908。
- 10640_4..8仅pending已取消；10640_0..3在跑保留，独立作全场监测对照，不混入新分母。新数组等释放卡位。唯一控制器PID2842910，日志reports/monitor_original_measured_20261020.log；优先10653再10640。C2无GPU作业可借第4卡，出现后并发≤3；node02/nice500，每分配20CPU/140GB。
- 逐例结果、旧拒绝check+姿态、停止矩阵、三处绑定归因与耗时见reports/D2_repair_status_20261020.md/json。原版全结果、三处绑定物理恢复、剩余后继碰撞归属未完成。无训练，D2不入训练/history/memory，确认状态永久排除。

下面是保留的历史状态，以本段为准。

当前修复执行源 `7484079b91021a7eebbcd48756c4eb3a047d1563` 已提交推送；真实startup10637/10638共4个π物理请求通过，正式10639（两状态续接）/10640（原版71状态）已提交。源码与manifest见下表。
旧标定源 `83075952` 的10625（12分支停止对照）继续独立运行；10627原版已取消并保留部分记录，10628两状态已闭合。旧规则与当前批次分开，不报混合整局上限。
10628已闭合：13402000在π控制57公开测得成功，停稳10步，交还后私有v3成功；17401000用满120控制后失败，停稳7步。前者后继请求生成，但腕扫因payload碰撞0步拒绝；后者后继23步。不能把请求生成或attempted写成续接技能成功。
CPU公开几何已定位13402000的腕视角碗边缘仍被留作静态障碍，向上1mm会触发payload碰撞；保持间隙和判据，继续查像素归属。全场感知同状态重放未闭合，窄监测默认off不推广。
原版VLA-off220独立131/220；三处绑定失败归因公开误检歧义，通用观察恢复CPU已验证。无训练；D2不入训练/history/memory，确认状态永久排除。

## 当前快照与运行（83075952）

- 源码目录 `/public/home/sunyihan/rpent_libero_eval/source_bounded_hybrid_handoff_20261019_83075952`；归档 `bounded_calibrated_vla_20261020.tar.gz` SHA256 `a27dd30845ab48b97adde83ecdb15eab4277a06679cfe4af84d7ad9ebaf87c09`。
- D2 manifest SHA256 `6d1be08b68de8e90b7803f91fa96486280ac434868a5dbc776658fe5e235c5b6`；原版 `d3b49b41acc532034617ced874ef866daeef92a6fdb552b3c8fe0f940a746335`；窄监测 `0d38b7c2b94a80cea95bb4ace56d9b10bed9004d1eda2c8e42083b4d267ad7d9`。
- 解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`；入口 `scripts.probe_bounded_hybrid_repair:evaluate_case`。固定启动器SHA256 `3fa8bb8f1740611bd815de8333ca0de9ddf7f66b8469da7847d1baa80ffd66aa`。
- 唯一资源控制器PID2504176（旧PID2483354已停）；日志 `reports/monitor_hybrid_repair_calibrated_20261020.log`。node02、nice500；C2无GPU作业时4×20核/140GB，否则并发回落≤3，不取消在跑任务。
- 新建原版汇总器已在实际计划运行，明确保留prefix_not_reached/unknown/无推理分支；还校验每状态各分支的初始物理与请求SHA，9项相关CPU汇总回归通过。
- 实际预检标定证据：`reports/calibrated_startup_wire_identity_20261020.json`。窄监测端点：`reports/calibrated_targeted_endpoints_CPU_20261020_r1.json`，物理状态恢复误差0，目标碗双指接触。
- 后继阻塞根因与修复中：VLA在抬高约3cm以后才捕获reference.scene，使当前碗的漏分割边缘距“静态”参照3.972mm，被4mm静态否决器排除。腕图60、像素(753,570)属于持有碗；旧cache明确否决362个当前语义像素。`reports/calibrated_t2_handoff_geometry_CPU_20261020_r3.json`只更换静态参照、两臂均不调用SAM：旧362个被否决、新0个；0/1/10/100mm上移几何探针由1mm失败变成全部通过。没有改碰撞间隙，没有声称整条路线/IK已通过。
- 修复保留抬起后的target+EEF配对、改用接触前静态场景；新增stationary_capture_step和artifact出处。13项VLA聚焦与276项相关回归已通过（首轮新测试的模拟对象缺姿态/接口参数，已补齐，未改实现判据）。正式物理回放10639在跑；83075952仍作为旧静态参照批。

### 接触前静态参照修复：7484079b

- 已按4个文件逐个add、提交并推送 `7484079b91021a7eebbcd48756c4eb3a047d1563`。归档 `bounded_precontact_vla_20261020.tar.gz` **完成后**的SHA256为 `3816c371e3d7b263d3c816cf5e56f72870083667760f36a5196f2bbe0bc824a8`；源码目录 `/public/home/sunyihan/rpent_libero_eval/source_bounded_hybrid_handoff_20261019_7484079b`。
- 276项相关CPU回归通过（153.65s），最终原版调度/汇总9项回归通过（0.27s）。pytest提示本地缺少timeout插件；测试本身通过。未跑全仓或模型训练。
- 原版分叉改为π三次先跑、自身技能后跑，固定分支index仍为1/2/3/0；各目录名、种子和分支预算保持，逐支恢复同一完整状态。startup与正式首分支同用index1。前序子任务仍需先到达登记分叉点，未到达不计π失败。
- 83075952原版已保存换源前中间表 `reports/calibrated_original_before_source_replacement_20261020.json`：71登记状态、1个prefix_not_reached、2条完成的self均失败；当时没有完成的π分支，不能写0/71。后续换源记录单独保留，不混新批。
- 三份新计划全部通过CPU预检。两状态试点startup10637 COMPLETED0:0、1m30s，共2个实际π物理请求；原版startup10638 COMPLETED0:0、2m18s，open/push共2个实际π物理请求。通用launcher的physical_episodes=0是其完整回合计数，不能据此否认startup物理请求。预备脚本首次从live根目录找不到（exit2），已改成直接运行上述不可变源码目录里的脚本；没有提交失败GPU作业。
- 正式10639（N2）：manifest SHA256 `eea82075e0b979df29a2945ea511b29a8335ac3d1564905a1ed00dcc3b891ba8`；原版10640（N8、9片）：manifest SHA256 `3b9ce36f49f9e2efb23775c1bf4f7b2ac2479a08d416558d64b9100204681996`。各输出根为 `results/bounded_skills/{targeted_vla_pilot_20261019,original_hybrid_forks_20261019}/7484079b`。
- 当前唯一资源控制器PID2607071，旧2598441/2504176已停；日志 `reports/monitor_precontact_748_formal_20261020.log`，controller SHA256 `035fc7fced3746f903999902ee4f7e36391c8b57d1a18b0def4c98b8d7cf36c6`。node02/nice500；C2无GPU R/PD才借第四卡；原版数组按实际空位放行。
- Codex1/Codex2通知已追加共享COORDINATION，收据 `reports/precontact_source_notice_20261020.json`，偏移6905579637；说明源码、scope、内部证据来源、旧批保留、无训练及永久隔离。

以下为分阶段历史记录。旧“待提交/待预检”和旧PID只描述当时状态；当前作业与待办以上述当前快照及最新实际收据为准。

## 当前指令与身份

以用户 10/19 10:30 指令为准。先修交还和停止规则，明确绑定归因；原版微波炉开/关、推盘子及失败杯子状态补 call_vla 三次分叉。混合整局分数在修复前不作结论。

- 仓库 `/home/agilex/cobot_magic/rpent_libero_eval`，分支 `harness-v5`，远端根 `/public/home/sunyihan/rpent_libero_eval`，SSH `gpu5880-ts`。
- 旧 D2 源 `75ce7d53b0e106618c61cc3ef1c5fc5bb93cecae`；旧正式数组 `10477` 在 10:35 PDT 取消剩余分片。收据 `reports/D2_10477_stopped_for_user_repair_20261019.json`。
- 精确六例以 `preparation/D2_handoff_six_20261019.json` 登记，来自保存的 `shared_D2_interim_20261019_r3.json` 中六条有实际 VLA 推理的分支。三失败：spatial_swap_t2 的种子 13401000 / 13402000，spatial_swap_t3 的 14401000。三成功：object_swap_t1 的 16401000、object_swap_t2 的 17401000 / 17402000。均为 init40。
- 原版 220 仍使用 ec89f74 + 旧并行启动器，不受本次源修改影响。仅按登记 old164 + 10446 new56 汇总，不能混入诊断。

## 已有证据

`reports/D2_handoff_six_raw_diagnosis_20261019.json`：五次 measured_sweep_collision，一次 measured_payload_collision；没有先报 IK 无解。五次在离当前位姿 0.8–3.6 mm 处拒绝，另一次 23.7 mm。原始 VLA 控制为 45–70 步，9–14 块，准备动作另计。

`reports/D2_contact_hold_CPU_20261019_r1.json`：CPU MuJoCo、关闭相机和 VLA，准确恢复六个旧端点的完整物理状态。零位姿增量、夹爪命令保持，六次均在 7–21 步内达到四帧低速；最大漂移 3.8–15.8 mm。三个旧 truth=true 的试次之后仍为 true。此项只证明端点停稳，不证明完整重放或后继技能成功；不修改旧标签。

当前 62 项聚焦 CPU 测试通过（VLA、运动、诊断、计时、启动器），另 `bash -n`、`py_compile`、`git diff --check` 通过。新增启动器原版诊断域先加载 env_server，修正 GL 导入先后；诊断输出不冒充完整回合成功。

OpenPI 官方对照：`https://github.com/Physical-Intelligence/openpi/blob/main/examples/libero/main.py`，10/19 已读。replan_steps=5，开局等待10步；空间/物体/目标/10/90 套件控制上限分别220/280/300/520/400。我们的三个失败都属于 spatial，扩预算对照取220。关闭 no_progress 时保留公开成功、越界和原生结束条件，单独记录实际停止原因。

## 代码与运行入口

- 核心：`robots/libero/bounded_motion.py:settle_osc_hold`，`rpent/skill_package/vla.py:VLABudget/run_fallback`，`robots/libero/bounded_skills.py:MeasuredSkillAdapter.call_vla`。
- 新诊断：`scripts/probe_bounded_hybrid_repair.py:evaluate_case`。同旧分叉点、同推理种子；保存共有动作前缀差异、耗时分类及交还后的第一个 bounded self chunk。原版对应子任务分叉也复用此入口，尚未登记/提交。
- 准备：`coordination/bounded_skills_20261016/scripts/prepare_hybrid_repair_20261019.py`。新 source archive ->12条诊断 manifest ->全量 CPU 预检 ->真实3设置首步 startup ->再提交两个6条分片。每卡仍共用 SAM3/π0.5，局间 fresh process/EGL/RNG/IK，局内候选串行。
- 启动器增加 `evaluation=hybrid_repair` 路由；仍调用已验证的 spawned-state warmstart 恢复和首请求内容/对象兼容逻辑。原版诊断也设置独立私有模型归档目录。
- VLA 回执有 preparation / inference / public_observation / control / handoff 计时；试次另保存不重叠的 EpisodeTimings 切片，SAM 为其中的 segmentation，私有计量已有单独秒数。

## 待继续

1. 交还源 e120c61f0156a28ba087937b23fecf7f00d38c6a 已提交推送并登记，三个计划 CPU 预检通过；同启动器真实 startup10531_0 已提交，当前因资源优先级排队，未声称物理通过。源码快照 `/public/home/sunyihan/rpent_libero_eval/source_bounded_hybrid_handoff_20261019_e120c61f`，归档 SHA256 `8fb00ad5b63e466626c7b310bc1e822181dbeaa423f8058ab065126255e3723a`，manifest SHA256 `822bf19c7d4ff8f6ffe87b606d2d01c602b7f7490be81edeb8214b26ffe04d3a`。
2. startup 实际产生推理和物理步后才放行12条诊断；更新唯一控制器的优先数组 ID，保留原版10446。不要重复提交。
3. 六条重放必须检查：初始 physics/request SHA、共有动作前缀、handoff settled、后继请求和 bounded chunk 是否真的执行。
4. 停止规则的3×2对照按轨迹最终接近实体、实际成功步、总预算及停止原因决定下一轮规则；先取得至少一条完整分支的耗时拆解，再改感知频率。
5. 三个绑定失败：object_task_t3 的 ketchup 两候选分数0.836/0.461；object_task_t4 的 milk 两候选0.852/0.820（第二个仅1.6cm高）；goal_swap_t4 的 bowl 两候选0.949/0.355。查看保存 RGB/SAM 掩码，排除公开误检，不按私有实例ID选择。现有 `trial` 在缺绑定时直接退出，没有给观察恢复机会，也要核对通用恢复路径。
6. 原版分叉仍待登记/预检/提交；新40局混合整局批须等上述修复定下后重新登记，旧10477不混入。

资源：仅node02，nice500；默认≤3卡，C2无GPU R/PD才借第4卡；合计≤80核/600GB。保护 c5/c6/rf 和 held。唯一资源控制器 PID1959364，源 `monitor_v3_timing_20261018.py`，当前优先10446/10531；旧PID1380503已停止；新诊断提交后需更新并确认只保留一个控制器。旧只读 watcher session11207以10477全结束为条件，取消后不会自然完成，后续不要靠它判断新诊断进度。所有确认状态永久排除训练，D2不进训练/history/memory。

## 后续 CPU 工作（10/19）

- 通用绑定恢复提交 `b74ee664` 已推送：缺绑定时两臂只选请求中的合法 observe，之后重新从公开测量绑定；不把 VLA 分支偷偷换成 self 接触。`reports/D2_binding_recovery_CPU_20261019.json` 用保存的三个 annotation/request 证实原 oracle 均会选腕部扫描（2.03 / 0.51 / 1.79秒，无物理步/GPU）。RGB 及掩码归因：BBQ酱误作 ketchup、奶油奶酪误作 milk、盘子误作 bowl；多个同类假设而无语言位置限定，原绑定器拒绝任选是正确的。真实重新观察能否消除歧义尚未实测。
- `reports/D2_old_stop_paths_CPU_20261019.json` 保持旧标签：t2 两种子 VLA 控制55/50步，末端离绑定目标29.2/29.1cm，离另一个 bowl4.8/7.4cm；最后15步仍净移14.9/15.8cm。t3 控制65步，末端离目标16.9cm，最后15步净移2.0cm。三条进展向量均无非有限值。距离标量+物体位移不能代表全部末端运动；仍待同状态120/220预算对照，不据此擅改最终阈值。最近实体只按初始公开中心计算，不是接触身份或私有末态。
- 原版分叉源 `4133210efe0118b4521b5f1f92637b446a2ac439` 已提交推送，源码快照 `/public/home/sunyihan/rpent_libero_eval/source_bounded_original_hybrid_forks_20261019_4133210e`，归档 SHA256 `efc47087ba85a142d4674f6e0244b276f4b3e4d6fe466702793537228c5b6a8b`。新增通用公开 push 模式，不把推盘子拆成 pick；LIBERO-90 原版微波炉准入修正。schema `bounded-skills/4`，SHA256 `6ea1c1a2a1941340f2a29b2d349d6c36d787a156fdc4b4c5ab3e652376ce392c`；核心仍无 BDDL/真值位姿。
- 321项聚焦CPU测试通过（168.92秒）；py_compile / diff-check通过。已有handoff旧测试改为验证新settle接口之前保留测量payload，与旧自由空间brake路径的有意替换一致。永久确认状态排除规则保持。
- 原版计划：微波炉开20、关20、推盘20、失败杯11，共71状态，每状态self一次和VLA三次。先真实首步startup；完整分支预算是明确的探索性no-progress关闭、原版套件评测量级控制预算，不冒充已选定停止规则。无训练；不计入原版220或D2整局分数。

原版71状态全部10项CPU预检通过，同启动器四模式首步startup10548_0已提交；manifest SHA256 `7f7cba7b5faf827f982be4c87f4e0967a7e1bc3deeb0647382f2eacce71b1105`。仍待真实首步，正式数组尚未提交。

## 原版分叉阶段更正（仍为开发登记）

`4133210e` 的 startup10548 在启动前取消，耗时0、无物理请求。CPU核对11个失败杯子状态的终末私有状态：9个第一目标已满足，2个第一目标也未满足；9个第二目标中2个已持物。不能统一测第一只杯子的pick。

提交 `cc364d3474d5be92584a53ea7a297c353baeb5e3` 已推送。新原版快照 `/public/home/sunyihan/rpent_libero_eval/source_bounded_original_hybrid_forks_20261019_cc364d34`；归档 `bounded_original_hybrid_forks_20261019_stagefix.tar.gz` SHA256 `9609f2b8fb34bb015d06d39e7c8047ca627e34b0e9104dcecd2cff9d4fd5d100`。原版fork按固定goal_index/subtask_mode，前序原版子任务只用bounded self动作执行，失败边界不可达时记prefix_not_reached；不跳真值位姿，不把未尝试计作π0.5失败。38项聚焦CPU测试通过，schema仍v4同SHA。新71状态计划重新CPU预检中，原版startup仅检查新LIBERO-90入口和push接口的真实VLA首步，不额外要求任务成功。

替换原版10项计划CPU预检通过；真实startup10554_0已提交、未声称物理通过，manifest SHA256 `00138db64e90545febdc26fff16f2f5aabea4e2a982f7d2706fad5f68f7e6941`。D2 10531保持。

## 在途实际结果与新根因（优先于上文旧待办）

D2真实首步已在自有10446_6分配中完成：`owned_startup_10446_6_r2`三种设置均1次推理+1物理步、退出0；重复排队10531已取消。复用原版SAM服务并仅新增1个π0.5服务，启动峰值21.9GB、附加进程树23.0GB RSS；原版剩余3局继续。初次附加启动的Slurm step10446.1因SLURM_JOB_NAME为srun命令名而非父作业名被guard拒绝，退出1、无物理请求；已改查scontrol真实作业归属，24项launcher CPU测试通过，旧日志保留。

正式六条在step10446.3 / `results/bounded_skills/hybrid_repair_20261019/e120c61f/owned_batch0_10446_6`运行。t2/13402000私有false、no_progress、25控制步；旧为50步。初始旧物理和请求SHA均相同，但第一动作最大差0.003125，预备位后公开夹爪开度相差约12.4微米。这不能归因于交还改动。handoff停稳18步，后继请求正常、bounded chunk执行23步。t2/13401000已落VLA分支false/70步，object_swap_t2/17401000已落true/45步；其后继chunk仍待汇总。

`D2_preparation_history_CPU_20261019.json`在同一真实MuJoCo保存状态下施加0/1/10/100步前史：下一物理qpos完全相同，公开gripper_qpos却随历史变；warmstart最后恢复也不能消除。Robosuite Observable._time_since_last_sample/_sampled及env.cur_time/timestep不在旧快照，force采样会推进相位。新`v5_branch_state`保存时钟、Observable运行字段和_obs_cache；恢复完整缓存时不force采样，并最后恢复qacc_warmstart。历史旧快照只可明确标记canonical fresh，无法补回真实旧相位，不能声称旧π输入逐字节一致。

`D2_preparation_history_fixed_CPU_20261019.json`：8/8完整恢复身份一致，物理qpos最大差0、公开夹爪最大差0。新分支还记录实际Pi05VLAClient.encode_obs的各字段SHA、states和采样seed，以及预测actions SHA/首动作，便于直接核查首输入/首动作。50项聚焦CPU测试通过；新源码快照待登记。10554仍排队，因原版分叉源缺完整观测恢复已取消，耗时0，未提交正式71状态。

窄测量实验源6a14b147已提交推送、默认off；330项CPU测试通过。仅逐步重测选中源/目标及父部件所需类别，保留双视角每控制步检查，handoff后与普通回执均全场景复测。2状态选择的CPU准备脚本未提交GPU。此实验不能代替新完整状态恢复验证。已登记e120c61f的12条仍用旧全场景监测；6个预算对照尚未运行，下一版将重登记。

## 10/20 当前续接点

- 最新物理源码仍 bb1a691cc4715b657f31baa84a444ddb6bb2d606，未修改技能/规划或停止阈值。修复版快照 `/public/home/sunyihan/rpent_libero_eval/source_bounded_hybrid_handoff_20261019_bb1a691c`。归档 SHA256 `1842c9f8e3fd617d7f3442938838ae5c439f72c0b84e077fdc92c26c1df73641`。
- 六个 e120 分支全部闭合，汇总 `reports/D2_handoff_e120_closed_20261020.json`，逐条检查与耗时表同名 `.md`。6/6 停稳，6/6 后继请求；3 条后继实际步进，3 条扫描零步碰撞拒绝。旧快照观测相位缺失，历史动作不相同；不能当成停止设置因果比较。
- bb1a 三设置真实启动在自有 step10446.4 完成（1:38，3 worker 均首推理＋首物理步）；`reports/bb1a_startup_wire_identity_20261020.json` 证明三个首输入、预测动作哈希均相同。CPU 比较器 `scripts/compare_vla_fork_inputs_20261020.py` 实跑 3 对均一致，报告 `reports/bb1a_startup_prefix_compare_CPU_20261020.json`。重复 pending10585 已取消，10590 对其依赖已解除。
- 正式 12 条：10593，准备目录 `results/bounded_skills/hybrid_repair_20261019/bb1a691c/preparation`，manifest SHA `287cf97256694891bc0739a271d8bcf418e50f5376884a701ee1cf85ea72c745`。两个6条分片。保持 full-scene 监测；预算对照仍120/220控制步、no_progress关闭，不改成功/区域/原生停止条件。
- 按需监测试点两状态准备完成，startup10594；目录 `results/bounded_skills/targeted_vla_pilot_20261019/bb1a691c/preparation`，manifest SHA `f16b60fc3c2f5ea65fb67a288fa84b18d894a32ef11c6fd281efdd05f57cac54`。正式未提交。需与新源 full monitor 对照输入/动作前缀、停止、真值、SAM 调用和墙钟，未验证不能推广。
- 原版71状态10项CPU预检通过，独立 startup10590；目录 `results/bounded_skills/original_hybrid_forks_20261019/bb1a691c/preparation`，manifest SHA `b4f09cb09df18a00ab3f4a2816808cee97986f5fce790ee37d624ae6cb664726`。正式未提交。附加原版startup10446.5在父原版10446_6自然COMPLETED后被Slurm终止（45秒、CANCELLED 0:15，无首物理证据），收据 `reports/original_owned_startup_interrupted_20261020.json`；后续长分支只用独立分配。
- 唯一资源控制器 PID2224026，优先10446/10593/10590/10594；日志 `reports/monitor_hybrid_repair_bb1a691c_20261020.log`。旧PID2198110已结束。资源仍仅node02、nice500，≤3 GPU（C2无GPU R/PD才可借第四）、≤80 CPU/600GB，保护rf/c5/c6/held。共享 COORDINATION 已追加六条闭合、wire一致性、新作业ID与附加startup中断，不能整读大文件。
- 下一步刷新10590/10593/10594的sacct与日志，真实startup通过再放正式；核对完整分支输入/预测共有前缀，不能只看初始物理SHA。原版220已闭合：131/220，worker错误0；分类/Wilson/逐局在 reports/original220_shared_closed_20261020.json 和同名.md，仅登记old164+10446 new56，不混入startup/D2/诊断。

## 10/20 13:27 PDT 提示词坐标系修复（优先于上文在途状态）

证据 `reports/D2_pi05_prompt_frame_CPU_20261020.json`：原始保存的测量图与policy图同为256×256，逐像素精确水平镜像。标定右轴为(0,1,0)，目标e75投影在测量图u126.45 / policy图u128.55，另一碗e118在测量图u233.54 / policy图u21.46。旧提示却为pick up the leftmost bowl。`reports/D2_endpoint_actual_objects_CPU_20261020_r1.json`从8个保存端点恢复真实物理几何，qpos/速度状态最大差0、无物理步/GPU；spatial t2确有另一碗双指接触，目标仍约29cm外。不能继续把这类失败只归因于no_progress阈值。

已停止唯一控制器2282060，并取消自有10593、10598在途/余片，收据 `reports/D2_prompt_frame_stop_old_source_20261020.json`；所有已完成和部分记录保留，不与新方向规则合并。10597旧提示试点两状态均false（253.57秒/522.09秒），完整控制记录保留；旧完整监测对照没闭合，不能宣布窄监测通过或停止规则选定。

新代码只为bounded call_vla生成Pi图方向描述：右轴取反，front/back不变；测量中的area left/right名字同时交换。源/目标ID、公开状态关系、像素输入和机器人状态不动。提示版本为measured-libero-subtask/3-pi05-view，公共schema仍bounded-skills/4。旧v5渲染接口未改。新source待CPU回归通过后提交、快照登记，三设置/原版/窄监测均重新真实startup，再跑原状态原采样种子。无新训练，无PRO专用规则。

提示框架修复 CPU 验证：v5_subtasks、bounded_skills、hybrid diagnostic/repair、branch state、shared launcher 共333项通过（187.98秒），py_compile和diff-check通过。此前两次新测试fixture错误（缺replace导入、错误假设e2存在）已修正；未放宽任何物理判据。

## 最新续接：e2470622 正式在途

源码 e2470622cea0795eece8f1ffdb95d713df30a272 已推送harness-v5；快照 `/public/home/sunyihan/rpent_libero_eval/source_bounded_hybrid_handoff_20261019_e2470622`，归档 `bounded_pi05_prompt_frame_20261020.tar.gz` SHA256 `8fd2efdf2268d0e3c885d88ebe8608cdde743750698d1a10285655845e978906`。入口 `scripts.probe_bounded_hybrid_repair:evaluate_case`，解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`，固定launcher仍`launcher_shared_20261019_3fa8bb8f1740`。首次归档在封口前启动上传，SHA预检拒绝且未占GPU；完整文件以rsync append-verify补齐后哈希通过，未绕过检查。

- D2准备：`results/bounded_skills/hybrid_repair_20261019/e2470622/preparation`，manifest SHA `a86c982493d3be3b2a5ed55f4200685ddd9a456bd98cfcb9bc92853c2b174105`。Startup10607三设置真实首推理＋首物理步通过；`reports/e247_startup_wire_identity_20261020.json`核对真实rightmost提示哈希、首输入与动作三者相同。正式10610两个6条分片。
- 原版准备：`results/bounded_skills/original_hybrid_forks_20261019/e2470622/preparation`，manifest SHA `20f736be6f71de402e5284014272b3eedc57a025a4a1e852ead30cac10089f3f`。Startup10608真实通过，正式10612九片。仍为全场景监测，窄测量尚未采用。杯子先到固定goal_index/phase的子任务起点；到不了保留prefix_not_reached，不算已测π失败。
- 窄监测准备：`results/bounded_skills/targeted_vla_pilot_20261019/e2470622/preparation`，manifest SHA `eaab5662901682c4b91da3e05e8385f60e9913b411800c26c670d9ef016b8d36`。Startup10609真实通过，正式10613；只两状态性能/一致性对照，不估成功率，不推广到全部原版直到对照闭合。
- 当前唯一资源控制器PID2378133，`reports/monitor_e247_formal_replacement_20261020.json`和`reports/monitor_hybrid_repair_e2470622_20261020.log`。优先10610/10612/10613。旧PID2368653已停止。node02，nice500；C2无GPU R/PD可借第四卡，有则10分钟内降throttle，不取消运行；合计≤80CPU/600GB，保护rf/c5/c6和held。
- `reports/e247_actual_first_input_vs_bb1_CPU_20261020_r1.json`：六例实际首输入非提示字段全同；三个碗例只task_descriptions改变，三个唯一类别无字段改变，允许把新旧差异明确归因到提示转换，不能与缺旧观测相位的10477直接作相同输入声明。
- 用户要求的最终靠近对象已补准确私有端点读取：`scripts/diagnose_vla_endpoints_CPU_20261020.py`，从保存endpoint恢复ControlEnv，不渲染、不进物理、不加载SAM/VLA，不恢复/声称旧相机采样相位；报告真实body origins/双指接触、距EEF、qpos/速度状态最大差。旧8例输出`reports/D2_endpoint_actual_objects_CPU_20261020_r1.json`，max状态差0；新源闭合后对新端点再跑。原来基于开局公开中心的nearest只是近似，不能替代新私有结果。

下一步：持续查新三组worker_summary与sacct；完成一条即做中间分析，出现worker_error立即日志诊断。先用共有实际输入/预测前缀核full vs targeted及三预算设置，再汇总真实停止原因/抓取真值/最终接触对象/交还后首bounded chunk。新源完整结果尚无，不要从旧0/2或首步通过推断成功率。再决定停止配置和窄监测；确认前不报混合整局上限。共享COORDINATION已通知源路径/SHA/入口/解释器/新旧批隔离和全部作业ID。

## 10/20 标定接线修复（优先于e247在途状态）

`reports/e247_missing_calibration_trace_CPU_20261020.json`：已登记原版空夹爪校准 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/gripper513_original_opening_calibration_20261005/runtime_calibration.json`，SHA256 `d4d977a5e5c23a23d80983ab34a4958373c6103035c2156ced24038204e4ca1c`，lower=0.0027024445589631796m、upper=0.07729756832122803m。当前hybrid构造V5Executor没传它，holding_aperture回退.005<opening<.075。t2/13402000真抓住后的opening约.00376m，53个抬升样本全被旧gate拒，离线首公开配对57步（rise50mm、手移10.97mm、相对差.506mm）。这不是新调PRO阈值，必须接回既有机器人标定；早期私有真值时刻不能从此捏造。

已停止10610、10612所有在途/待排片，保留源e247部分记录；10613已COMPLETED保留（私有t2=true、salad=false），控制器2378133已停。收据 `reports/e247_missing_calibration_stop_20261020.json`。当前没有新GPU提交，先完成代码CPU检查。

新代码：manifest case顶层`grasp_measurement_calibration`保存path/SHA，三种prepare脚本默认取已登记原版标定，可显式指定；CPU validate_plan和运行时都读同一SHA固定文件，`make_executor`实际传给V5Executor，运行时落`public_gripper_calibration.json`证明加载来源。新建D2计划需要显式校准引用。没有改force/speed、3cm抬升阈值、co-motion阈值或v3私有真值。

验证：hybrid diagnostic/repair/shared launcher 45项通过（2.06s），py_compile、diff-check通过；配置回归跨实际JSON加载→真实V5Executor→公开开度分类，3.76mm允许继续RGBD证据、1.8mm空闭/79mm空开仍拒，校准SHA变化拒绝。下一步逐文件提交推送，等新归档完全生成后才上传；真实三设置/原版/窄监测startup后正式重放。所有旧源记录单独保留。
