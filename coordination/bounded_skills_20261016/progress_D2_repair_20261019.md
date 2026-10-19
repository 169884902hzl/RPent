e120c61f 六条已闭合：6/6 停稳且生成后继请求；3 条后继技能实际步进，3 条 observe 在零步时被碰撞检查拒绝。17401000 交还后 carry_to→release 原生成功，不代表 D2 整局上限。
六分支 SAM RPC 占墙钟约 91–95%；25 控制步例共 961.88 秒，其中 SAM 877.40 秒、推理 1.16 秒、交还 0.23 秒、私有计量 0.13 秒。
旧快照漏采样缓存/相位，不能复原历史 π 输入；bb1a691c 补时钟与缓存，CPU 八种历史完整恢复的 qpos 和公开夹爪差异均为 0，50 项聚焦测试通过。
bb1a691c 三设置真实首步预检通过，实际输入和预测哈希相同；12 条正式诊断 10593 排队。原版 71 状态 CPU 预检通过，startup10590 排队；按需测量 startup10594 排队，两个正式数组均未提交。
三个绑定失败归因为公开同类误检歧义，已接合法观察恢复，物理恢复待验证；D2 不进训练/history/memory，确认状态永久排除，无训练。

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
