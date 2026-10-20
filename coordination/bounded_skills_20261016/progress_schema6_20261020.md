schema6 六项实现已接线；384 项相关测试通过，尚未通过 D 的物理核对。
原版 220 离线选 N=31，保留全部 131 个历史成功，但历史墙钟节省为 0；不改用会截断成功局的更小 N。
增量感知首版失败保留；双视角保守版比较 1,289 次锚点，56 次可缓存，位置/尺寸差均 0，超过 1 cm 的漏变化 0。
保存输入的配准 JSON 与 6 张平面掩码逐字节一致；平面拟合小幅提速，配准批量化几乎无提速。
177d44e9修复公开候选失败记账，266项相关回归通过；两批已真实启动，随后因Codex2 GPU排队归还借卡。10698自然运行，续跑已登记等待Codex2启动；D的完整结果仍待。

## 接口与实现

- 共享规格：`SKILL_PACKAGE_SPEC.md`；schema `bounded-skills/6`，legal `public-request-legal/3`。
- `move_to(anchor)` 合并及失败后换方向；只在选中后按 above/right/front/left × over/direct/around 完整规划。回执记录实际解析方向与路径。
- `guarded_move(anchor, axis, direction)`：公开 RGB-D 表面配准，2 cm 测量检查点，连续两次无进展停，最多 30 cm/400 控制；保留 nudge。未知终点必须先拿到实际回执再执行后继动作。
- 双视角 ROI 增量测量、执行路径 10 cm 邻域刷新、持物/接触强制更新、mask 跟踪失败回 SAM；缓存显式带 `cached` 和 `capture_step`。
- `progress` 是公开进展计数，重复回执和缓存不能清零；N 只从原版 220 定，未使用 D2。
- chunk 后继只做端点筛查；夹爪步后的姿态 IK 可复用，碰撞/载荷屏幕仍在实际执行前重建。
- 物体测量复用已有向量化像素筛选与保序体素化，新增局部平面批量 SVD、接触轴分批最近邻查询。未改变控制力度、速度、预算或真值判据。

## CPU 原件

`reports/schema6_original220_progress_r2.json`：220 个原版回合，所有 N 的逐局截断与节省墙钟、100 个 move_to 分叉登记。N=1/2/4/8/16/30 分别截断 30/4/2/1/1/1 个成功回合，N=31 截断 0，节省 0 秒。进展定义偏保守，结论如实保留。

`reports/schema6_incremental_original24_r1.json`：原版前 24 局，单主视角低分辨率差分拟缓存 610/1289，169 次与新测量相差 >1 cm（其中 104 次 table）。它不是通过证据，也不是仿真真值运动标签。

`reports/schema6_incremental_original24_r2.json`：相同 1289 次，双视角全分辨率差分拟缓存 56，超过 1 cm 的漏变化 0；缓存候选位置/尺寸的最大差都是 0。更保守只获得 4.3% 的复用，尚无整局提速结论。实际执行路径邻域还会强制刷新，不能把该数当生产 SAM 减少量。

`reports/schema6_numeric_saved3_r2.json`：碗/杯/微波炉三个保存公开输入，配准完整 JSON SHA 相同；6 张主/腕掩码逐字节相同。配准 old/new 秒为 7.632/7.556、12.275/12.273、5.672/5.532；平面拟合主要在 0.047–0.125 秒范围，不能用它宣称解决几十秒瓶颈。

测试：相关 adapter/chunk/schema/合法集/分叉/持物/追踪 384 passed（3m52s）；pytest 原有 timeout 配置警告 1 条。脚本通过 py_compile。没有训练模型。

## 资源和旧分母

`reports/schema6_resource_return_10688_completed.json`：取消 10688_2 时，9 个完整 worker 保留；`libero_spatial_task_t4_s40` 的中断轨迹保留并登记续跑。Codex2 的 10749 排队 20:43:13、实际启动 21:01:42（集群时间）；归还耗时 1109 秒，超出 600 秒要求，记一次违例。10748 的 CPU sacct 门控失败原日志保留；10749 实际运行后，10699 改为 afterany:10698，避免占第二张卡。c5/c6/rf/p3a5 与旧 held 作业未修改。

旧 3968 D2 原件：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/{D2_public_binding_hybrid_20261020,D2_cached_binding_hybrid_20261020}/3968bdb4/job1068*/N8/`。两条 relation 错误由 10699/source6a2d6bb8 补跑，和 schema6 分开；Codex1 可直接取 worker/choices/private_truth/summary 原件归因。

## 继续执行

先完成冻结源码的 CPU preflight、同 launcher 真实物理启动，再逐步跑 D：100 个 move 位置成对、抽屉开/关各 20 对、同固定 32 个 N1、新 D2 40×恢复0/1/2。按完成回合续跑，启动错误非零退出；保持 node02/1 GPU/nice500，CPU 和 Codex2 合计不超 80 核/600 GB。既有确认状态永久排除训练，D2 全部评测专用。

## 源码与提交后登记

源码提交 `5fad1176`，仅启动器输入检查/独立启动入口补丁 `907a572f`，已普通推送 `user-fork/harness-v5`。远端运行快照 `/public/home/sunyihan/rpent_libero_eval/source_schema6_907a572f_20261020`，归档 SHA256 `0ff4f706a7609438f4f106b46f0d01fec174c7e949efdaedd49b1b3e50857d41`。schema SHA256 `ef7531ab9b810ee8c56679c7c685941321ee3c2046080b359a1478fc4c722794`；contract SHA256 `c4b559d00d0333532ce76467df32e0ce12097ca6ef21c53834d30476f3315d8c`。

机器可读登记保存在远端 `results/bounded_skills/schema6_20261020/preparation_907a572f/`：move100.json（100 对）、drawer40.json（开关各 20 对）、N1_fixed32.json（同 32 状态）、D2_recovery0/1/2.json（每档 40 局）。上一份 preparation/ 与 5fad 快照保留；CPU preflight 均通过。

共享 COORDINATION 已写 schema6 字段变化、SHA 与证据范围，回执 `reports/schema6_interface_delivery.json`。独立物理启动 `10755`（node02/1GPU/8CPU/96GB/nice500）等 `10699` 后开始；当前只是排队，没有物理成绩。正式 100 对尚未放行。此后新增启动壳不改变固定的技能/规划源码。

## 21:50 集群时间更新

`ec899215` 快照已独立解压到 `/public/home/sunyihan/rpent_libero_eval/source_schema6_ec899215_20261020`，归档 SHA256 `435cb7fc817e7c6cf549e483d58ae868f8fa1d3a94d4ce4c3d0c4b4777b1c7d8`。move100、drawer40、N1_fixed32、D2 三档共六类 CPU 预检全部通过，原件 `reports/schema6_ec899215_preflight.json`。接口 SHA 未变化，已另追加共享登记。旧待运行启动 10755 取消，换为 10757/ec899215，仍等待 10699；这不构成真实启动通过。

10698 基线臂完成前 22 个完整回合，优化臂尚未开始；`reports/schema6_N1_three_arm_interim_r1.json` 保留此前 21 局中间原件。三臂汇总器现已逐对输出 baseline/optimized/schema6，ID 因 schema 变化而不同只作为描述，不用来判断语义等价。初态哈希差异继续披露。GPU 当前 10698、Codex2 的 10749/10754、用户 p3a5 各自运行；C3 未占第二张卡。

检查 D2 独立重放路径时发现：两路都失败时没有将已测得的择优方法加入重放，导致未实际重放。新代码对已测得的零比零平局也从整局初态实际重放 self；方法未知仍不代选。原分叉与旧源码保留。对应回归两类加现有混合/汇总共 40 passed（`/tmp/schema6_replay_regression.log`）；新增物理汇总器保留未完成/未知分母、逐状态翻转、Wilson 区间，并拒绝初态哈希不一致的配对。报告烟测原件 `reports/schema6_reporting_smoke.json`。该补丁须以新源码登记 D2，不能混入正在运行的旧分母。

## f4 源物理启动与闭合失败恢复修复

`f4bebbd6` 的独立物理启动 10760 COMPLETED 0:0、2分38秒。默认/原选变体从相同完整物理哈希出发，各执行119控制步，均到达端点；不是完整子任务成功率。两个正式开发批 10762(move100)、10763(drawer40)采用固定 f4 技能/规划源、`ee418571` 启动器，分别通过同 launcher 的真实启动后才启动 N8。每局独立进程/EGL/RNG/IK，共享单卡 SAM/π 服务；不并行局内候选。37 项启动器回归通过，固定32时延仍为N1。提交收据 `reports/schema6_{move100,drawer40}_submission.json`。

随后 CPU 回归发现：set_gripper(close)未夹到物体时没有 held ID，导致失败未归给已测量的接触锚点，下次请求漏掉换方向候选（实测1个、应有4个）。补丁从实际执行回执的夹爪检查取得接触锚点，并保留当前公开 active 作为接触上下文；不读取私有坐标。10762/10763在22:05:37停止以更换开发源码，所有记录保留。move批已关闭2对，两变体均2/2、改善0、退步0，Wilson均[34.24%,100%]；其余98对未完成，不计失败。抽屉没有完整回合，仅启动证据。原件 `reports/schema6_move100_f4_stopped_diagnostic.json`、`reports/schema6_f4_empty_closure_stop.json`。这些是修复前诊断，不混入修复后的 D 分母。

借卡现在由显式 job ID 的30秒监控负责：Codex2出现GPU排队即取消该借卡分片，保留完成回合，实际退出后再确认归还；CPU-only pending不触发GPU退卡。10760监控自然结束未取消，原件 `reports/schema6_borrow10760.jsonl`。10762/10763随开发源码切换结束；未修改任何保护作业和旧held。10698仍自然运行，当前基线完成26局，优化臂还未开始。

闭合修复及相关技能/chunk回归298 passed（210.10秒，`/tmp/schema6_empty_close_fixed.log`）；原先仅1个方向的回归现得到4个候选。原有pytest timeout配置警告保留。后续从新源码重新登记与物理启动，再开D批。

## 22:30 集群时间：等价提速、N1续跑和新诊断关联

`bfd030c1` 的10764/10765均已通过同launcher真实物理启动，才发放N8局进程。10764截至中间汇总关闭9对，其中7对真值已知，两臂各6/7，改善0、退步0；2对因诊断子任务缺关联为unknown，尚未完成91对。10765尚无完整双臂回合。不是D通过证据。

CPU复现：case008公开锚点e114为microwave door，part_of=e98；现有任务绑定到e98。旧move诊断只比较ID相等，因此没有选择要测量的子任务。新launcher按现有测量的part_of祖先关联私有目标，并在已持物时跳过pick、关联运输目的地。它不修改公开候选、绑定规则、技能或判据。4项launcher回归通过（含真实启动顺序/续跑/父子关联/持物阶段），旧unknown原件保留，新物理结果须另登记。

`b1365785` 在原有8mm残差截断下使用精确最近邻查询上界；三个真实保存输入完整配准JSON逐字节相同，6张平面mask差0。`reports/schema6_numeric_capped_saved3_r1.json`：碗7.824→3.558秒，杯12.302→4.410秒，微波炉5.786→2.432秒，仅函数级2.20–2.79倍，不代表整局提速。相关40项CPU检查通过。

`ce2de76f85a0049b96a4a362ca3d69be7e4007c4` 已普通推送；含N1逐局断点续跑、D2独立重放墙钟字段，44项相关检查通过。快照`/public/home/sunyihan/rpent_libero_eval/source_schema6_ce2de76f_20261020`，归档SHA256 `45b70244d85afec85f4b02777dc836e2f0fd4523f1f12836651014689903efa3`。六类CPU预检全通过，登记`preparation_ce2de76f/`。schema和contract SHA不变。

已提交10771固定32 N1（并发1，等10764）、10772/10773/10774 D2恢复0/1/2（每档40、N8，依次等10765及前一档）。每批重新真实启动，有已完成回合指针和中断保留；独立整局重放墙钟排除方法选择与分叉，未知局不参与速度平均。借卡监控覆盖这些显式job，Codex2出现GPU排队即取消借卡任务，CPU-only排队不触发。所有作业仅node02、nice500；无训练或保护作业修改。

## 22:38 集群时间：修复合并候选的失败记账

物理日志case001中，零步`measured_sweep_collision`连续出现，下一请求的`move_to(anchor=e54)`却始终`recent_failures=0`。CPU同样复现：第一次失败后第二次应为1，实际为0。原因是完整执行会将合并选项解析成带approach/path的内部变体；FailureMemory用skill+parameters作键，执行时记内部变体，下一次公开请求查合并选项，键不同。

修复只在单步执行记账处保留原公开候选作为键，实际内部路线、碰撞筛查、回执ID与判据不改。回归验证连续两次零步碰撞后，合并选项被移出，其他方向仍可选；公开场景变化后才恢复。schema/contract字段及SHA不变。

修复后的schema6、技能适配器及启动器回归266 passed，188.94秒，原有pytest timeout配置警告1条；日志`/tmp/schema6_public_retry_identity_fixed.log`。修复前新回归在第二次请求稳定失败（0 != 1），修复后通过。

10764最终关闭11对，9对已知，两臂各7/9，改善0、退步0；2对unknown、89未完成。10776的新诊断launcher已真实启动，但随后因同一记账缺陷停批。22:37:48取消10765/10776及尚未运行的10771–10774，全部中断和完整原件保留，不混入修复后的D分母。停止记录远端`stopped_public_retry_identity_20261020.json`；10698/10699及保护作业未改。旧3968末局续跑10777排在10699后，保持旧源独立分母。

## 22:50 集群时间（07:50 PDT）：新源真实启动通过

源码`177d44e99cb8944112b0c4720debf0b5a61d0a05`已普通推送；快照`/public/home/sunyihan/rpent_libero_eval/source_schema6_177d44e9_20261020`，归档SHA256 `d97bd3757b2901b5cbafb6da4cdbd9ce44c0880794b69757ae56662b87fb1bfe`。六类CPU预检均通过，原件`reports/schema6_177d44e9_preflight.json`；schema/contract SHA未变，已交Codex1/2登记，回执`reports/interface_177d44e9_delivery.json`。

10780/move100与10781/drawer40均已通过同快照、同launcher的真实启动，再发放各8个独立回合进程。move默认/原选两臂完整初态哈希相同，各执行119控制步；drawer nudge/guarded两臂分别执行289/891控制步。证据`reports/startup_177d44e9_evidence_r1.json`。这只证明真实启动，不是完整子任务或回合的成功率。

10782固定32 N1等10780；10783/10784/10785为D2恢复预算0/1/2，各40局、依次等10781及前一档。六个显式借卡job均有30秒轮询的归还监控；Codex2仅CPU排队不触发，GPU排队立即取消借卡分片并保留完成回合。当前C3三张（10698/10780/10781），Codex2一张（10749），合计C3 GPU资源24核/288GB；无保护作业和旧held修改。

22:55物理核对`reports/public_retry_physical_177d44e9_r1.json`：drawer case001的合并move连续两次零步碰撞，公开失败计数0→1，第三次请求移除该合并选项，其他方向保留。move100已关闭5对、两臂各5/5（Wilson [56.55%,100%]）、改善0/退步0，95对待完成，原件`reports/move100_N8_177d44e9_interim_2255.json`。drawer尚无完整双臂回合，不能从启动样本推断成功率。

N1三臂中间原件`reports/N1_three_arm_177d44e9_interim_2252.json`：10698基线关闭26整局及2个VLA试点；整局25/26，每循环中位117.08秒、整局中位289.76秒。优化臂与schema6臂均尚无关闭记录，不存在已验证的整局提速或结果一致性结论。六类新manifest已同步到`preparation/schema6_177d44e9/`，均保留远端源码与输入哈希。

## N1旧VLA试点的schema6迁移修复

CPU检查发现固定32中的两个VLA试点仍走旧版“只换schema header”入口，该入口不支持v6；旧检查点也没有schema6新增的公开进展/合并候选运行时字段。不能把旧版12个move变体仅换header当作schema6候选。

修复只在N1登记为`schema6_source`时启用：恢复同一物理状态与原重试历史，初始化新增运行时字段，重新测量公开传感器并生成schema6请求；在配对原件中显式记`schema6_public_request_rebuilt=true`，不声称请求与旧版相等。N1启动器在正式32状态前，用同launcher额外真实启动旧试点24，成功才继续。此前运行的177d44e9技能/规划源码不修改，move与drawer批次继续。

迁移/共享启动器50 passed；schema6/物理启动器15 passed，原有pytest timeout配置警告保留。日志`/tmp/schema6_replay_migration_regression.log`、`/tmp/schema6_replay_adapter_regression.log`；shell语法、py_compile通过。N1待更换为该评测入口修复的独立快照与manifest后重提；尚无新试点物理结果。

## 23:04集群时间：借卡实际归还与续跑登记

Codex2 GPU作业10786于22:58:10提交；10780/10781于22:58:41实际退出，归还用时31秒，满足10分钟要求。旧pending 10782–10785同步取消，未执行。原件`reports/schema6_card_return_10786_and_resume2.json`。关闭9个move对，8对已知，两臂配对均6/8，改善0/退步0；case007原选变体当前不合法，保留unknown，不补成失败。单臂默认6/9、原选6/8的分母不同，不能直接比较。drawer尚无完整双臂局，全部中断轨迹保留。

已重提10787 move100、10788 drawer40，均`after:10786`，仅等Codex2服务实际启动，不提前占卡。随后10789固定32 N1、10790/10791/10792 D2恢复0/1/2按原依赖接续。所有job仍仅node02、nice500、每job1GPU/8CPU/96GB。六个归还监控保持运行；仅在Dependency等待的job不持卡，继续等待，变为可运行或运行后仍按Codex2 GPU排队信号归还。

N1评测入口源码`8c3cdd38bf10d8b0910f6b578b85d384188c9c01`已普通推送，快照`/public/home/sunyihan/rpent_libero_eval/source_schema6_8c3cdd38_20261020`，归档SHA256 `64b46dbbe9b338e509c2598af1ac5426aa7c064541d602b64eaf9c6b2b8219f8`。技能、guarded、增量感知、schema和contract与177完全相同；只修N1旧试点恢复入口并加真实试点启动。新N1 CPU预检通过，manifest `preparation/schema6_8c3cdd38/N1_fixed32.json`，独立输出`results/bounded_skills/schema6_20261020/8c3cdd38/N1_fixed32/`。其余续跑保持177源码与完成回合指针，不混分母。

## 08:20 PDT：合并move的接近阶段与CPU标注修复

177d44e9的drawer case000反复move_to/腕部观察。实物仿真日志显示EEF已到合并规划器选择的上方入口，但oracle仍比较旧接触拟合的侧向approach_xyz_m。因此尚未进入descend；不是没有执行物理控制，也不是碰撞筛查已证明下降可行。

CPU稳定复现：同一已测量侧向接触计划，schema6合并move默认从上方接近，旧选择序列为move_to→observe。修复在公开路线预测和实际成功move后保存该路线的move_endpoint_xyz_m；oracle以此判断接近阶段，仍用原接触点生成descend并完整筛查。预测只更新克隆，真实计划不被污染；未成功的move不提交端点。通用私有规则版本升为libero-private-task-progress-rules/14，不增加任务特例，schema/contract不变。

同时修复capture_annotation_state遗漏schema6_v1/public_progress：CPU快照必须保留当前合并候选和便宜前缀口径。离线11项回归通过（45.69秒），包含在线与离线legal/acceptable/selected逐前缀一致、零仿真步/零RPC新增。日志/tmp/schema6_capture_regression.log。修复前接近端点回归稳定失败，修复后通过。

08:13 PDT停止自己的10787/10788及尚未执行的10789–10792，以免已知阶段错误继续耗卡；完整与中断原件保留在177d44e9目录，旧确认状态不改判。10698、10699、10777和Codex2/保护/held作业未改。Codex2已自行撤销10786，其后续GPU短测将等10749结束，不再等一个已取消的依赖。

接近阶段相关四文件回归296项通过；8项只因原测试硬编码旧judge /13失败（前面的行为断言已过），已更新为/14后单独复跑。首轮日志/tmp/schema6_endpoint_phase_regression.log；版本断言复跑/tmp/schema6_endpoint_phase_judge_rerun.log。旧物理停止汇总reports/move177_stopped_endpoint_r1.json仍为9关闭/8已知、两臂6/8、改善0退步0；未完成91对，unknown1对。逐次阶段证据reports/endpoint_phase_177_evidence.json。新物理分母尚未开始。

## 新源be3dae5e物理批和CPU迁移接口

be3dae5e32afff965d2ede20abb5fc159ccbc7ab已普通推送，快照source_schema6_be3dae5e_20261020，archive SHA256 7d8647ec01bbf9e8f882b5c32557b98398c5130720d1e3c833f82ae9977c5532。六类CPU preflight全通过，manifest与提交收据preparation/schema6_be3dae5e/。10793 move100、10794 drawer40已运行；10795 N1等10793，10796–10798 D2恢复0/1/2等drawer及前档。当前三张C3(含10698)、一张C2，无C2 GPU排队，借卡监控每30秒查询。所有node02/nice500；完成与中断回合分开保留。schema与contract SHA不变。

296项相关回归通过，加更新judge版本断言后的8项通过(20.55秒)，离线快照11项通过(45.69秒)。本次旧版judge断言失败原日志保留，不伪称首次全过。

Codex2要求旧original220 annotation与18保存PRO状态的CPU新候选入口。新增rebuild_schema6_captured_request(state,request)返回(rebuilt_state,current_request,mapping_flags)，共享当前请求候选builder。不执行仿真、不调用感知/RPC；保留捕获的RGB-D/本体/接触计划，private_status不参与候选生成。旧move12变体合并映射到1项；above/over旧ID另列default_old_move_by_anchor。旧标签必须按新prefix重算，不能只改header。缺失failure/progress历史分别显式标记，已保存旧失败记账投影到合并项。执行中未完成前缀拒绝迁移，必须在该前缀完成后重采。D2/PRO仍仅评测，接口不授权其数据进训练。

离线接口14项通过(42.92秒)，新增旧失败记账投影1项通过(2.14秒)；schema6 builder12项通过(1.91秒)。同schema6输入重建请求完全相等；legacy old→new映射、任意非oracle前缀、候选对私有目标不敏感、无RPC/无物理动作均有回归。日志/tmp/schema6_captured_rebuild_full.log、/tmp/schema6_capture_memory_projection.log、/tmp/schema6_builder_regression.log。真实旧保存输入的适配仍须单独跑，不将CPU假输入测试称物理证据。该接口补丁不改变在跑be3dae5e分母。

离线迁移的有效默认变体保持显式未知：above/over只列作优先序参考，不能当作实际通过完整规划的默认路线。返回default_old_candidate_id_by_new_id全部null，default_resolution写明需完整路线规划；prefix_compatible空且requires_prefix_relabel=true，供Codex2保留未知。不得把优先序参考当作可接受集合成员资格证据。四项映射/历史回归通过，日志/tmp/schema6_default_provenance.log。

## 精确18条PRO CPU交付与端点收敛诊断

`ff71966c` 接口已用Codex2的精确18条 `dataset_v2/pro_eval.jsonl.gz` 跑完，公开输出远端 `results/bounded_skills/schema6_20261020/PRO18_CPU_ff71966c_r2/public_packets.jsonl`，私有空前缀标签单列 `private_empty_prefix_labels.jsonl`。18/18成功重建，候选总数1646→838，单请求35–79。原件摘要保存在 `reports/PRO18_CPU_ff71966c_r2_summary.json`。消费者的18条旧请求曾把schema3改为4；均用完整请求SHA核对恢复源请求，不猜候选或有效默认。提供者与源请求两种SHA、唯一差异字段及恢复出处全部保留。3条没有分支choices的记录，用完整SHA证明原始header后恢复；不是物理分支成功。所有18条的新空前缀私有规则可标注，但旧前缀/有效默认仍未知，不可拿来作旧正标签。首次r1仅15/18成功，失败记录保留。r2原件与源CPU callable已追加共享COORDINATION，PRO仍仅评测。

be3 drawer case000及另外状态共16次descend都在标称轨迹结束时退出，残差约2.3cm、测得末端仍约5.1cm/s；路线IK和碰撞筛查通过。原执行器只走完标称参考，没有有界端点保持，故下一步接收失败。`3429e275f045e6490699465c75a7d7b13e8ca843` 添加最多30个20Hz端点保持步，固定已筛查的同一端点、保持夹爪指令和原12mm/0.05rad判据，不扩展路线、不增加夹持力。保持用完仍不达标则明确 `endpoint_not_reached`，不能冒充endpoint成功。阻挡回归验证仍失败，跟踪滞后回归验证可收敛；motion/schema6/chunk共69项通过（52.85秒），日志 `/tmp/schema6_endpoint_hold_regression.log`。物理是否解决仍待同状态验证，不把CPU测试当作真实控制结果。

08:49 PDT取消自己的10794与尚未启动的10795–10798；原drawer仅关闭2对，均nudge/guarded失败，完整与中断原件保留。10793 move旧源继续提供开发对照，10698按用户要求自然运行；其他项目、Codex2及held不动。3429快照归档SHA256 `ecdc4365cc5aad2b379b147edbef7469b8466e490b17d51219eb4bcf36d8bff7`，新抽屉同状态真实启动将先验证端点保持，不能用be3成绩混入新源码分母。schema/contract/spec字节均未变，D尚未通过。

## 10/21：端点保持未消除阻挡，已定位接触豁免错误

10799完成同launcher物理启动，但descend在30个端点保持后仍误差0.02345255m；保持不是修复结果。10800因诊断launcher缺PYTHONPATH启动失败(exit1，原文ModuleNotFoundError: No module named robots)，修入口后10803完成334控制步纯物理回放，每一步末端位置误差最大0.0m。第287步起右手指壳gripper0_right_finger2_collision与wooden_cabinet_1_g18接触48步，最小关节余量0.93589rad；不是关节限位。前一节关于反馈滞后的说明只是CPU假设，不能解释这次物理失败。

公开保存输入同时支持根因：下降第20个参考点(固定下降前的两个实测指关节)与目标点云有163个右手指壳交点，其中72个在指垫接触区域外；场景点云交点为0。这些交点匹配测得的把手云，而非没有测到障碍。旧contact_allowed直接豁免整份目标点云与所有手指壳；最终接触位姿本身无指壳交点，问题发生在接近路线中段。补丁只允许目标与实际指垫区域接触(含XML中指垫/指壳的重叠)，其余指壳仍筛查；合并move在选择变体时同时筛查该入口到接触点的公开路线，不再把安全入口等同于安全接触路线。判据、力、预算不变。

原件和摘要：reports/schema6_endpoint_collision_10803.json。CPU真实保存输入已能拒绝原来被豁免的72点；仍须同状态物理检查后才发放完整D批。schema/contract/spec字节不变；旧be3、3429物理分母与新补丁严格分开。

测试：screen/schema6针对性31项通过（1.94秒）；首轮相关282项中281项通过，唯一失败为旧测试只计move路线调用、未计新增接触路线检查的调用次数，已更新后针对性通过。完整相关回归正在复跑，原日志/tmp/schema6_pad_ingress_regression.log保留。Ruff指出这些旧文件已有多项格式/fixture告警，未做无关全文件整理。
