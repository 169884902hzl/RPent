交还修复已有六个保存端点的 CPU 仿真：全部停稳，三个原本真抓住的物体均保持抓持；尚未完成六条完整 VLA 重放和下一个技能验证。
新代码改为接触后零增量 OSC 阻尼停稳，保留夹爪命令；下一次移动仍做测量、扫掠和 IK 筛查。
停止规则已配置化，登记原三失败种子分别比较关闭 no_progress 的 120 / 220 控制步预算；尚无新 GPU 结果。
三个绑定失败均已归因到公开同类误检与脚本跳过观察恢复；保存请求的原 oracle 3/3 会选腕部扫描。已修恢复控制流，没有用私有坐标强绑。
10477 已按用户 10:30 第 5 条停止，旧记录完整保留；10446 原版并行继续。无训练。

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
